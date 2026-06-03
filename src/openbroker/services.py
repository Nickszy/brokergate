from fastapi import HTTPException, status

from openbroker.adapters import (
    BrokerAdapter,
    TigerPaperAdapter,
    TigerOpenApiAdapter,
    LongbridgePaperAdapter,
    LongbridgeOpenApiAdapter,
)
from openbroker.config import settings
from openbroker.models import (
    AuditEvent,
    BrokerId,
    BrokerOrderReceipt,
    ConfirmOrderRequest,
    OrderDraft,
    OrderStatus,
    TradeOrderRequest,
)
from openbroker.risk import RiskEngine, risk_engine
from openbroker.storage import InMemoryStore, store


class OrderWorkflow:
    def __init__(
        self,
        store: InMemoryStore,
        adapters: dict[BrokerId, BrokerAdapter],
        risk_engine: RiskEngine,
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.risk_engine = risk_engine

    async def create_draft(self, request: TradeOrderRequest, actor: str) -> OrderDraft:
        adapter = self.adapters.get(request.broker)
        if adapter is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")

        account_summary = await adapter.get_account_summary(request.account_id)
        risk_checks = self.risk_engine.evaluate_order(request, account_summary)
        blocked_checks = [check for check in risk_checks if check.status == "blocked"]
        if blocked_checks:
            self.store.append_audit(
                AuditEvent(
                    actor=actor,
                    action="risk.order_blocked",
                    subject=f"{request.broker}:{request.account_id}:{request.symbol}",
                    details={"risk_checks": [check.model_dump(mode="json") for check in risk_checks]},
                )
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Order blocked by risk engine",
                    "risk_checks": [check.model_dump(mode="json") for check in risk_checks],
                },
            )

        warnings = self._risk_warnings(request)
        draft = self.store.save_draft(
            OrderDraft(request=request, risk_warnings=warnings, risk_checks=risk_checks)
        )
        self.store.append_audit(
            AuditEvent(
                actor=actor,
                action="order.draft_created",
                subject=draft.id,
                details={"broker": request.broker, "symbol": request.symbol, "side": request.side},
            )
        )
        return draft

    async def confirm_and_submit(
        self,
        draft_id: str,
        confirmation: ConfirmOrderRequest,
    ) -> BrokerOrderReceipt:
        draft = self.store.get_draft(draft_id)
        if draft is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order draft not found")
        if draft.status != OrderStatus.draft:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Order draft is not confirmable")
        if confirmation.confirmation_text != self._expected_confirmation(draft):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Confirmation text mismatch")

        adapter = self.adapters.get(draft.request.broker)
        if adapter is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")

        draft.status = OrderStatus.confirmed
        self.store.save_draft(draft)
        self.store.append_audit(
            AuditEvent(
                actor=confirmation.confirmed_by,
                action="order.confirmed",
                subject=draft.id,
                details={"confirmation_text": confirmation.confirmation_text},
            )
        )
        receipt = await adapter.submit_order(draft)
        self.store.append_audit(
            AuditEvent(
                actor=confirmation.confirmed_by,
                action="order.submitted",
                subject=draft.id,
                details={"broker_order_id": receipt.broker_order_id, "broker": receipt.broker},
            )
        )
        return receipt

    @staticmethod
    def expected_confirmation(draft: OrderDraft) -> str:
        return OrderWorkflow._expected_confirmation(draft)

    @staticmethod
    def _expected_confirmation(draft: OrderDraft) -> str:
        req = draft.request
        return f"CONFIRM {req.side.upper()} {req.quantity} {req.symbol}"

    @staticmethod
    def _risk_warnings(request: TradeOrderRequest) -> list[str]:
        warnings: list[str] = []
        if request.order_type == "market":
            warnings.append("Market orders may execute at an unexpected price.")
        if request.side == "buy" and request.limit_price is None:
            warnings.append("Buy order has no limit price.")
        return warnings


if settings.broker_mode == "paper":
    tiger_adapter: BrokerAdapter = TigerPaperAdapter()
    longbridge_adapter: BrokerAdapter = LongbridgePaperAdapter()
else:
    tiger_adapter = TigerOpenApiAdapter() if settings.tiger_enabled else TigerPaperAdapter()
    longbridge_adapter = LongbridgeOpenApiAdapter() if settings.longbridge_enabled else LongbridgePaperAdapter()

workflow = OrderWorkflow(
    store=store,
    adapters={
        BrokerId.tiger: tiger_adapter,
        BrokerId.longbridge: longbridge_adapter,
    },
    risk_engine=risk_engine,
)
