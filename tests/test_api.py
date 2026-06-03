import os
os.environ["OPENBROKER_TIGER_ENABLED"] = "false"

from fastapi.testclient import TestClient

from openbroker.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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

