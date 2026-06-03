from unittest.mock import MagicMock, patch
import pytest
from decimal import Decimal
from openbroker.adapters.longbridge import LongbridgeOpenApiAdapter
from openbroker.models import OrderDraft, TradeOrderRequest, OrderSide, OrderType, OrderStatus


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_get_account_summary(mock_config_cls, mock_ctx_cls):
    mock_bal = MagicMock()
    mock_bal.total_cash = 54321.10
    mock_bal.buy_power = 98765.20
    mock_bal.currency = "USD"

    mock_ctx = mock_ctx_cls.return_value
    mock_ctx.account_balance.return_value = [mock_bal]

    adapter = LongbridgeOpenApiAdapter()
    summary = await adapter.get_account_summary("LB12345")

    assert summary.cash == Decimal("54321.1")
    assert summary.buying_power == Decimal("98765.2")
    assert summary.account_id == "LB12345"
    assert summary.broker == "longbridge"
    assert summary.base_currency == "USD"


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_list_positions(mock_config_cls, mock_ctx_cls):
    mock_pos = MagicMock()
    mock_pos.symbol = "700.HK"
    mock_pos.symbol_name = "Tencent"
    mock_pos.currency = "HKD"
    mock_pos.quantity = 200.0
    mock_pos.cost_price = 350.0

    mock_channel = MagicMock()
    mock_channel.positions = [mock_pos]

    mock_resp = MagicMock()
    mock_resp.channels = [mock_channel]

    mock_ctx = mock_ctx_cls.return_value
    mock_ctx.stock_positions.return_value = mock_resp

    adapter = LongbridgeOpenApiAdapter()
    positions = await adapter.list_positions("LB12345")

    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "700.HK"
    assert pos.name == "Tencent"
    assert pos.quantity == Decimal("200")
    assert pos.market_value == Decimal("70000")
    assert pos.cost_basis == Decimal("350")
    assert pos.currency == "HKD"


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_list_orders(mock_config_cls, mock_ctx_cls):
    mock_order = MagicMock()
    mock_order.order_id = "lb-order-123"
    mock_order.status.name = "Filled"

    mock_ctx = mock_ctx_cls.return_value
    mock_ctx.today_orders.return_value = [mock_order]

    adapter = LongbridgeOpenApiAdapter()

    with patch("openbroker.config.settings.longbridge_account", "LB12345"):
        orders = await adapter.list_orders("LB12345")
        assert len(orders) == 1
        assert orders[0].broker_order_id == "lb-order-123"

        orders_other = await adapter.list_orders("OTHER")
        assert len(orders_other) == 0


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_submit_order(mock_config_cls, mock_ctx_cls):
    req = TradeOrderRequest(
        broker="longbridge",
        account_id="LB12345",
        symbol="700.HK",
        side=OrderSide.buy,
        order_type=OrderType.limit,
        quantity=Decimal("100"),
        limit_price=Decimal("350.0"),
    )
    draft = OrderDraft(
        request=req,
        status=OrderStatus.confirmed
    )

    mock_resp = MagicMock()
    mock_resp.order_id = "lb-order-submitted-99"

    mock_ctx = mock_ctx_cls.return_value
    mock_ctx.submit_order.return_value = mock_resp

    adapter = LongbridgeOpenApiAdapter()

    from longbridge.openapi import OrderType as LBOrderType, OrderSide as LBOrderSide, TimeInForceType

    with patch("openbroker.config.settings.broker_mode", "live-trade"), \
         patch("openbroker.config.settings.longbridge_account", "LB12345"):

        receipt = await adapter.submit_order(draft)

        assert receipt.broker_order_id == "lb-order-submitted-99"
        assert receipt.status == OrderStatus.submitted

        mock_ctx.submit_order.assert_called_once_with(
            symbol="700.HK",
            order_type=LBOrderType.LO,
            side=LBOrderSide.Buy,
            quantity=Decimal("100"),
            time_in_force=TimeInForceType.Day,
            submitted_price=Decimal("350.0"),
            remark="OpenBroker Trade"
        )
