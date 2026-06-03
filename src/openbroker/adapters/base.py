from abc import ABC, abstractmethod

from openbroker.models import AccountSummary, BrokerId, BrokerOrderReceipt, OrderDraft, Position


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
    async def list_orders(self, account_id: str) -> list[BrokerOrderReceipt]:
        """List orders for the account."""

    @abstractmethod
    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        """Submit a confirmed order draft to the broker."""

