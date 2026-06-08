import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from brokergate.adapters.base import BrokerAdapter
from brokergate.adapters.paper_mock import mock_market_depth, mock_quote_snapshot
from brokergate.models import (
    AccountSummary,
    BrokerId,
    BrokerOrder,
    BrokerOrderReceipt,
    BrokerOrderStatus,
    CancelOrderRequest,
    DepthLevel,
    ExecutionQueryFilters,
    InstrumentProfile,
    MaxTradableQuantityRequest,
    OrderDraft,
    OrderExecution,
    OrderQueryFilters,
    OrderSide,
    OrderStatus,
    OrderType,
    OutsideRth,
    Position,
    QuoteDepth,
    QuoteSnapshot,
    ReplaceOrderRequest,
    TimeInForce,
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


def _enum_name(value: Any) -> str:
    """Normalize a Longbridge SDK enum (or a test mock) to its bare variant name.

    The real SDK enums are Rust/PyO3-backed: their `.name` attribute is None and
    str() renders as "OrderStatus.Canceled", so we take the part after the dot.
    Test mocks set `.name` to a plain string, so we honor that when present.
    """
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name.strip().upper()
    if value.__class__.__module__.startswith("unittest.mock"):
        return ""
    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.strip().upper()


def _map_order_status(value: Any) -> BrokerOrderStatus:
    status_name = _enum_name(value)
    if status_name in ("FILLED", "FULLY_FILLED"):
        return BrokerOrderStatus.filled
    if status_name in ("PARTIALFILLED", "PARTIALLY_FILLED", "PART_FILLED", "PARTIALWITHDRAWAL"):
        return BrokerOrderStatus.partially_filled
    if status_name in ("CANCELLED", "CANCELED"):
        return BrokerOrderStatus.cancelled
    if status_name in ("REJECTED", "UNKNOWN"):
        return BrokerOrderStatus.rejected
    if status_name == "EXPIRED":
        return BrokerOrderStatus.expired
    if status_name:
        return BrokerOrderStatus.submitted
    return BrokerOrderStatus.unknown


def _map_order_side(value: Any) -> OrderSide:
    return OrderSide.sell if _enum_name(value) == "SELL" else OrderSide.buy


def _map_order_type(value: Any) -> OrderType:
    # Longbridge has many concrete types (LO/ELO/ALO/ODD/LIT/MO/AO/TSLP*...);
    # collapse them onto the gateway's generic market/limit for reporting.
    if _enum_name(value) in ("MO", "AO"):
        return OrderType.market
    return OrderType.limit


def _currency_for_symbol(symbol: Any) -> str:
    """Infer trading currency from a Longbridge `ticker.region` symbol.

    SecurityQuote/Execution objects do not carry a currency field, so fall back
    to the region suffix (e.g. 700.HK -> HKD, AAPL.US -> USD)."""
    region = _str_or_empty(symbol).upper().rsplit(".", 1)[-1]
    return {
        "HK": "HKD",
        "US": "USD",
        "SG": "SGD",
        "SH": "CNY",
        "SZ": "CNY",
    }.get(region, "USD")


class LongbridgePaperAdapter(BrokerAdapter):
    broker_id = BrokerId.longbridge
    serves_mock_market_data = True

    async def test_connection(self, account_id: str) -> bool:
        return True

    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        base_currency = currency.upper() if currency else "USD"
        return AccountSummary(
            broker=BrokerId.longbridge,
            account_id=account_id,
            base_currency=base_currency,
            cash=Decimal("100000"),
            buying_power=Decimal("100000"),
            raw={"mode": "paper"},
        )

    async def list_positions(self, account_id: str) -> list[Position]:
        return [
            Position(
                broker=BrokerId.longbridge,
                account_id=account_id,
                symbol="700.HK",
                name="Tencent Holdings Ltd.",
                quantity=Decimal("100"),
                market_value=None,
                currency="HKD",
                cost_basis=Decimal("380"),
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
            broker=BrokerId.longbridge,
            broker_order_id=f"paper_longbridge_{uuid4().hex}",
            status=OrderStatus.submitted,
            raw={
                "mode": "paper",
                "symbol": draft.request.symbol,
                "side": draft.request.side,
                "quantity": str(draft.request.quantity),
            },
        )

    async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
        return [mock_quote_snapshot(BrokerId.longbridge, symbol) for symbol in symbols]

    async def get_market_depth(self, symbol: str) -> QuoteDepth:
        return mock_market_depth(BrokerId.longbridge, symbol)


class LongbridgeOpenApiAdapter(BrokerAdapter):
    broker_id = BrokerId.longbridge

    def __init__(self) -> None:
        # QuoteContext opens a persistent gateway connection whose handshake
        # costs ~4-5s. Building one per request reconnects every time and trips
        # broker_query_timeout, so cache and reuse a single warm context
        # (warm quote/depth calls then take ~0.3s).
        self._quote_context_cache: Any = None
        self._quote_context_lock = threading.Lock()

    def _get_longbridge_config(self) -> Any:
        from brokergate.config import settings
        from longbridge.openapi import Config

        if not settings.longbridge_app_key and not settings.longbridge_app_secret:
            try:
                return Config.from_apikey_env()
            except Exception as e:
                raise ValueError(
                    "Longbridge configuration credentials are not set. "
                    "Please configure either BROKERGATE_LONGBRIDGE_* settings in .env "
                    "or the SDK-native LONGBRIDGE_* environment variables."
                ) from e

        kwargs = {}
        if settings.longbridge_http_url:
            kwargs["http_url"] = settings.longbridge_http_url

        return Config.from_apikey(
            app_key=settings.longbridge_app_key,
            app_secret=settings.longbridge_app_secret,
            access_token=settings.longbridge_access_token,
            **kwargs,
        )

    def _trade_context(self) -> Any:
        from longbridge.openapi import TradeContext

        return TradeContext(self._get_longbridge_config())

    def _quote_context(self) -> Any:
        from longbridge.openapi import QuoteContext

        if self._quote_context_cache is not None:
            return self._quote_context_cache
        with self._quote_context_lock:
            if self._quote_context_cache is None:
                self._quote_context_cache = QuoteContext(self._get_longbridge_config())
            return self._quote_context_cache

    def _to_dict(self, obj: Any) -> Any:
        if obj.__class__.__module__.startswith("unittest.mock"):
            return str(obj)
        if isinstance(obj, (int, float, str, bool)) or obj is None:
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._to_dict(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        if hasattr(obj, "model_dump"):
            return self._to_dict(obj.model_dump())
        obj_dict = getattr(obj, "__dict__", None)
        if isinstance(obj_dict, dict):
            return {k: self._to_dict(v) for k, v in obj_dict.items() if not k.startswith("_")}
        return str(obj)

    def _validate_account(self, account_id: str) -> None:
        from brokergate.config import settings

        if account_id != settings.longbridge_account:
            raise ValueError(
                f"Account mismatch: requested account {account_id} does not match "
                f"configured Longbridge account {settings.longbridge_account}"
            )

    def _order_from_sdk(self, account_id: str, order: Any) -> BrokerOrder:
        return BrokerOrder(
            broker=BrokerId.longbridge,
            account_id=account_id,
            broker_order_id=_str_or_empty(getattr(order, "order_id", None)),
            symbol=_str_or_empty(getattr(order, "symbol", None)),
            side=_map_order_side(getattr(order, "side", None)),
            order_type=_map_order_type(getattr(order, "order_type", None)),
            quantity=_decimal_or_zero(getattr(order, "quantity", None)),
            filled_quantity=_decimal_or_zero(getattr(order, "executed_quantity", None)),
            limit_price=_decimal_or_zero(getattr(order, "price", None)) or None,
            average_fill_price=_decimal_or_zero(getattr(order, "executed_price", None)) or None,
            status=_map_order_status(getattr(order, "status", None)),
            currency=_str_or_empty(getattr(order, "currency", None)) or "USD",
            submitted_at=_safe_datetime(
                getattr(order, "submitted_at", None) or getattr(order, "created_at", None)
            ),
            raw={"order": self._to_dict(order)},
        )

    def _execution_from_sdk(self, account_id: str, execution: Any) -> OrderExecution:
        return OrderExecution(
            broker=BrokerId.longbridge,
            account_id=account_id,
            broker_order_id=_str_or_empty(getattr(execution, "order_id", None)) or None,
            execution_id=_str_or_empty(
                getattr(execution, "trade_id", None) or getattr(execution, "execution_id", None)
            ),
            symbol=_str_or_empty(getattr(execution, "symbol", None)),
            side=_map_order_side(getattr(execution, "side", None)),
            quantity=_decimal_or_zero(
                getattr(execution, "quantity", None) or getattr(execution, "executed_quantity", None)
            ),
            price=_decimal_or_zero(getattr(execution, "price", None) or getattr(execution, "executed_price", None)),
            currency=_str_or_empty(getattr(execution, "currency", None))
            or _currency_for_symbol(getattr(execution, "symbol", None)),
            executed_at=_safe_datetime(
                getattr(execution, "executed_at", None) or getattr(execution, "trade_done_at", None)
            )
            or datetime.now(UTC),
            raw={"execution": self._to_dict(execution)},
        )

    def _quote_from_sdk(self, quote: Any) -> QuoteSnapshot:
        symbol = _str_or_empty(getattr(quote, "symbol", None))
        return QuoteSnapshot(
            broker=BrokerId.longbridge,
            symbol=symbol,
            currency=_str_or_empty(getattr(quote, "currency", None)) or _currency_for_symbol(symbol),
            last_price=_decimal_or_zero(getattr(quote, "last_done", None)) or None,
            open_price=_decimal_or_zero(getattr(quote, "open", None)) or None,
            high_price=_decimal_or_zero(getattr(quote, "high", None)) or None,
            low_price=_decimal_or_zero(getattr(quote, "low", None)) or None,
            previous_close=_decimal_or_zero(getattr(quote, "prev_close", None)) or None,
            timestamp=_safe_datetime(getattr(quote, "timestamp", None)),
            raw={"quote": self._to_dict(quote)},
        )

    async def test_connection(self, account_id: str) -> bool:
        try:
            balances = self._trade_context().account_balance()
            return bool(balances)
        except Exception:
            return False

    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        self._validate_account(account_id)

        try:
            balances = self._trade_context().account_balance()
            if not balances:
                raise ValueError("No account balance retrieved from Longbridge")

            target_bal = None
            if currency:
                for bal in balances:
                    if bal.currency.upper() == currency.upper():
                        target_bal = bal
                        break
                if not target_bal:
                    raise ValueError(f"Requested currency {currency} is not present in the Longbridge balance set.")
            else:
                for bal in balances:
                    if bal.currency == "USD":
                        target_bal = bal
                        break
                if not target_bal:
                    for bal in balances:
                        if bal.currency == "HKD":
                            target_bal = bal
                            break
                if not target_bal and balances:
                    target_bal = balances[0]

            if not target_bal:
                raise ValueError("No balance information found")

            return AccountSummary(
                broker=BrokerId.longbridge,
                account_id=account_id,
                base_currency=target_bal.currency if target_bal.currency else "USD",
                cash=_decimal_or_zero(target_bal.total_cash),
                buying_power=_decimal_or_zero(target_bal.buy_power),
                raw={"balances": str(balances)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get account summary from Longbridge: {str(e)}") from e

    async def list_positions(self, account_id: str) -> list[Position]:
        self._validate_account(account_id)

        try:
            sdk_resp = self._trade_context().stock_positions()
            if not sdk_resp or not sdk_resp.channels:
                return []

            unified_positions = []
            for chan in sdk_resp.channels:
                for pos in chan.positions:
                    unified_positions.append(
                        Position(
                            broker=BrokerId.longbridge,
                            account_id=account_id,
                            symbol=pos.symbol if pos.symbol else "",
                            name=pos.symbol_name if pos.symbol_name else "",
                            quantity=_decimal_or_zero(pos.quantity),
                            market_value=None,
                            currency=pos.currency if pos.currency else "HKD",
                            cost_basis=_decimal_or_zero(pos.cost_price),
                        )
                    )
            return unified_positions
        except Exception as e:
            raise RuntimeError(f"Failed to list positions from Longbridge: {str(e)}") from e

    async def list_orders(
        self,
        account_id: str,
        filters: OrderQueryFilters | None = None,
    ) -> list[BrokerOrder]:
        self._validate_account(account_id)

        try:
            sdk_orders = self._trade_context().today_orders(symbol=filters.symbol if filters else None)
            if not sdk_orders:
                return []

            orders = []
            for order in sdk_orders:
                mapped_status = _map_order_status(getattr(order, "status", None))
                if filters and filters.status and mapped_status != filters.status:
                    continue
                orders.append(self._order_from_sdk(account_id, order))
            return orders
        except Exception as e:
            raise RuntimeError(f"Failed to list orders from Longbridge: {str(e)}") from e

    async def get_order(self, account_id: str, broker_order_id: str) -> BrokerOrder:
        self._validate_account(account_id)
        try:
            order = self._trade_context().order_detail(broker_order_id)
            if not order:
                raise KeyError(f"Order {broker_order_id} not found")
            return self._order_from_sdk(account_id, order)
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get order from Longbridge: {str(e)}") from e

    async def get_max_tradable_quantity(
        self,
        request: MaxTradableQuantityRequest,
    ) -> TradableQuantity:
        from longbridge.openapi import OrderSide as LBOrderSide
        from longbridge.openapi import OrderType as LBOrderType

        self._validate_account(request.account_id)
        try:
            response = self._trade_context().estimate_max_purchase_quantity(
                symbol=request.symbol,
                order_type=LBOrderType.LO,
                side=LBOrderSide.Buy if request.side == "buy" else LBOrderSide.Sell,
                price=request.price,
                currency=request.currency,
            )
            max_quantity = _decimal_or_zero(
                getattr(response, "cash_max_qty", None)
                or getattr(response, "margin_max_qty", None)
                or getattr(response, "max_quantity", None)
                or response
            )
            return TradableQuantity(
                broker=BrokerId.longbridge,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                price=request.price,
                currency=request.currency,
                max_quantity=max_quantity,
                raw={"source": "longbridge_openapi", "response": self._to_dict(response)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to estimate Longbridge tradable quantity: {str(e)}") from e

    def _resolve_order_type(self, request: TradeOrderRequest) -> Any:
        """Pick the concrete Longbridge OrderType from the generic request shape."""
        from longbridge.openapi import OrderType as LBOrderType

        if request.trailing_amount is not None:
            return LBOrderType.TSLPAMT
        if request.trailing_percent is not None:
            return LBOrderType.TSLPPCT
        if request.trigger_price is not None:
            # stop-limit when a limit price is also given, otherwise stop-market
            return LBOrderType.LIT if request.limit_price is not None else LBOrderType.MIT
        if request.order_type == OrderType.market:
            return LBOrderType.MO
        return LBOrderType.LO

    def _resolve_time_in_force(self, request: TradeOrderRequest) -> Any:
        from longbridge.openapi import TimeInForceType

        if request.time_in_force == TimeInForce.gtc:
            return TimeInForceType.GoodTilCanceled
        if request.time_in_force == TimeInForce.gtd:
            return TimeInForceType.GoodTilDate
        return TimeInForceType.Day

    def _resolve_outside_rth(self, request: TradeOrderRequest) -> Any:
        from longbridge.openapi import OutsideRTH

        return {
            OutsideRth.rth_only: OutsideRTH.RTHOnly,
            OutsideRth.any_time: OutsideRTH.AnyTime,
            OutsideRth.overnight: OutsideRTH.Overnight,
        }.get(request.outside_rth, OutsideRTH.RTHOnly)

    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        from brokergate.config import settings
        from longbridge.openapi import OrderSide as LBOrderSide

        if settings.broker_mode not in ("paper", "live-trade"):
            raise ValueError(
                "Longbridge adapter can only submit orders in broker paper or live-trade mode; "
                f"current broker_mode is '{settings.broker_mode}'."
            )

        self._validate_account(draft.request.account_id)

        if draft.request.quantity % 1 != 0:
            raise ValueError(f"Fractional quantities are not supported: {draft.request.quantity}")

        if draft.status != OrderStatus.confirmed:
            raise ValueError("Longbridge adapter only accepts confirmed order drafts")

        request = draft.request
        if request.time_in_force == TimeInForce.gtd and request.expire_date is None:
            raise ValueError("expire_date is required when time_in_force is gtd")

        order_type = self._resolve_order_type(request)
        kwargs: dict[str, Any] = {
            "symbol": request.symbol,
            "order_type": order_type,
            "side": LBOrderSide.Buy if request.side == "buy" else LBOrderSide.Sell,
            "submitted_quantity": Decimal(str(request.quantity)),
            "time_in_force": self._resolve_time_in_force(request),
            "remark": request.client_memo or "BrokerGate Trade",
        }
        if request.limit_price is not None:
            kwargs["submitted_price"] = Decimal(str(request.limit_price))
        if request.trigger_price is not None:
            kwargs["trigger_price"] = Decimal(str(request.trigger_price))
        if request.trailing_amount is not None:
            kwargs["trailing_amount"] = Decimal(str(request.trailing_amount))
        if request.trailing_percent is not None:
            kwargs["trailing_percent"] = Decimal(str(request.trailing_percent))
        if request.time_in_force == TimeInForce.gtd and request.expire_date is not None:
            kwargs["expire_date"] = request.expire_date
        if request.outside_rth is not None:
            kwargs["outside_rth"] = self._resolve_outside_rth(request)

        try:
            resp = self._trade_context().submit_order(**kwargs)

            if not resp or not resp.order_id:
                raise RuntimeError("Failed to place order: Longbridge SDK did not return an order ID")

            return BrokerOrderReceipt(
                broker=BrokerId.longbridge,
                broker_order_id=str(resp.order_id),
                status=OrderStatus.submitted,
                raw={"response": self._to_dict(resp)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to submit order to Longbridge OpenAPI: {str(e)}") from e

    async def replace_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: ReplaceOrderRequest,
    ) -> BrokerOrder:
        self._validate_account(account_id)
        try:
            self._trade_context().replace_order(
                order_id=broker_order_id,
                quantity=request.quantity,
                price=request.limit_price,
                remark="BrokerGate replace",
            )
            return await self.get_order(account_id, broker_order_id)
        except Exception as e:
            raise RuntimeError(f"Failed to replace Longbridge order: {str(e)}") from e

    async def cancel_order(
        self,
        account_id: str,
        broker_order_id: str,
        request: CancelOrderRequest,
    ) -> BrokerOrder:
        self._validate_account(account_id)
        try:
            self._trade_context().cancel_order(broker_order_id)
            return await self.get_order(account_id, broker_order_id)
        except KeyError:
            return BrokerOrder(
                broker=BrokerId.longbridge,
                account_id=account_id,
                broker_order_id=broker_order_id,
                status=BrokerOrderStatus.cancelled,
                raw={"source": "longbridge_openapi_cancel_order"},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to cancel Longbridge order: {str(e)}") from e

    async def list_today_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters | None = None,
    ) -> list[OrderExecution]:
        self._validate_account(account_id)
        try:
            executions = self._trade_context().today_executions(symbol=filters.symbol if filters else None)
            return [self._execution_from_sdk(account_id, execution) for execution in executions or []]
        except Exception as e:
            raise RuntimeError(f"Failed to list Longbridge today executions: {str(e)}") from e

    async def list_history_executions(
        self,
        account_id: str,
        filters: ExecutionQueryFilters,
    ) -> list[OrderExecution]:
        self._validate_account(account_id)
        try:
            executions = self._trade_context().history_executions(
                symbol=filters.symbol,
                start_at=filters.date_from,
                end_at=filters.date_to,
            )
            return [self._execution_from_sdk(account_id, execution) for execution in executions or []]
        except Exception as e:
            raise RuntimeError(f"Failed to list Longbridge history executions: {str(e)}") from e

    async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]:
        try:
            # Use quote() (pull snapshot), NOT realtime_quote() which only returns
            # symbols previously subscribed to the streaming feed (else empty).
            quotes = self._quote_context().quote(symbols)
            return [self._quote_from_sdk(quote) for quote in quotes or []]
        except Exception as e:
            raise RuntimeError(f"Failed to get Longbridge quote snapshots: {str(e)}") from e

    async def get_market_depth(self, symbol: str) -> QuoteDepth:
        try:
            book = self._quote_context().depth(symbol)
            return QuoteDepth(
                broker=BrokerId.longbridge,
                symbol=symbol,
                asks=self._depth_levels_from_sdk(getattr(book, "asks", None)),
                bids=self._depth_levels_from_sdk(getattr(book, "bids", None)),
                raw={"depth": self._to_dict(book)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get Longbridge market depth: {str(e)}") from e

    @staticmethod
    def _depth_levels_from_sdk(levels: Any) -> list[DepthLevel]:
        result: list[DepthLevel] = []
        for level in levels or []:
            price = getattr(level, "price", None)
            # Markets without a depth entitlement return placeholder levels with
            # price=None / volume=0; drop them so an empty side means "no depth".
            if price is None:
                continue
            order_num = getattr(level, "order_num", None)
            result.append(
                DepthLevel(
                    price=_decimal_or_zero(price) or None,
                    volume=_decimal_or_zero(getattr(level, "volume", None)),
                    order_count=int(order_num) if order_num is not None else None,
                )
            )
        return result

    async def get_instrument_profile(self, symbol: str) -> InstrumentProfile:
        try:
            infos = self._quote_context().static_info([symbol])
            if not infos:
                raise KeyError(f"Instrument {symbol} not found")
            info = infos[0]
            return InstrumentProfile(
                broker=BrokerId.longbridge,
                symbol=_str_or_empty(getattr(info, "symbol", None)) or symbol,
                name=(
                    _str_or_empty(getattr(info, "name_en", None))
                    or _str_or_empty(getattr(info, "name_cn", None))
                    or _str_or_empty(getattr(info, "name_hk", None))
                    or None
                ),
                market=_str_or_empty(getattr(info, "exchange", None)) or None,
                currency=_str_or_empty(getattr(info, "currency", None)) or None,
                instrument_type="stock",
                lot_size=_decimal_or_zero(getattr(info, "lot_size", None)) or None,
                tradable=True,
                raw={"static_info": self._to_dict(info)},
            )
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to get Longbridge instrument profile: {str(e)}") from e
