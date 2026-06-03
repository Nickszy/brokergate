from unittest.mock import MagicMock, patch
import pytest
from decimal import Decimal
from openbroker.adapters.tiger import TigerOpenApiAdapter
from openbroker.models import OrderDraft, TradeOrderRequest, OrderSide, OrderType, OrderStatus


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

    def mock_place_order(order):
        order.id = 998877
    mock_client.place_order.side_effect = mock_place_order

    adapter = TigerOpenApiAdapter()

    with patch("tigeropen.common.util.contract_utils.stock_contract") as mock_stock_contract, \
         patch("tigeropen.common.util.order_utils.limit_order") as mock_limit_order:

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
            account=mock_config_cls.return_value.account,
            contract=mock_contract_obj,
            action="BUY",
            quantity=10,
            limit_price=150.0
        )
