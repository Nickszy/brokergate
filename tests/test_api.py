import os
os.environ["BROKERGATE_TIGER_ENABLED"] = "false"
os.environ["BROKERGATE_LONGBRIDGE_ENABLED"] = "false"

from fastapi.testclient import TestClient

from brokergate.main import app


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
