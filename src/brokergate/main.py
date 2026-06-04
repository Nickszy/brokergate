import asyncio
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from brokergate.config import settings
from brokergate.models import (
    AccountSummary,
    AuditEvent,
    BrokerId,
    BrokerOrder,
    BrokerOrderStatus,
    CancelOrderRequest,
    ConfirmOrderRequest,
    ExecutionQueryFilters,
    InstrumentProfile,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderExecution,
    OrderFee,
    OrderPreview,
    OrderQueryFilters,
    Position,
    QuoteSnapshot,
    ReplaceOrderRequest,
    TradeOrderRequest,
)
from brokergate.services import market_data_router, workflow
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


def unsupported_error(exc: NotImplementedError) -> HTTPException:
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


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


@app.post("/v1/orders/preview", dependencies=[Depends(require_api_key)])
async def preview_order(request: TradeOrderRequest) -> OrderPreview:
    return await workflow.preview_order(request)


@app.post("/v1/orders/max-tradable-quantity", dependencies=[Depends(require_api_key)])
async def max_tradable_quantity(request: MaxTradableQuantityRequest):
    return await workflow.get_max_tradable_quantity(request)


@app.post("/v1/orders/{draft_id}/confirm", dependencies=[Depends(require_api_key)])
async def confirm_order(draft_id: str, confirmation: ConfirmOrderRequest):
    return await workflow.confirm_and_submit(draft_id, confirmation)


@app.get("/v1/audit/events", dependencies=[Depends(require_api_key)])
async def audit_events() -> list[AuditEvent]:
    return store.audit_events


@app.get("/v1/accounts/{account_id}/summary", dependencies=[Depends(require_api_key)])
async def get_account_summary(account_id: str, broker: BrokerId = BrokerId.tiger) -> AccountSummary:
    adapter = workflow.get_adapter(broker)
    return await adapter.get_account_summary(account_id)


@app.get("/v1/accounts/{account_id}/positions", dependencies=[Depends(require_api_key)])
async def list_positions(account_id: str, broker: BrokerId = BrokerId.tiger) -> list[Position]:
    adapter = workflow.get_adapter(broker)
    return await adapter.list_positions(account_id)


@app.get("/v1/accounts/{account_id}/orders", dependencies=[Depends(require_api_key)])
async def list_orders(
    account_id: str,
    broker: BrokerId = BrokerId.tiger,
    symbol: str | None = None,
    order_status: BrokerOrderStatus | None = Query(default=None, alias="status"),
) -> dict[str, list[BrokerOrder]]:
    adapter = workflow.get_adapter(broker)
    filters = OrderQueryFilters(symbol=symbol, status=order_status)
    try:
        orders = await adapter.list_orders(account_id, filters=filters)
    except NotImplementedError as exc:
        raise unsupported_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Broker order list failed",
                "broker": broker,
                "account_id": account_id,
                "error": str(exc),
            },
        ) from exc
    return {"orders": orders}


@app.post(
    "/v1/accounts/{account_id}/orders/{broker_order_id}/sync",
    dependencies=[Depends(require_api_key)],
)
async def sync_order_status(
    account_id: str,
    broker_order_id: str,
    broker: BrokerId = BrokerId.tiger,
) -> BrokerOrder:
    return await workflow.sync_order_status(
        broker=broker,
        account_id=account_id,
        broker_order_id=broker_order_id,
        actor="api-key",
    )


@app.post(
    "/v1/accounts/{account_id}/orders/{broker_order_id}/replace",
    dependencies=[Depends(require_api_key)],
)
async def replace_order(
    account_id: str,
    broker_order_id: str,
    request: ReplaceOrderRequest,
    broker: BrokerId = BrokerId.tiger,
) -> BrokerOrder:
    return await workflow.replace_order(broker, account_id, broker_order_id, request)


@app.post(
    "/v1/accounts/{account_id}/orders/{broker_order_id}/cancel",
    dependencies=[Depends(require_api_key)],
)
async def cancel_order(
    account_id: str,
    broker_order_id: str,
    request: CancelOrderRequest,
    broker: BrokerId = BrokerId.tiger,
) -> BrokerOrder:
    return await workflow.cancel_order(broker, account_id, broker_order_id, request)


@app.get(
    "/v1/accounts/{account_id}/orders/{broker_order_id}/fees",
    dependencies=[Depends(require_api_key)],
)
async def get_order_fees(
    account_id: str,
    broker_order_id: str,
    broker: BrokerId = BrokerId.tiger,
) -> OrderFee:
    adapter = workflow.get_adapter(broker)
    try:
        return await adapter.get_order_fees(account_id, broker_order_id)
    except NotImplementedError as exc:
        raise unsupported_error(exc) from exc


@app.get(
    "/v1/accounts/{account_id}/executions/today",
    dependencies=[Depends(require_api_key)],
)
async def list_today_executions(
    account_id: str,
    broker: BrokerId = BrokerId.tiger,
    symbol: str | None = None,
) -> dict[str, list[OrderExecution]]:
    adapter = workflow.get_adapter(broker)
    try:
        executions = await adapter.list_today_executions(
            account_id,
            filters=ExecutionQueryFilters(symbol=symbol),
        )
    except NotImplementedError as exc:
        raise unsupported_error(exc) from exc
    return {"executions": executions}


@app.get(
    "/v1/accounts/{account_id}/executions/history",
    dependencies=[Depends(require_api_key)],
)
async def list_history_executions(
    account_id: str,
    broker: BrokerId = BrokerId.tiger,
    symbol: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, list[OrderExecution]]:
    adapter = workflow.get_adapter(broker)
    try:
        executions = await adapter.list_history_executions(
            account_id,
            filters=ExecutionQueryFilters(symbol=symbol, date_from=date_from, date_to=date_to),
        )
    except NotImplementedError as exc:
        raise unsupported_error(exc) from exc
    return {"executions": executions}


@app.get("/v1/market/quotes", dependencies=[Depends(require_api_key)])
async def get_quote_snapshots(
    symbols: str,
    broker: str = "tiger",
    fallback: bool = False,
) -> dict[str, list[QuoteSnapshot]]:
    symbol_list = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    quotes = await market_data_router.get_quote_snapshots(
        broker=broker,
        symbols=symbol_list,
        fallback=fallback,
    )
    return {"quotes": quotes}


@app.get("/v1/market/instruments/{symbol}", dependencies=[Depends(require_api_key)])
async def get_instrument_profile(
    symbol: str,
    broker: str = "tiger",
    fallback: bool = False,
) -> InstrumentProfile:
    return await market_data_router.get_instrument_profile(
        broker=broker,
        symbol=symbol,
        fallback=fallback,
    )
