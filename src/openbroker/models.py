from datetime import UTC, datetime
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


class OrderStatus(StrEnum):
    draft = "draft"
    confirmed = "confirmed"
    submitted = "submitted"
    rejected = "rejected"


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

class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    actor: str
    action: str
    subject: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class Position(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    name: str | None = None
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"
    cost_basis: Decimal
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

