from decimal import Decimal, ROUND_FLOOR

from fastapi import HTTPException, status

from brokergate.adapters import (
    BrokerAdapter,
    LongbridgeOpenApiAdapter,
    LongbridgePaperAdapter,
    TigerOpenApiAdapter,
    TigerPaperAdapter,
)
from brokergate.config import settings
from brokergate.models import (
    AuditEvent,
    BrokerId,
    BrokerOrder,
    BrokerOrderReceipt,
    BrokerOrderStatus,
    CancelOrderRequest,
    ConfirmOrderRequest,
    InstrumentProfile,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderPreview,
    OrderStatus,
    QuoteSnapshot,
    ReplaceOrderRequest,
    RiskCheckStatus,
    TradableQuantity,
    TradeOrderRequest,
)
from brokergate.risk import RiskEngine, risk_engine
from brokergate.storage import InMemoryStore, store


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

    def get_adapter(self, broker: BrokerId) -> BrokerAdapter:
        adapter = self.adapters.get(broker)
        if adapter is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")
        return adapter

    async def create_draft(self, request: TradeOrderRequest, actor: str) -> OrderDraft:
        adapter = self.get_adapter(request.broker)

        try:
            account_summary = await adapter.get_account_summary(
                request.account_id,
                currency=request.currency,
            )
        except Exception as exc:
            self.store.append_audit(
                AuditEvent(
                    actor=actor,
                    action="account.snapshot_failed",
                    subject=f"{request.broker}:{request.account_id}",
                    details={"broker": request.broker, "account_id": request.account_id, "error": str(exc)},
                )
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Broker account snapshot failed",
                    "broker": request.broker,
                    "account_id": request.account_id,
                    "error": str(exc),
                },
            ) from exc
        risk_checks = self.risk_engine.evaluate_order(request, account_summary)
        blocked_checks = [check for check in risk_checks if check.status == RiskCheckStatus.blocked]
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

        adapter = self.get_adapter(draft.request.broker)

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
        try:
            receipt = await adapter.submit_order(draft)
        except Exception as exc:
            draft.status = OrderStatus.rejected
            self.store.save_draft(draft)
            self.store.append_audit(
                AuditEvent(
                    actor=confirmation.confirmed_by,
                    action="order.submit_failed",
                    subject=draft.id,
                    details={
                        "broker": draft.request.broker,
                        "account_id": draft.request.account_id,
                        "error": str(exc),
                    },
                )
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Broker order submission failed",
                    "draft_id": draft.id,
                    "broker": draft.request.broker,
                    "error": str(exc),
                },
            ) from exc
        self.store.append_audit(
            AuditEvent(
                actor=confirmation.confirmed_by,
                action="order.submitted",
                subject=draft.id,
                details={"broker_order_id": receipt.broker_order_id, "broker": receipt.broker},
            )
        )
        return receipt

    async def preview_order(self, request: TradeOrderRequest) -> OrderPreview:
        adapter = self.get_adapter(request.broker)
        try:
            account_summary = await adapter.get_account_summary(request.account_id, currency=request.currency)
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker account snapshot failed",
                broker=request.broker,
                account_id=request.account_id,
                error=exc,
            ) from exc
        risk_checks = self.risk_engine.evaluate_order(request, account_summary)
        try:
            return await adapter.preview_order(request, account_summary)
        except NotImplementedError:
            return self._local_order_preview(request, account_summary.buying_power, risk_checks)
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker order preview failed",
                broker=request.broker,
                account_id=request.account_id,
                error=exc,
            ) from exc

    async def get_max_tradable_quantity(
        self,
        request: MaxTradableQuantityRequest,
    ) -> TradableQuantity:
        adapter = self.get_adapter(request.broker)
        try:
            return await adapter.get_max_tradable_quantity(request)
        except NotImplementedError:
            if request.side == "sell":
                try:
                    positions = await adapter.list_positions(request.account_id)
                except Exception as exc:
                    raise self._broker_bad_gateway(
                        message="Broker position list failed",
                        broker=request.broker,
                        account_id=request.account_id,
                        error=exc,
                    ) from exc
                held_quantity = Decimal("0")
                for position in positions:
                    if position.symbol.upper() == request.symbol.upper():
                        held_quantity = position.quantity
                        break
                return TradableQuantity(
                    broker=request.broker,
                    account_id=request.account_id,
                    symbol=request.symbol,
                    side=request.side,
                    price=request.price,
                    currency=request.currency,
                    max_quantity=held_quantity,
                    raw={"source": "local_position_estimate"},
                )
            try:
                account_summary = await adapter.get_account_summary(request.account_id, currency=request.currency)
            except Exception as exc:
                raise self._broker_bad_gateway(
                    message="Broker account snapshot failed",
                    broker=request.broker,
                    account_id=request.account_id,
                    error=exc,
                ) from exc
            return self._local_max_tradable_quantity(request, account_summary.buying_power)
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker max tradable quantity failed",
                broker=request.broker,
                account_id=request.account_id,
                error=exc,
            ) from exc

    async def sync_order_status(
        self,
        broker: BrokerId,
        account_id: str,
        broker_order_id: str,
        actor: str,
    ) -> BrokerOrder:
        adapter = self.get_adapter(broker)
        try:
            order = await adapter.get_order(account_id, broker_order_id)
        except KeyError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker order status sync failed",
                broker=broker,
                account_id=account_id,
                error=exc,
            ) from exc
        self.store.append_audit(
            AuditEvent(
                actor=actor,
                action="order.status_synced",
                subject=f"{broker}:{account_id}:{broker_order_id}",
                details={"status": order.status},
            )
        )
        return order

    async def replace_order(
        self,
        broker: BrokerId,
        account_id: str,
        broker_order_id: str,
        request: ReplaceOrderRequest,
    ) -> BrokerOrder:
        adapter = self.get_adapter(broker)
        try:
            existing_order = await adapter.get_order(account_id, broker_order_id)
        except KeyError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker order lookup failed",
                broker=broker,
                account_id=account_id,
                error=exc,
            ) from exc

        new_quantity = request.quantity or existing_order.quantity
        new_price = request.limit_price or existing_order.limit_price
        expected_confirmation = self._expected_replace_confirmation(
            quantity=new_quantity,
            symbol=existing_order.symbol,
            limit_price=new_price,
        )
        if request.confirmation_text != expected_confirmation:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Replace confirmation text mismatch")
        if existing_order.side == "buy":
            if new_price is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Limit price is required for buy order replacement",
                )
            risk_request = TradeOrderRequest(
                broker=broker,
                account_id=account_id,
                symbol=existing_order.symbol,
                side=existing_order.side,
                order_type=existing_order.order_type,
                quantity=new_quantity,
                limit_price=new_price,
                currency=existing_order.currency,
            )
            try:
                account_summary = await adapter.get_account_summary(account_id, currency=existing_order.currency)
            except Exception as exc:
                raise self._broker_bad_gateway(
                    message="Broker account snapshot failed",
                    broker=broker,
                    account_id=account_id,
                    error=exc,
                ) from exc
            risk_checks = self.risk_engine.evaluate_order(risk_request, account_summary)
            blocked_checks = [check for check in risk_checks if check.status == RiskCheckStatus.blocked]
            if blocked_checks:
                self.store.append_audit(
                    AuditEvent(
                        actor=request.confirmed_by,
                        action="risk.order_replace_blocked",
                        subject=f"{broker}:{account_id}:{broker_order_id}",
                        details={"risk_checks": [check.model_dump(mode="json") for check in risk_checks]},
                    )
                )
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "Order replace blocked by risk engine",
                        "risk_checks": [check.model_dump(mode="json") for check in risk_checks],
                    },
                )

        self.store.append_audit(
            AuditEvent(
                actor=request.confirmed_by,
                action="order.replace_requested",
                subject=f"{broker}:{account_id}:{broker_order_id}",
                details=request.model_dump(mode="json"),
            )
        )
        try:
            order = await adapter.replace_order(account_id, broker_order_id, request)
        except NotImplementedError as exc:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        except Exception as exc:
            self.store.append_audit(
                AuditEvent(
                    actor=request.confirmed_by,
                    action="order.replace_failed",
                    subject=f"{broker}:{account_id}:{broker_order_id}",
                    details={"error": str(exc)},
                )
            )
            raise self._broker_bad_gateway(
                message="Broker order replace failed",
                broker=broker,
                account_id=account_id,
                error=exc,
            ) from exc
        self.store.append_audit(
            AuditEvent(
                actor=request.confirmed_by,
                action="order.replace_submitted",
                subject=f"{broker}:{account_id}:{broker_order_id}",
                details={"status": order.status},
            )
        )
        return order

    async def cancel_order(
        self,
        broker: BrokerId,
        account_id: str,
        broker_order_id: str,
        request: CancelOrderRequest,
    ) -> BrokerOrder:
        adapter = self.get_adapter(broker)
        try:
            existing_order = await adapter.get_order(account_id, broker_order_id)
        except KeyError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception as exc:
            raise self._broker_bad_gateway(
                message="Broker order lookup failed",
                broker=broker,
                account_id=account_id,
                error=exc,
            ) from exc
        if existing_order.status not in {
            BrokerOrderStatus.submitted,
            BrokerOrderStatus.partially_filled,
        }:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Order status is not cancellable")

        self.store.append_audit(
            AuditEvent(
                actor=request.confirmed_by,
                action="order.cancel_requested",
                subject=f"{broker}:{account_id}:{broker_order_id}",
                details=request.model_dump(mode="json"),
            )
        )
        try:
            order = await adapter.cancel_order(account_id, broker_order_id, request)
        except NotImplementedError as exc:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        except Exception as exc:
            self.store.append_audit(
                AuditEvent(
                    actor=request.confirmed_by,
                    action="order.cancel_failed",
                    subject=f"{broker}:{account_id}:{broker_order_id}",
                    details={"error": str(exc)},
                )
            )
            raise self._broker_bad_gateway(
                message="Broker order cancel failed",
                broker=broker,
                account_id=account_id,
                error=exc,
            ) from exc
        self.store.append_audit(
            AuditEvent(
                actor=request.confirmed_by,
                action="order.cancel_submitted",
                subject=f"{broker}:{account_id}:{broker_order_id}",
                details={"status": order.status},
            )
        )
        return order

    @staticmethod
    def expected_confirmation(draft: OrderDraft) -> str:
        return OrderWorkflow._expected_confirmation(draft)

    @staticmethod
    def _expected_confirmation(draft: OrderDraft) -> str:
        req = draft.request
        return f"CONFIRM {req.side.upper()} {req.quantity} {req.symbol}"

    @staticmethod
    def _expected_replace_confirmation(
        quantity: Decimal,
        symbol: str,
        limit_price: Decimal | None,
    ) -> str:
        if limit_price is None:
            return f"CONFIRM REPLACE {quantity} {symbol}"
        return f"CONFIRM REPLACE {quantity} {symbol} {limit_price}"

    @staticmethod
    def _broker_bad_gateway(
        message: str,
        broker: BrokerId,
        account_id: str,
        error: Exception,
    ) -> HTTPException:
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": message,
                "broker": broker,
                "account_id": account_id,
                "error": str(error),
            },
        )

    @staticmethod
    def _risk_warnings(request: TradeOrderRequest) -> list[str]:
        warnings: list[str] = []
        if request.order_type == "market":
            warnings.append("Market orders may execute at an unexpected price.")
        if request.side == "buy" and request.limit_price is None:
            warnings.append("Buy order has no limit price.")
        return warnings

    @staticmethod
    def _local_order_preview(
        request: TradeOrderRequest,
        buying_power: Decimal,
        risk_checks,
    ) -> OrderPreview:
        estimated_amount = None
        max_quantity = None
        if request.limit_price is not None:
            estimated_amount = request.quantity * request.limit_price
            max_quantity = (buying_power / request.limit_price).to_integral_value(
                rounding=ROUND_FLOOR
            )
        return OrderPreview(
            broker=request.broker,
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            limit_price=request.limit_price,
            estimated_amount=estimated_amount,
            max_tradable_quantity=max_quantity,
            risk_checks=risk_checks,
            broker_preview={"source": "local_estimate"},
        )

    @staticmethod
    def _local_max_tradable_quantity(
        request: MaxTradableQuantityRequest,
        buying_power: Decimal,
    ) -> TradableQuantity:
        if request.price is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Price is required for local max tradable quantity estimate",
            )
        return TradableQuantity(
            broker=request.broker,
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            currency=request.currency,
            max_quantity=(buying_power / request.price).to_integral_value(rounding=ROUND_FLOOR),
            raw={"source": "local_estimate", "buying_power": str(buying_power)},
        )


class MarketDataRouter:
    def __init__(
        self,
        adapters: dict[BrokerId, BrokerAdapter],
        preferred_order: tuple[BrokerId, ...] = (BrokerId.tiger, BrokerId.longbridge),
    ) -> None:
        self.adapters = adapters
        self.preferred_order = preferred_order

    async def get_quote_snapshots(
        self,
        broker: str,
        symbols: list[str],
        fallback: bool = False,
    ) -> list[QuoteSnapshot]:
        attempts = self._build_attempts(broker, fallback)
        last_error: tuple[BrokerId, Exception] | None = None
        fallback_from: BrokerId | None = None
        fallback_reason: str | None = None

        for index, broker_id in enumerate(attempts):
            try:
                adapter = self._adapter_or_raise(broker_id)
                quotes = await adapter.get_quote_snapshots(symbols)
                return [
                    self._mark_quote(
                        quote,
                        broker_id,
                        fallback_from=fallback_from,
                        fallback_reason=fallback_reason,
                    )
                    for quote in quotes
                ]
            except NotImplementedError as exc:
                last_error = (broker_id, exc)
            except Exception as exc:
                last_error = (broker_id, exc)
            if index == 0:
                fallback_from = broker_id
                fallback_reason = str(last_error[1]) if last_error else None

        self._raise_market_data_error(last_error)

    async def get_instrument_profile(
        self,
        broker: str,
        symbol: str,
        fallback: bool = False,
    ) -> InstrumentProfile:
        attempts = self._build_attempts(broker, fallback)
        last_error: tuple[BrokerId, Exception] | None = None
        fallback_from: BrokerId | None = None
        fallback_reason: str | None = None

        for index, broker_id in enumerate(attempts):
            try:
                adapter = self._adapter_or_raise(broker_id)
                profile = await adapter.get_instrument_profile(symbol)
                return self._mark_profile(
                    profile,
                    broker_id,
                    fallback_from=fallback_from,
                    fallback_reason=fallback_reason,
                )
            except NotImplementedError as exc:
                last_error = (broker_id, exc)
            except Exception as exc:
                last_error = (broker_id, exc)
            if index == 0:
                fallback_from = broker_id
                fallback_reason = str(last_error[1]) if last_error else None

        self._raise_market_data_error(last_error)

    def _build_attempts(self, broker: str, fallback: bool) -> list[BrokerId]:
        if broker == "auto":
            return [broker_id for broker_id in self.preferred_order if broker_id in self.adapters]

        try:
            primary = BrokerId(broker)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="broker must be one of tiger, longbridge, futu, or auto",
            ) from exc

        if not fallback:
            return [primary]

        attempts = [primary]
        attempts.extend(broker_id for broker_id in self.preferred_order if broker_id != primary)
        return attempts

    def _adapter_or_raise(self, broker: BrokerId) -> BrokerAdapter:
        adapter = self.adapters.get(broker)
        if adapter is None:
            raise NotImplementedError("Broker adapter not available")
        return adapter

    @staticmethod
    def _mark_quote(
        quote: QuoteSnapshot,
        source_broker: BrokerId,
        fallback_from: BrokerId | None,
        fallback_reason: str | None,
    ) -> QuoteSnapshot:
        update: dict[str, object] = {"source_broker": source_broker}
        if fallback_from is not None:
            update["fallback_from"] = fallback_from
            update["fallback_reason"] = fallback_reason
        return quote.model_copy(update=update)

    @staticmethod
    def _mark_profile(
        profile: InstrumentProfile,
        source_broker: BrokerId,
        fallback_from: BrokerId | None,
        fallback_reason: str | None,
    ) -> InstrumentProfile:
        update: dict[str, object] = {"source_broker": source_broker}
        if fallback_from is not None:
            update["fallback_from"] = fallback_from
            update["fallback_reason"] = fallback_reason
        return profile.model_copy(update=update)

    @staticmethod
    def _raise_market_data_error(last_error: tuple[BrokerId, Exception] | None) -> None:
        if last_error is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")

        broker, exc = last_error
        if isinstance(exc, NotImplementedError):
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Broker market data request failed", "broker": broker, "error": str(exc)},
        ) from exc


tiger_adapter: BrokerAdapter = TigerOpenApiAdapter() if settings.tiger_enabled else TigerPaperAdapter()
longbridge_adapter: BrokerAdapter = (
    LongbridgeOpenApiAdapter() if settings.longbridge_enabled else LongbridgePaperAdapter()
)

workflow = OrderWorkflow(
    store=store,
    adapters={
        BrokerId.tiger: tiger_adapter,
        BrokerId.longbridge: longbridge_adapter,
    },
    risk_engine=risk_engine,
)
market_data_router = MarketDataRouter(workflow.adapters)
