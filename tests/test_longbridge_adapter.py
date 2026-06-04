from unittest.mock import MagicMock, patch
import pytest
from decimal import Decimal
from brokergate.adapters.longbridge import LongbridgeOpenApiAdapter
from brokergate.models import (
    CancelOrderRequest,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderSide,
    OrderStatus,
    OrderType,
    ReplaceOrderRequest,
    TradeOrderRequest,
)


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
    with patch("brokergate.config.settings.longbridge_account", "LB12345"):
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
    with patch("brokergate.config.settings.longbridge_account", "LB12345"):
        positions = await adapter.list_positions("LB12345")

    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "700.HK"
    assert pos.name == "Tencent"
    assert pos.quantity == Decimal("200")
    assert pos.market_value is None
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

    with patch("brokergate.config.settings.longbridge_account", "LB12345"):
        orders = await adapter.list_orders("LB12345")
        assert len(orders) == 1
        assert orders[0].broker_order_id == "lb-order-123"

        with pytest.raises(ValueError):
            await adapter.list_orders("OTHER")


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

    with patch("brokergate.config.settings.broker_mode", "live-trade"), \
         patch("brokergate.config.settings.longbridge_account", "LB12345"):

        receipt = await adapter.submit_order(draft)

        assert receipt.broker_order_id == "lb-order-submitted-99"
        assert receipt.status == OrderStatus.submitted

        mock_ctx.submit_order.assert_called_once_with(
            symbol="700.HK",
            order_type=LBOrderType.LO,
            side=LBOrderSide.Buy,
            submitted_quantity=Decimal("100"),
            time_in_force=TimeInForceType.Day,
            submitted_price=Decimal("350.0"),
            remark="BrokerGate Trade"
        )


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_max_quantity_uses_sdk(mock_config_cls, mock_ctx_cls):
    mock_resp = MagicMock()
    mock_resp.cash_max_qty = Decimal("88")
    mock_resp.margin_max_qty = Decimal("99")
    mock_ctx_cls.return_value.estimate_max_purchase_quantity.return_value = mock_resp

    adapter = LongbridgeOpenApiAdapter()
    with patch("brokergate.config.settings.longbridge_account", "LB12345"):
        result = await adapter.get_max_tradable_quantity(
            MaxTradableQuantityRequest(
                broker="longbridge",
                account_id="LB12345",
                symbol="700.HK",
                side=OrderSide.buy,
                price=Decimal("350"),
                currency="HKD",
            )
        )

    assert result.max_quantity == Decimal("88")
    assert result.raw["source"] == "longbridge_openapi"


@patch("longbridge.openapi.TradeContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_replace_and_cancel_use_sdk(mock_config_cls, mock_ctx_cls):
    mock_order = MagicMock()
    mock_order.order_id = "lb-order-123"
    mock_order.symbol = "700.HK"
    mock_order.side.name = "Buy"
    mock_order.status.name = "New"
    mock_order.submitted_quantity = Decimal("100")
    mock_order.executed_quantity = Decimal("0")
    mock_order.submitted_price = Decimal("350")
    mock_order.currency = "HKD"

    mock_ctx = mock_ctx_cls.return_value
    mock_ctx.order_detail.return_value = mock_order

    adapter = LongbridgeOpenApiAdapter()
    with patch("brokergate.config.settings.longbridge_account", "LB12345"):
        replaced = await adapter.replace_order(
            "LB12345",
            "lb-order-123",
            ReplaceOrderRequest(
                quantity=Decimal("100"),
                limit_price=Decimal("351"),
                confirmation_text="CONFIRM REPLACE 100 700.HK 351",
                confirmed_by="tester",
            ),
        )
        cancelled = await adapter.cancel_order(
            "LB12345",
            "lb-order-123",
            CancelOrderRequest(confirmed_by="tester"),
        )

    assert replaced.broker_order_id == "lb-order-123"
    assert cancelled.broker_order_id == "lb-order-123"
    mock_ctx.replace_order.assert_called_once()
    mock_ctx.cancel_order.assert_called_once_with("lb-order-123")


@patch("longbridge.openapi.QuoteContext")
@patch("longbridge.openapi.Config")
@pytest.mark.anyio
async def test_longbridge_adapter_quotes_and_static_info_use_sdk(mock_config_cls, mock_quote_cls):
    quote = MagicMock()
    quote.symbol = "700.HK"
    quote.currency = "HKD"
    quote.last_done = Decimal("350")

    info = MagicMock()
    info.symbol = "700.HK"
    info.name_en = "Tencent"
    info.name_cn = ""
    info.name_hk = ""
    info.exchange = "SEHK"
    info.currency = "HKD"
    info.lot_size = 100

    mock_quote = mock_quote_cls.return_value
    mock_quote.realtime_quote.return_value = [quote]
    mock_quote.static_info.return_value = [info]

    adapter = LongbridgeOpenApiAdapter()
    snapshots = await adapter.get_quote_snapshots(["700.HK"])
    profile = await adapter.get_instrument_profile("700.HK")

    assert snapshots[0].last_price == Decimal("350")
    assert profile.name == "Tencent"
    mock_quote.realtime_quote.assert_called_once_with(["700.HK"])
    mock_quote.static_info.assert_called_once_with(["700.HK"])
