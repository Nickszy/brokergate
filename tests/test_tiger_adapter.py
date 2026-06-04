from unittest.mock import MagicMock, patch
import pytest
from decimal import Decimal
from brokergate.adapters.tiger import TigerOpenApiAdapter
from brokergate.models import (
    AccountSummary,
    CancelOrderRequest,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderSide,
    OrderStatus,
    OrderType,
    ReplaceOrderRequest,
    TradeOrderRequest,
)


@patch("tigeropen.trade.trade_client.TradeClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_get_account_summary(mock_config_cls, mock_client_cls):
    mock_segment = MagicMock()
    mock_segment.cash_balance = 12345.67
    mock_segment.buying_power = 98765.43

    mock_assets = MagicMock()
    mock_assets.segments = {"S": mock_segment}

    mock_client = mock_client_cls.return_value
    mock_client.get_prime_assets.return_value = mock_assets

    adapter = TigerOpenApiAdapter()
    summary = await adapter.get_account_summary("U12345")

    assert summary.cash == Decimal("12345.67")
    assert summary.buying_power == Decimal("98765.43")
    assert summary.account_id == "U12345"
    assert summary.broker == "tiger"


@patch("tigeropen.trade.trade_client.TradeClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_list_positions(mock_config_cls, mock_client_cls):
    mock_contract = MagicMock()
    mock_contract.symbol = "AAPL"
    mock_contract.name = "Apple Inc."
    mock_contract.currency = "USD"

    mock_pos = MagicMock()
    mock_pos.contract = mock_contract
    mock_pos.quantity = 15.0
    mock_pos.market_value = 2250.0
    mock_pos.average_cost = 145.0

    mock_client = mock_client_cls.return_value
    mock_client.get_positions.return_value = [mock_pos]

    adapter = TigerOpenApiAdapter()
    positions = await adapter.list_positions("U12345")

    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "AAPL"
    assert pos.name == "Apple Inc."
    assert pos.quantity == Decimal("15")
    assert pos.market_value == Decimal("2250")
    assert pos.cost_basis == Decimal("145")
    assert pos.currency == "USD"


@patch("tigeropen.trade.trade_client.TradeClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_submit_order(mock_config_cls, mock_client_cls):
    req = TradeOrderRequest(
        broker="tiger",
        account_id="U12345",
        symbol="AAPL",
        side=OrderSide.buy,
        order_type=OrderType.limit,
        quantity=Decimal("10"),
        limit_price=Decimal("150.0"),
    )
    draft = OrderDraft(
        request=req,
        status=OrderStatus.confirmed
    )

    mock_client = mock_client_cls.return_value
    mock_config_cls.return_value.account = "U12345"

    def mock_place_order(order):
        order.id = 998877
    mock_client.place_order.side_effect = mock_place_order

    adapter = TigerOpenApiAdapter()

    with patch("tigeropen.common.util.contract_utils.stock_contract") as mock_stock_contract, \
         patch("tigeropen.common.util.order_utils.limit_order") as mock_limit_order, \
         patch("brokergate.config.settings.broker_mode", "live-trade"), \
         patch("brokergate.config.settings.tiger_account", "U12345"):

        mock_contract_obj = MagicMock()
        mock_stock_contract.return_value = mock_contract_obj

        mock_order_obj = MagicMock()
        mock_order_obj.id = None
        mock_limit_order.return_value = mock_order_obj

        receipt = await adapter.submit_order(draft)

        assert receipt.broker_order_id == "998877"
        assert receipt.status == OrderStatus.submitted

        mock_stock_contract.assert_called_once_with(symbol="AAPL", currency="USD", exchange="SMART")
        mock_limit_order.assert_called_once_with(
            account=draft.request.account_id,
            contract=mock_contract_obj,
            action="BUY",
            quantity=10,
            limit_price=150.0
        )


@patch("tigeropen.trade.trade_client.TradeClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_preview_and_max_quantity_use_sdk(mock_config_cls, mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_preview = MagicMock()
    mock_preview.commission = 1.23
    mock_client.preview_order.return_value = mock_preview
    mock_client.get_estimate_tradable_quantity.return_value = 99

    req = TradeOrderRequest(
        broker="tiger",
        account_id="U12345",
        symbol="AAPL",
        side=OrderSide.buy,
        order_type=OrderType.limit,
        quantity=Decimal("2"),
        limit_price=Decimal("150"),
    )

    adapter = TigerOpenApiAdapter()
    with patch("tigeropen.common.util.contract_utils.stock_contract"), \
         patch("tigeropen.common.util.order_utils.limit_order") as mock_limit_order:
        mock_limit_order.return_value = MagicMock()
        preview = await adapter.preview_order(
            req,
            AccountSummary(
                broker="tiger",
                account_id="U12345",
                cash=Decimal("100000"),
                buying_power=Decimal("100000"),
            ),
        )
        max_qty = await adapter.get_max_tradable_quantity(
            MaxTradableQuantityRequest(
                broker="tiger",
                account_id="U12345",
                symbol="AAPL",
                side=OrderSide.buy,
                price=Decimal("150"),
            )
        )

    assert preview.broker_preview["source"] == "tiger_openapi"
    assert preview.estimated_fees == Decimal("1.23")
    assert max_qty.max_quantity == Decimal("99")
    assert max_qty.raw["source"] == "tiger_openapi"


@patch("tigeropen.trade.trade_client.TradeClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_replace_and_cancel_use_sdk(mock_config_cls, mock_client_cls):
    mock_order = MagicMock()
    mock_order.id = 123
    mock_order.order_id = 123
    mock_order.account = "U12345"
    mock_order.quantity = 1
    mock_order.filled = 0
    mock_order.limit_price = 100
    mock_order.status.name = "NEW"
    mock_order.contract.symbol = "AAPL"
    mock_order.contract.currency = "USD"

    mock_client = mock_client_cls.return_value
    mock_client.get_order.return_value = mock_order

    adapter = TigerOpenApiAdapter()
    replaced = await adapter.replace_order(
        "U12345",
        "123",
        ReplaceOrderRequest(
            quantity=Decimal("2"),
            limit_price=Decimal("101"),
            confirmation_text="CONFIRM REPLACE 2 AAPL 101",
            confirmed_by="tester",
        ),
    )
    cancelled = await adapter.cancel_order(
        "U12345",
        "123",
        CancelOrderRequest(confirmed_by="tester"),
    )

    assert replaced.broker_order_id == "123"
    assert cancelled.broker_order_id == "123"
    mock_client.modify_order.assert_called_once()
    mock_client.cancel_order.assert_called_once_with(account="U12345", id=123)


@patch("tigeropen.quote.quote_client.QuoteClient")
@patch("tigeropen.tiger_open_config.TigerOpenClientConfig")
@pytest.mark.anyio
async def test_tiger_adapter_quote_snapshots_use_sdk(mock_config_cls, mock_quote_cls):
    quote = MagicMock()
    quote.symbol = "AAPL"
    quote.currency = "USD"
    quote.latest_price = 190.5
    quote.bid_price = 190.4
    quote.ask_price = 190.6

    mock_quote_cls.return_value.get_briefs.return_value = [quote]

    adapter = TigerOpenApiAdapter()
    snapshots = await adapter.get_quote_snapshots(["AAPL"])

    assert snapshots[0].symbol == "AAPL"
    assert snapshots[0].last_price == Decimal("190.5")
    mock_quote_cls.return_value.get_briefs.assert_called_once_with(["AAPL"], include_ask_bid=True)
