from abc import ABC, abstractmethod

from brokergate.models import (
    AccountSummary,
    BrokerId,
    BrokerOrder,
    BrokerOrderReceipt,
    CancelOrderRequest,
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
    TradableQuantity,
    TradeOrderRequest,
)


class BrokerAdapter(ABC):
    broker_id: BrokerId

    @abstractmethod
    async def test_connection(self, account_id: str) -> bool:
        """Test the connection to the broker."""

    @abstractmethod
    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        """Return the broker account snapshot used by query APIs and risk checks."""

    @abstractmethod
    async def list_positions(self, account_id: str) -> list[Position]:
        """List open positions for the account."""

    @abstractmethod
    async def list_orders(
        self,
        account_id: str,
        filters: OrderQueryFilters | None = None,
    ) -> list[BrokerOrder]:
        """List orders for the account."""

    async def get_order(self, account_id: str, broker_order_id: str) -> BrokerOrder:
        orders = await self.list_orders(account_id)
        for order in orders:
            if order.broker_order_id == broker_order_id:
                return order
        raise KeyError(f"Order {broker_order_id} not found")

    async def preview_order(
        self,
        request: TradeOrderRequest,
        account_summary: AccountSummary,
    ) -> OrderPreview:
        raise NotImplementedError("Order preview is not supported by this broker adapter")

    async def get_max_tradable_quantity(
        self,
        request: MaxTradableQuantityRequest,
    ) -> TradableQuantity:
        raise NotImplementedError("Max tradable quantity is not supported by this broker adapter")

    @abstractmethod
    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        """Submit a confirmed order draft to the broker."""

    async def replace_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: ReplaceOrderRequest,
    ) -> BrokerOrder:
        raise NotImplementedError("Replace order is not supported by this broker adapter")

    async def cancel_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: CancelOrderRequest,
    ) -> BrokerOrder:
        raise NotImplementedError("Cancel order is not supported by this broker adapter")

    async def get_order_fees(self, account_id: str, broker_order_id: str) -> OrderFee:
        raise NotImplementedError("Order fees are not supported by this broker adapter")

    async def list_today_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters | None = None,
    ) -> list[OrderExecution]:
        raise NotImplementedError("Today executions are not supported by this broker adapter")

    async def list_history_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters,
    ) -> list[OrderExecution]:
        raise NotImplementedError("History executions are not supported by this broker adapter")

    async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
        raise NotImplementedError("Quote snapshots are not supported by this broker adapter")

    async def get_instrument_profile(self, symbol: str) -> InstrumentProfile:
        raise NotImplementedError("Instrument profile is not supported by this broker adapter")
