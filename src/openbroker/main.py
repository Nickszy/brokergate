from fastapi import Depends, FastAPI, Header, HTTPException, status

from openbroker.config import settings
from openbroker.models import (
    AccountSummary,
    AuditEvent,
    BrokerId,
    ConfirmOrderRequest,
    OrderDraft,
    Position,
    TradeOrderRequest,
)
from openbroker.services import workflow
from openbroker.storage import store

app = FastAPI(
    title="OpenBroker API",
    summary="Self-hosted multi-broker trading gateway with human-confirmed execution.",
    version="0.1.0",
)


def require_api_key(x_api_key: str = Header(default="")) -> str:
    if settings.api_key != "change-me" and x_api_key != settings.api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return "api-key"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env, "broker_mode": settings.broker_mode}


@app.get("/v1/brokers", dependencies=[Depends(require_api_key)])
async def brokers() -> dict[str, list[dict[str, str]]]:
    return {
        "brokers": [
            {"id": BrokerId.tiger, "status": "paper-ready"},
            {"id": BrokerId.futu, "status": "planned"},
            {"id": BrokerId.longbridge, "status": "planned"},
        ]
    }


@app.post("/v1/orders/drafts", dependencies=[Depends(require_api_key)])
async def create_order_draft(request: TradeOrderRequest) -> dict[str, str | OrderDraft]:
    draft = await workflow.create_draft(request, actor="api-key")
    return {
        "draft": draft,
        "required_confirmation": workflow.expected_confirmation(draft),
    }


@app.post("/v1/orders/{draft_id}/confirm", dependencies=[Depends(require_api_key)])
async def confirm_order(draft_id: str, confirmation: ConfirmOrderRequest):
    return await workflow.confirm_and_submit(draft_id, confirmation)


@app.get("/v1/audit/events", dependencies=[Depends(require_api_key)])
async def audit_events() -> list[AuditEvent]:
    return store.audit_events


@app.get("/v1/accounts/{account_id}/summary", dependencies=[Depends(require_api_key)])
async def get_account_summary(account_id: str, broker: BrokerId = BrokerId.tiger) -> AccountSummary:
    adapter = workflow.adapters.get(broker)
    if not adapter:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")
    return await adapter.get_account_summary(account_id)


@app.get("/v1/accounts/{account_id}/positions", dependencies=[Depends(require_api_key)])
async def list_positions(account_id: str, broker: BrokerId = BrokerId.tiger) -> list[Position]:
    adapter = workflow.adapters.get(broker)
    if not adapter:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Broker adapter not available")
    return await adapter.list_positions(account_id)

