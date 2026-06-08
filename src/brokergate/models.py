from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class BrokerId(StrEnum):
    tiger = "tiger"
    futu = "futu"
    longbridge = "longbridge"


class OrderSide(StrEnum):
    buy = "buy"
    sell = "sell"


class OrderType(StrEnum):
    market = "market"
    limit = "limit"


class TimeInForce(StrEnum):
    day = "day"
    gtc = "gtc"  # good til canceled
    gtd = "gtd"  # good til date (requires expire_date)


class OutsideRth(StrEnum):
    rth_only = "rth_only"  # regular trading hours only
    any_time = "any_time"  # pre/post market included
    overnight = "overnight"


class OrderStatus(StrEnum):
    draft = "draft"
    confirmed = "confirmed"
    submitted = "submitted"
    rejected = "rejected"


class BrokerOrderStatus(StrEnum):
    unknown = "unknown"
    submitted = "submitted"
    partially_filled = "partially_filled"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"
    expired = "expired"


class RiskCheckStatus(StrEnum):
    passed = "passed"
    blocked = "blocked"


class AccountSummary(BaseModel):
    broker: BrokerId
    account_id: str
    base_currency: str = "USD"
    cash: Decimal = Field(ge=0)
    buying_power: Decimal = Field(ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)


class RiskCheckResult(BaseModel):
    rule_id: str
    status: RiskCheckStatus
    reason: str
    required_amount: Decimal | None = None
    available_buying_power: Decimal | None = None
    currency: str | None = None


class TradeOrderRequest(BaseModel):
    broker: BrokerId
    account_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1, examples=["AAPL"])
    side: OrderSide
    order_type: OrderType = OrderType.limit
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    client_memo: str | None = Field(default=None, max_length=500)
    time_in_force: TimeInForce = TimeInForce.day
    expire_date: date | None = None  # required when time_in_force is gtd
    trigger_price: Decimal | None = Field(default=None, gt=0)  # stop/trigger (LIT/MIT)
    trailing_amount: Decimal | None = Field(default=None, gt=0)  # trailing stop by amount
    trailing_percent: Decimal | None = Field(default=None, gt=0)  # trailing stop by percent
    outside_rth: OutsideRth | None = None  # US pre/post/overnight session


class OrderQueryFilters(BaseModel):
    symbol: str | None = None
    status: BrokerOrderStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ExecutionQueryFilters(BaseModel):
    symbol: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class MaxTradableQuantityRequest(BaseModel):
    broker: BrokerId
    account_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: OrderSide
    price: Decimal | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ReplaceOrderRequest(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    confirmation_text: str = Field(min_length=1)
    confirmed_by: str = Field(min_length=1)


class CancelOrderRequest(BaseModel):
    confirmed_by: str = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=500)


class OrderDraft(BaseModel):
    id: str = Field(default_factory=lambda: f"draft_{uuid4().hex}")
    request: TradeOrderRequest
    status: OrderStatus = OrderStatus.draft
    risk_warnings: list[str] = Field(default_factory=list)
    risk_checks: list[RiskCheckResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConfirmOrderRequest(BaseModel):
    confirmation_text: str = Field(min_length=1)
    confirmed_by: str = Field(min_length=1)


class BrokerOrderReceipt(BaseModel):
    broker: BrokerId
    broker_order_id: str
    status: OrderStatus
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)


class BrokerOrder(BaseModel):
    broker: BrokerId
    account_id: str
    broker_order_id: str
    symbol: str = ""
    side: OrderSide = OrderSide.buy
    order_type: OrderType = OrderType.limit
    quantity: Decimal = Decimal("0")
    filled_quantity: Decimal = Decimal("0")
    limit_price: Decimal | None = None
    average_fill_price: Decimal | None = None
    status: BrokerOrderStatus = BrokerOrderStatus.unknown
    currency: str = "USD"
    submitted_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderPreview(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal | None = None
    estimated_amount: Decimal | None = None
    estimated_fees: Decimal | None = None
    max_tradable_quantity: Decimal | None = None
    risk_checks: list[RiskCheckResult] = Field(default_factory=list)
    broker_preview: dict[str, Any] = Field(default_factory=dict)


class TradableQuantity(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    side: OrderSide
    price: Decimal | None = None
    currency: str
    max_quantity: Decimal
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderFee(BaseModel):
    broker: BrokerId
    account_id: str
    broker_order_id: str | None = None
    symbol: str | None = None
    currency: str = "USD"
    total_fee: Decimal | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderExecution(BaseModel):
    broker: BrokerId
    account_id: str
    execution_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    currency: str
    executed_at: datetime
    broker_order_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class QuoteSnapshot(BaseModel):
    broker: BrokerId
    source_broker: BrokerId | None = None
    fallback_from: BrokerId | None = None
    fallback_reason: str | None = None
    symbol: str
    name: str | None = None
    currency: str = "USD"
    last_price: Decimal | None = None
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    previous_close: Decimal | None = None
    timestamp: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class DepthLevel(BaseModel):
    """A single price level in an order book (one side)."""

    price: Decimal | None = None
    volume: Decimal = Decimal("0")
    order_count: int | None = None


class QuoteDepth(BaseModel):
    """Order-book depth (level-2) for a symbol: ranked ask and bid levels.

    ``asks`` are ordered best (lowest) ask first; ``bids`` best (highest) bid
    first. Levels with no price (e.g. markets without depth entitlement) are
    dropped by the adapters, so an empty side means depth is unavailable.
    """

    broker: BrokerId
    source_broker: BrokerId | None = None
    fallback_from: BrokerId | None = None
    fallback_reason: str | None = None
    symbol: str
    currency: str | None = None
    asks: list[DepthLevel] = Field(default_factory=list)
    bids: list[DepthLevel] = Field(default_factory=list)
    timestamp: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class InstrumentProfile(BaseModel):
    broker: BrokerId
    source_broker: BrokerId | None = None
    fallback_from: BrokerId | None = None
    fallback_reason: str | None = None
    symbol: str
    name: str | None = None
    market: str | None = None
    currency: str | None = None
    instrument_type: str | None = None
    lot_size: Decimal | None = None
    tradable: bool | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    actor: str
    action: str
    subject: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiagnosticCategory(StrEnum):
    health_check = "health_check"
    connection_test = "connection_test"
    account_summary = "account_summary"
    positions_query = "positions_query"
    orders_query = "orders_query"
    executions_query = "executions_query"
    market_data = "market_data"


class DiagnosticResult(StrEnum):
    success = "success"
    warning = "warning"
    error = "error"


class DiagnosticEvent(BaseModel):
    """A gateway sync/connection diagnostic record surfaced on the 连接 dashboard."""

    id: str = Field(default_factory=lambda: f"diag_{uuid4().hex}")
    category: DiagnosticCategory
    result: DiagnosticResult
    broker: BrokerId | None = None
    account: str | None = None
    message: str = ""
    duration_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class Position(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    name: str | None = None
    quantity: Decimal
    market_value: Decimal | None = None
    currency: str = "USD"
    cost_basis: Decimal
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
