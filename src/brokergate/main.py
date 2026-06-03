import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException, status

from brokergate.config import settings
from brokergate.models import (
    AccountSummary,
    AuditEvent,
    BrokerId,
    ConfirmOrderRequest,
    OrderDraft,
    Position,
    TradeOrderRequest,
)
from brokergate.services import workflow
from brokergate.storage import store

app = FastAPI(
    title="BrokerGate API",
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
async def brokers() -> dict[str, list[dict[str, object]]]:
    return {
        "brokers": [
            await broker_status(BrokerId.tiger, settings.tiger_account),
            {"id": BrokerId.futu, "status": "planned", "registered": False, "connected": False},
            await broker_status(BrokerId.longbridge, settings.longbridge_account),
        ]
    }


async def broker_status(broker: BrokerId, account_id: str) -> dict[str, object]:
    adapter = workflow.adapters.get(broker)
    if adapter is None:
        return {"id": broker, "status": "planned", "registered": False, "connected": False}

    adapter_name = adapter.__class__.__name__
    is_local_paper = adapter_name.endswith("PaperAdapter")
    try:
        connected = await asyncio.wait_for(
            asyncio.to_thread(lambda: asyncio.run(adapter.test_connection(account_id))),
            timeout=5,
        )
        error = None
    except TimeoutError:
        connected = False
        error = "connection test timed out"
    except Exception as exc:
        connected = False
        error = str(exc)

    if connected and is_local_paper:
        status_value = "local-paper-ready"
    elif connected and settings.broker_mode == "paper":
        status_value = "broker-paper-ready"
    elif connected and settings.broker_mode == "live-trade":
        status_value = "trade-ready"
    elif connected:
        status_value = "query-ready"
    else:
        status_value = "connection-failed"

    result: dict[str, object] = {
        "id": broker,
        "status": status_value,
        "registered": True,
        "connected": connected,
        "adapter": adapter_name,
        "broker_mode": settings.broker_mode,
    }
    if error:
        result["error"] = error
    return result


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
