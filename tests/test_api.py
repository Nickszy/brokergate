import os
os.environ["BROKERGATE_TIGER_ENABLED"] = "false"
os.environ["BROKERGATE_LONGBRIDGE_ENABLED"] = "false"

from decimal import Decimal

from fastapi.testclient import TestClient

from brokergate.main import app
from brokergate.models import (
    AccountSummary,
    BrokerId,
    BrokerOrder,
    BrokerOrderStatus,
    InstrumentProfile,
    OrderSide,
    OrderType,
    QuoteSnapshot,
)
from brokergate.services import workflow


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_brokers_returns_dynamic_registration_status() -> None:
    response = client.get("/v1/brokers")
    assert response.status_code == 200
    brokers = {item["id"]: item for item in response.json()["brokers"]}

    assert brokers["tiger"]["registered"] is True
    assert brokers["tiger"]["connected"] is True
    assert brokers["tiger"]["status"] == "local-paper-ready"
    assert brokers["longbridge"]["registered"] is True
    assert brokers["longbridge"]["connected"] is True
    assert brokers["longbridge"]["status"] == "local-paper-ready"
    assert brokers["futu"]["registered"] is False
    assert brokers["futu"]["status"] == "planned"


def test_create_and_confirm_order_draft() -> None:
    draft_response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": "1",
            "limit_price": "100",
        },
    )

    assert draft_response.status_code == 200
    payload = draft_response.json()
    draft_id = payload["draft"]["id"]

    confirm_response = client.post(
        f"/v1/orders/{draft_id}/confirm",
        json={"confirmation_text": payload["required_confirmation"], "confirmed_by": "tester"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "submitted"


def test_blocks_buy_order_above_buying_power() -> None:
    response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": "100000",
            "limit_price": "100",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Order blocked by risk engine"


def test_get_account_summary() -> None:
    response = client.get("/v1/accounts/paper-account/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "paper-account"
    assert data["broker"] == "tiger"
    assert data["cash"] == "100000"
    assert data["buying_power"] == "100000"


def test_list_positions() -> None:
    response = client.get("/v1/accounts/paper-account/positions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    pos = data[0]
    assert pos["symbol"] == "AAPL"
    assert pos["quantity"] == "10"
    assert pos["market_value"] == "1500"
    assert pos["cost_basis"] == "140"


def test_blocks_currency_mismatch() -> None:
    response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": "10",
            "limit_price": "100",
            "currency": "HKD",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Order blocked by risk engine"
    checks = response.json()["detail"]["risk_checks"]
    currency_check = next(c for c in checks if c["rule_id"] == "currency_mismatch")
    assert currency_check["status"] == "blocked"


def test_blocks_fractional_quantity() -> None:
    response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": "10.5",
            "limit_price": "100",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Order blocked by risk engine"
    checks = response.json()["detail"]["risk_checks"]
    qty_check = next(c for c in checks if c["rule_id"] == "fractional_quantity_limit")
    assert qty_check["status"] == "blocked"


def test_blocks_symbol_currency_mismatch() -> None:
    response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "700.HK",
            "side": "buy",
            "order_type": "limit",
            "quantity": "10",
            "limit_price": "100",
            "currency": "USD",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Order blocked by risk engine"
    checks = response.json()["detail"]["risk_checks"]
    sym_currency_check = next(c for c in checks if c["rule_id"] == "symbol_currency_mismatch")
    assert sym_currency_check["status"] == "blocked"


def test_longbridge_create_and_confirm_order_draft() -> None:
    draft_response = client.post(
        "/v1/orders/drafts",
        json={
            "broker": "longbridge",
            "account_id": "paper-longbridge-account",
            "symbol": "700.HK",
            "side": "buy",
            "order_type": "limit",
            "quantity": "100",
            "limit_price": "350",
            "currency": "HKD",
        },
    )

    assert draft_response.status_code == 200
    payload = draft_response.json()
    draft_id = payload["draft"]["id"]

    confirm_response = client.post(
        f"/v1/orders/{draft_id}/confirm",
        json={"confirmation_text": payload["required_confirmation"], "confirmed_by": "tester"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "submitted"


def test_longbridge_get_account_summary() -> None:
    response = client.get("/v1/accounts/paper-longbridge-account/summary?broker=longbridge")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "paper-longbridge-account"
    assert data["broker"] == "longbridge"
    assert data["cash"] == "100000"
    assert data["buying_power"] == "100000"


def test_longbridge_list_positions() -> None:
    response = client.get("/v1/accounts/paper-longbridge-account/positions?broker=longbridge")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    pos = data[0]
    assert pos["symbol"] == "700.HK"
    assert pos["quantity"] == "100"
    assert pos["market_value"] is None
    assert pos["cost_basis"] == "380"


def test_order_preview_uses_local_buying_power_estimate() -> None:
    response = client.post(
        "/v1/orders/preview",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": "2",
            "limit_price": "100",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["estimated_amount"] == "200"
    assert data["max_tradable_quantity"] == "1000"
    assert data["broker_preview"]["source"] == "local_estimate"


def test_max_tradable_quantity_uses_local_estimate() -> None:
    response = client.post(
        "/v1/orders/max-tradable-quantity",
        json={
            "broker": "longbridge",
            "account_id": "paper-longbridge-account",
            "symbol": "700.HK",
            "side": "buy",
            "price": "500",
            "currency": "HKD",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["max_quantity"] == "200"
    assert data["raw"]["source"] == "local_estimate"


def test_sell_max_tradable_quantity_uses_position_estimate() -> None:
    response = client.post(
        "/v1/orders/max-tradable-quantity",
        json={
            "broker": "tiger",
            "account_id": "paper-account",
            "symbol": "AAPL",
            "side": "sell",
            "price": "100",
            "currency": "USD",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["max_quantity"] == "10"
    assert data["raw"]["source"] == "local_position_estimate"


def test_list_orders_exposes_unified_order_collection() -> None:
    response = client.get("/v1/accounts/paper-account/orders?broker=tiger")
    assert response.status_code == 200
    assert response.json() == {"orders": []}


def test_unsupported_trade_extensions_return_501() -> None:
    fee_response = client.get("/v1/accounts/paper-account/orders/order-1/fees?broker=tiger")
    quote_response = client.get("/v1/market/quotes?broker=tiger&symbols=AAPL")
    instrument_response = client.get("/v1/market/instruments/AAPL?broker=tiger")

    assert fee_response.status_code == 501
    assert quote_response.status_code == 501
    assert instrument_response.status_code == 501


def test_futu_extensions_do_not_fake_success() -> None:
    response = client.get("/v1/accounts/futu-account/orders?broker=futu")
    assert response.status_code == 501
    assert response.json()["detail"] == "Broker adapter not available"


def test_market_quotes_auto_falls_back_to_longbridge_when_tiger_denies_permission(monkeypatch) -> None:
    class TigerQuoteDeniedAdapter:
        async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
            raise RuntimeError("permission denied(Current user and device do not have permissions in the US market)")

    class LongbridgeQuoteAdapter:
        async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
            return [
                QuoteSnapshot(
                    broker=BrokerId.longbridge,
                    symbol=symbols[0],
                    last_price=Decimal("188.88"),
                )
            ]

    monkeypatch.setitem(workflow.adapters, BrokerId.tiger, TigerQuoteDeniedAdapter())
    monkeypatch.setitem(workflow.adapters, BrokerId.longbridge, LongbridgeQuoteAdapter())

    response = client.get("/v1/market/quotes?broker=auto&symbols=AAPL")

    assert response.status_code == 200
    quote = response.json()["quotes"][0]
    assert quote["broker"] == "longbridge"
    assert quote["source_broker"] == "longbridge"
    assert quote["fallback_from"] == "tiger"
    assert "permission denied" in quote["fallback_reason"]


def test_market_instrument_explicit_broker_can_opt_into_fallback(monkeypatch) -> None:
    class TigerInstrumentTimeoutAdapter:
        async def get_instrument_profile(self, symbol: str) -> InstrumentProfile:
            raise TimeoutError("connect timeout")

    class LongbridgeInstrumentAdapter:
        async def get_instrument_profile(self, symbol: str) -> InstrumentProfile:
            return InstrumentProfile(
                broker=BrokerId.longbridge,
                symbol=symbol,
                name="Apple",
                market="US",
                currency="USD",
            )

    monkeypatch.setitem(workflow.adapters, BrokerId.tiger, TigerInstrumentTimeoutAdapter())
    monkeypatch.setitem(workflow.adapters, BrokerId.longbridge, LongbridgeInstrumentAdapter())

    no_fallback_response = client.get("/v1/market/instruments/AAPL?broker=tiger")
    fallback_response = client.get("/v1/market/instruments/AAPL?broker=tiger&fallback=true")

    assert no_fallback_response.status_code == 502
    assert fallback_response.status_code == 200
    data = fallback_response.json()
    assert data["broker"] == "longbridge"
    assert data["source_broker"] == "longbridge"
    assert data["fallback_from"] == "tiger"
    assert data["fallback_reason"] == "connect timeout"


def test_replace_order_requires_exact_confirmation(monkeypatch) -> None:
    class FakeReplaceAdapter:
        async def get_order(self, account_id: str, broker_order_id: str) -> BrokerOrder:
            return BrokerOrder(
                broker=BrokerId.tiger,
                account_id=account_id,
                broker_order_id=broker_order_id,
                symbol="AAPL",
                side=OrderSide.buy,
                order_type=OrderType.limit,
                quantity=Decimal("1"),
                limit_price=Decimal("100"),
                status=BrokerOrderStatus.submitted,
                currency="USD",
            )

        async def get_account_summary(
            self,
            account_id: str,
            currency: str | None = None,
        ) -> AccountSummary:
            return AccountSummary(
                broker=BrokerId.tiger,
                account_id=account_id,
                cash=Decimal("100000"),
                buying_power=Decimal("100000"),
            )

        async def replace_order(self, *args, **kwargs):
            raise AssertionError("replace_order should not be called when confirmation mismatches")

    monkeypatch.setitem(workflow.adapters, BrokerId.tiger, FakeReplaceAdapter())

    response = client.post(
        "/v1/accounts/paper-account/orders/order-1/replace?broker=tiger",
        json={
            "quantity": "2",
            "limit_price": "101",
            "confirmation_text": "wrong",
            "confirmed_by": "tester",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Replace confirmation text mismatch"
