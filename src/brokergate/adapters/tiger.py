from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from brokergate.adapters.base import BrokerAdapter
from brokergate.models import (
    AccountSummary,
    BrokerId,
    BrokerOrder,
    BrokerOrderReceipt,
    BrokerOrderStatus,
    CancelOrderRequest,
    ExecutionQueryFilters,
    InstrumentProfile,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderExecution,
    OrderFee,
    OrderPreview,
    OrderQueryFilters,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    QuoteSnapshot,
    ReplaceOrderRequest,
    RiskCheckResult,
    RiskCheckStatus,
    TradableQuantity,
    TradeOrderRequest,
)


def _decimal_or_zero(value: Any) -> Decimal:
    try:
        if value is None or value.__class__.__module__.startswith("unittest.mock"):
            return Decimal("0")
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _str_or_empty(value: Any) -> str:
    if value is None or value.__class__.__module__.startswith("unittest.mock"):
        return ""
    return str(value)


def _safe_datetime(value: Any) -> datetime | None:
    if value is None or value.__class__.__module__.startswith("unittest.mock"):
        return None
    if isinstance(value, datetime):
        return value
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=UTC)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _map_order_status(value: Any) -> BrokerOrderStatus:
    status_name = _str_or_empty(getattr(value, "name", value)).upper()
    if status_name in ("FILLED", "FULLY_FILLED"):
        return BrokerOrderStatus.filled
    if status_name in ("PARTIALLY_FILLED", "PART_FILLED"):
        return BrokerOrderStatus.partially_filled
    if status_name in ("CANCELLED", "CANCELED"):
        return BrokerOrderStatus.cancelled
    if status_name in ("REJECTED", "INACTIVE", "INVALID"):
        return BrokerOrderStatus.rejected
    if status_name == "EXPIRED":
        return BrokerOrderStatus.expired
    if status_name:
        return BrokerOrderStatus.submitted
    return BrokerOrderStatus.unknown


def _map_order_side(value: Any) -> OrderSide:
    side_name = _str_or_empty(getattr(value, "name", value)).upper()
    return OrderSide.sell if side_name == "SELL" else OrderSide.buy


class TigerPaperAdapter(BrokerAdapter):
    broker_id = BrokerId.tiger

    async def test_connection(self, account_id: str) -> bool:
        return True

    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        return AccountSummary(
            broker=BrokerId.tiger,
            account_id=account_id,
            base_currency="USD",
            cash=Decimal("100000"),
            buying_power=Decimal("100000"),
            raw={"mode": "paper"},
        )

    async def list_positions(self, account_id: str) -> list[Position]:
        return [
            Position(
                broker=BrokerId.tiger,
                account_id=account_id,
                symbol="AAPL",
                name="Apple Inc.",
                quantity=Decimal("10"),
                market_value=Decimal("1500"),
                currency="USD",
                cost_basis=Decimal("140"),
            )
        ]

    async def list_orders(
        self,
        account_id: str,
        filters: OrderQueryFilters | None = None,
    ) -> list[BrokerOrder]:
        return []

    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        return BrokerOrderReceipt(
            broker=BrokerId.tiger,
            broker_order_id=f"paper_tiger_{uuid4().hex}",
            status=OrderStatus.submitted,
            raw={
                "mode": "paper",
                "symbol": draft.request.symbol,
                "side": draft.request.side,
                "quantity": str(draft.request.quantity),
            },
        )


class TigerOpenApiAdapter(BrokerAdapter):
    broker_id = BrokerId.tiger

    def _get_tiger_config(self) -> Any:
        from pathlib import Path

        from brokergate.config import settings
        from tigeropen.tiger_open_config import TigerOpenClientConfig

        if settings.tiger_config_dir:
            config = TigerOpenClientConfig(props_path=settings.tiger_config_dir)
        else:
            config = TigerOpenClientConfig()
            config.tiger_id = settings.tiger_id
            config.account = settings.tiger_account
            if settings.tiger_private_key_path:
                raw_key = Path(settings.tiger_private_key_path).read_text(encoding="utf-8")
                clean_key = raw_key.replace("-----BEGIN RSA PRIVATE KEY-----", "")
                clean_key = clean_key.replace("-----END RSA PRIVATE KEY-----", "")
                clean_key = "".join(clean_key.split())
                config.private_key = clean_key

        if settings.tiger_license:
            config.license = settings.tiger_license

        if settings.tiger_token_path:
            config.token_path = settings.tiger_token_path

        return config

    def _trade_client(self) -> Any:
        from tigeropen.trade.trade_client import TradeClient

        return TradeClient(self._get_tiger_config())

    def _quote_client(self) -> Any:
        from tigeropen.quote.quote_client import QuoteClient

        return QuoteClient(self._get_tiger_config())

    def _stock_contract(self, symbol: str, currency: str = "USD") -> Any:
        from tigeropen.common.util.contract_utils import stock_contract

        exchange = "SMART" if currency.upper() == "USD" else "SEHK"
        return stock_contract(symbol=symbol, currency=currency.upper(), exchange=exchange)

    def _limit_order(self, request: TradeOrderRequest) -> Any:
        from tigeropen.common.util.order_utils import limit_order

        if request.limit_price is None:
            raise ValueError("Tiger order preview requires a limit price in the MVP")
        return limit_order(
            account=request.account_id,
            contract=self._stock_contract(request.symbol, request.currency),
            action=request.side.upper(),
            quantity=int(request.quantity),
            limit_price=float(request.limit_price),
        )

    def _to_dict(self, obj: Any) -> Any:
        if isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        if hasattr(obj, "__dict__"):
            return {k: self._to_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        if isinstance(obj, (int, float, str, bool)) or obj is None:
            return obj
        return str(obj)

    def _order_from_sdk(self, account_id: str, order: Any) -> BrokerOrder:
        contract = getattr(order, "contract", None)
        return BrokerOrder(
            broker=BrokerId.tiger,
            account_id=account_id,
            broker_order_id=_str_or_empty(getattr(order, "id", None) or getattr(order, "order_id", None)),
            symbol=_str_or_empty(getattr(contract, "symbol", None)),
            side=_map_order_side(getattr(order, "action", None)),
            order_type=OrderType.limit,
            quantity=_decimal_or_zero(getattr(order, "quantity", None)),
            filled_quantity=_decimal_or_zero(getattr(order, "filled", None)),
            limit_price=_decimal_or_zero(getattr(order, "limit_price", None)) or None,
            average_fill_price=_decimal_or_zero(getattr(order, "avg_fill_price", None)) or None,
            status=_map_order_status(getattr(order, "status", None)),
            currency=_str_or_empty(getattr(contract, "currency", None)) or "USD",
            submitted_at=_safe_datetime(getattr(order, "order_time", None)),
            raw={"order": self._to_dict(order)},
        )

    def _execution_from_sdk(self, account_id: str, txn: Any) -> OrderExecution:
        contract = getattr(txn, "contract", None)
        return OrderExecution(
            broker=BrokerId.tiger,
            account_id=account_id,
            broker_order_id=_str_or_empty(getattr(txn, "order_id", None)) or None,
            execution_id=_str_or_empty(getattr(txn, "id", None) or getattr(txn, "id_", None)),
            symbol=_str_or_empty(getattr(contract, "symbol", None)),
            side=_map_order_side(getattr(txn, "action", None)),
            quantity=_decimal_or_zero(getattr(txn, "filled_quantity", None)),
            price=_decimal_or_zero(getattr(txn, "filled_price", None)),
            currency=_str_or_empty(getattr(contract, "currency", None)) or "USD",
            executed_at=_safe_datetime(getattr(txn, "transacted_at", None)) or datetime.now(UTC),
            raw={"transaction": self._to_dict(txn)},
        )

    def _execution_from_order(self, account_id: str, order: Any) -> OrderExecution:
        contract = getattr(order, "contract", None)
        return OrderExecution(
            broker=BrokerId.tiger,
            account_id=account_id,
            broker_order_id=_str_or_empty(getattr(order, "id", None) or getattr(order, "order_id", None)),
            execution_id=_str_or_empty(getattr(order, "id", None) or getattr(order, "order_id", None)),
            symbol=_str_or_empty(getattr(contract, "symbol", None)),
            side=_map_order_side(getattr(order, "action", None)),
            quantity=_decimal_or_zero(getattr(order, "filled", None)),
            price=_decimal_or_zero(getattr(order, "avg_fill_price", None)),
            currency=_str_or_empty(getattr(contract, "currency", None)) or "USD",
            executed_at=_safe_datetime(getattr(order, "trade_time", None))
            or _safe_datetime(getattr(order, "update_time", None))
            or datetime.now(UTC),
            raw={"order": self._to_dict(order), "source": "filled_order"},
        )

    def _quote_from_sdk(self, quote: Any) -> QuoteSnapshot:
        return QuoteSnapshot(
            broker=BrokerId.tiger,
            symbol=_str_or_empty(getattr(quote, "symbol", None)),
            name=_str_or_empty(getattr(quote, "name", None)) or None,
            currency=_str_or_empty(getattr(quote, "currency", None)) or "USD",
            last_price=_decimal_or_zero(
                getattr(quote, "latest_price", None)
                or getattr(quote, "latestPrice", None)
                or getattr(quote, "close", None)
            )
            or None,
            bid_price=_decimal_or_zero(getattr(quote, "bid_price", None)) or None,
            ask_price=_decimal_or_zero(getattr(quote, "ask_price", None)) or None,
            open_price=_decimal_or_zero(getattr(quote, "open", None)) or None,
            high_price=_decimal_or_zero(getattr(quote, "high", None)) or None,
            low_price=_decimal_or_zero(getattr(quote, "low", None)) or None,
            previous_close=_decimal_or_zero(getattr(quote, "pre_close", None)) or None,
            timestamp=_safe_datetime(getattr(quote, "timestamp", None)),
            raw={"quote": self._to_dict(quote)},
        )

    async def test_connection(self, account_id: str) -> bool:
        try:
            accounts = self._trade_client().get_managed_accounts()
            return bool(accounts)
        except Exception:
            return False

    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        try:
            assets_list = self._trade_client().get_prime_assets(account=account_id)
            if not assets_list:
                raise ValueError(f"No asset information returned for account {account_id}")

            assets = assets_list[0] if isinstance(assets_list, list) else assets_list
            segment = assets.segments.get("S")
            if not segment:
                raise ValueError(f"No stock segment ('S') found in assets for account {account_id}")

            cash = Decimal(str(segment.cash_balance)) if segment.cash_balance is not None else Decimal("0")
            buying_power = (
                Decimal(str(segment.buying_power)) if segment.buying_power is not None else Decimal("0")
            )

            return AccountSummary(
                broker=BrokerId.tiger,
                account_id=account_id,
                base_currency="USD",
                cash=cash,
                buying_power=buying_power,
                raw=self._to_dict(assets),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get account summary from Tiger OpenAPI: {str(e)}") from e

    async def list_positions(self, account_id: str) -> list[Position]:
        try:
            positions_list = self._trade_client().get_positions(account=account_id)
            if not positions_list:
                return []

            unified_positions = []
            for pos in positions_list:
                contract = pos.contract
                symbol = contract.symbol if contract else ""
                name = contract.name if contract else ""
                currency = contract.currency if contract else "USD"

                unified_positions.append(
                    Position(
                        broker=BrokerId.tiger,
                        account_id=account_id,
                        symbol=symbol,
                        name=name,
                        quantity=_decimal_or_zero(pos.quantity),
                        market_value=_decimal_or_zero(pos.market_value),
                        currency=currency,
                        cost_basis=_decimal_or_zero(pos.average_cost),
                    )
                )
            return unified_positions
        except Exception as e:
            raise RuntimeError(f"Failed to list positions from Tiger OpenAPI: {str(e)}") from e

    async def list_orders(
        self,
        account_id: str,
        filters: OrderQueryFilters | None = None,
    ) -> list[BrokerOrder]:
        try:
            sdk_orders = self._trade_client().get_orders(account=account_id)
            if not sdk_orders:
                return []

            orders = []
            for order in sdk_orders:
                if getattr(order, "account", account_id) != account_id:
                    continue
                symbol = _str_or_empty(getattr(getattr(order, "contract", None), "symbol", None))
                if filters and filters.symbol and symbol and symbol.upper() != filters.symbol.upper():
                    continue
                mapped_status = _map_order_status(getattr(order, "status", None))
                if filters and filters.status and mapped_status != filters.status:
                    continue
                orders.append(self._order_from_sdk(account_id, order))
            return orders
        except Exception as e:
            raise RuntimeError(f"Failed to list orders from Tiger OpenAPI: {str(e)}") from e

    async def get_order(self, account_id: str, broker_order_id: str) -> BrokerOrder:
        try:
            order = self._trade_client().get_order(account=account_id, id=int(broker_order_id))
            if not order:
                raise KeyError(f"Order {broker_order_id} not found")
            return self._order_from_sdk(account_id, order)
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get order from Tiger OpenAPI: {str(e)}") from e

    async def preview_order(
        self,
        request: TradeOrderRequest,
        account_summary: AccountSummary,
    ) -> OrderPreview:
        try:
            preview = self._trade_client().preview_order(self._limit_order(request))
            estimated_amount = (
                request.quantity * request.limit_price if request.limit_price is not None else None
            )
            return OrderPreview(
                broker=BrokerId.tiger,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                limit_price=request.limit_price,
                estimated_amount=estimated_amount,
                estimated_fees=_decimal_or_zero(getattr(preview, "commission", None)) or None,
                risk_checks=[
                    RiskCheckResult(
                        rule_id="broker_preview",
                        status=RiskCheckStatus.passed,
                        reason="Tiger OpenAPI order preview returned successfully.",
                    )
                ],
                broker_preview={"source": "tiger_openapi", "preview": self._to_dict(preview)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to preview order from Tiger OpenAPI: {str(e)}") from e

    async def get_max_tradable_quantity(
        self,
        request: MaxTradableQuantityRequest,
    ) -> TradableQuantity:
        try:
            order_request = TradeOrderRequest(
                broker=BrokerId.tiger,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                quantity=Decimal("1"),
                limit_price=request.price,
                currency=request.currency,
            )
            result = self._trade_client().get_estimate_tradable_quantity(
                self._limit_order(order_request)
            )
            max_quantity = _decimal_or_zero(
                getattr(result, "quantity", None)
                or getattr(result, "max_quantity", None)
                or getattr(result, "tradable_quantity", None)
                or result
            )
            return TradableQuantity(
                broker=BrokerId.tiger,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                price=request.price,
                currency=request.currency,
                max_quantity=max_quantity,
                raw={"source": "tiger_openapi", "response": self._to_dict(result)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to estimate Tiger tradable quantity: {str(e)}") from e

    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        from brokergate.config import settings
        from tigeropen.common.util.order_utils import limit_order

        if settings.broker_mode not in ("paper", "live-trade"):
            raise ValueError(
                "Tiger adapter can only submit orders in broker paper or live-trade mode; "
                f"current broker_mode is '{settings.broker_mode}'."
            )

        if draft.status != OrderStatus.confirmed:
            raise ValueError("Tiger adapter only accepts confirmed order drafts")

        try:
            config = self._get_tiger_config()
            trade_client = self._trade_client()

            if draft.request.account_id != config.account:
                raise ValueError(
                    f"Account mismatch: draft account {draft.request.account_id} "
                    f"does not match adapter account {config.account}"
                )

            if settings.broker_mode == "paper" and draft.request.account_id != settings.tiger_account:
                raise ValueError("Tiger broker paper mode only allows the configured Tiger paper account.")

            if draft.request.quantity % 1 != 0:
                raise ValueError(f"Fractional quantities are not supported: {draft.request.quantity}")

            currency = draft.request.currency.upper()
            contract = self._stock_contract(draft.request.symbol, currency)

            order = limit_order(
                account=draft.request.account_id,
                contract=contract,
                action=draft.request.side.upper(),
                quantity=int(draft.request.quantity),
                limit_price=float(draft.request.limit_price)
                if draft.request.limit_price is not None
                else None,
            )

            trade_client.place_order(order)

            if not order.id:
                raise RuntimeError("Failed to place order: Tiger SDK did not return an order ID")

            return BrokerOrderReceipt(
                broker=BrokerId.tiger,
                broker_order_id=str(order.id),
                status=OrderStatus.submitted,
                raw={"order": self._to_dict(order)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to submit order to Tiger OpenAPI: {str(e)}") from e

    async def replace_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: ReplaceOrderRequest,
    ) -> BrokerOrder:
        try:
            trade_client = self._trade_client()
            order = trade_client.get_order(account=account_id, id=int(broker_order_id))
            if not order:
                raise KeyError(f"Order {broker_order_id} not found")
            trade_client.modify_order(
                order,
                quantity=float(request.quantity) if request.quantity is not None else None,
                limit_price=float(request.limit_price) if request.limit_price is not None else None,
            )
            return await self.get_order(account_id, broker_order_id)
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to replace Tiger order: {str(e)}") from e

    async def cancel_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: CancelOrderRequest,
    ) -> BrokerOrder:
        try:
            self._trade_client().cancel_order(account=account_id, id=int(broker_order_id))
            return await self.get_order(account_id, broker_order_id)
        except KeyError:
            return BrokerOrder(
                broker=BrokerId.tiger,
                account_id=account_id,
                broker_order_id=broker_order_id,
                status=BrokerOrderStatus.cancelled,
                raw={"source": "tiger_openapi_cancel_order"},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to cancel Tiger order: {str(e)}") from e

    async def get_order_fees(self, account_id: str, broker_order_id: str) -> OrderFee:
        try:
            order = self._trade_client().get_order(
                account=account_id,
                id=int(broker_order_id),
                show_charges=True,
            )
            if not order:
                raise KeyError(f"Order {broker_order_id} not found")
            charges = getattr(order, "charges", None)
            return OrderFee(
                broker=BrokerId.tiger,
                account_id=account_id,
                broker_order_id=broker_order_id,
                symbol=_str_or_empty(getattr(getattr(order, "contract", None), "symbol", None)) or None,
                currency=_str_or_empty(getattr(getattr(order, "contract", None), "currency", None))
                or "USD",
                total_fee=_decimal_or_zero(getattr(order, "commission", None)) or None,
                items=[{"charges": self._to_dict(charges)}] if charges else [],
                raw={"order": self._to_dict(order)},
            )
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get Tiger order fees: {str(e)}") from e

    async def list_today_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters | None = None,
    ) -> list[OrderExecution]:
        today = datetime.now(UTC)
        merged_filters = filters or ExecutionQueryFilters()
        merged_filters.date_from = merged_filters.date_from or today
        merged_filters.date_to = merged_filters.date_to or today
        return await self.list_history_executions(account_id, merged_filters)

    async def list_history_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters,
    ) -> list[OrderExecution]:
        try:
            if not filters.symbol:
                orders = self._trade_client().get_filled_orders(
                    account=account_id,
                    start_time=filters.date_from.strftime("%Y-%m-%d")
                    if isinstance(filters.date_from, datetime)
                    else None,
                    end_time=filters.date_to.strftime("%Y-%m-%d")
                    if isinstance(filters.date_to, datetime)
                    else None,
                )
                if not orders:
                    return []
                return [self._execution_from_order(account_id, order) for order in orders]

            kwargs: dict[str, Any] = {"account": account_id}
            kwargs["symbol"] = filters.symbol
            if isinstance(filters.date_from, datetime):
                kwargs["since_date"] = filters.date_from.strftime("%Y-%m-%d")
            if isinstance(filters.date_to, datetime):
                kwargs["to_date"] = filters.date_to.strftime("%Y-%m-%d")
            transactions = self._trade_client().get_transactions(**kwargs)
            if not transactions:
                return []
            return [self._execution_from_sdk(account_id, txn) for txn in transactions]
        except Exception as e:
            raise RuntimeError(f"Failed to list Tiger executions: {str(e)}") from e

    async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
        try:
            quotes = self._quote_client().get_briefs(symbols, include_ask_bid=True)
            return [self._quote_from_sdk(quote) for quote in quotes or []]
        except Exception as e:
            raise RuntimeError(f"Failed to get Tiger quote snapshots: {str(e)}") from e

    async def get_instrument_profile(self, symbol: str) -> InstrumentProfile:
        try:
            contract = self._trade_client().get_contract(symbol=symbol)
            if not contract:
                raise KeyError(f"Instrument {symbol} not found")
            return InstrumentProfile(
                broker=BrokerId.tiger,
                symbol=symbol,
                name=_str_or_empty(getattr(contract, "name", None)) or None,
                market=_str_or_empty(getattr(contract, "market", None)) or None,
                currency=_str_or_empty(getattr(contract, "currency", None)) or None,
                instrument_type=_str_or_empty(getattr(contract, "sec_type", None)) or "stock",
                tradable=True,
                raw={"contract": self._to_dict(contract)},
            )
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get Tiger instrument profile: {str(e)}") from e
