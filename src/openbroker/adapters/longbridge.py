from uuid import uuid4
from decimal import Decimal
from typing import Any

from openbroker.adapters.base import BrokerAdapter
from openbroker.models import AccountSummary, BrokerId, BrokerOrderReceipt, OrderDraft, OrderStatus, Position


class LongbridgePaperAdapter(BrokerAdapter):
    broker_id = BrokerId.longbridge

    async def test_connection(self, account_id: str) -> bool:
        return True

    async def get_account_summary(self, account_id: str) -> AccountSummary:
        return AccountSummary(
            broker=BrokerId.longbridge,
            account_id=account_id,
            base_currency="USD",
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
                market_value=Decimal("40000"),
                currency="HKD",
                cost_basis=Decimal("380"),
            )
        ]

    async def list_orders(self, account_id: str) -> list[BrokerOrderReceipt]:
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


class LongbridgeOpenApiAdapter(BrokerAdapter):
    broker_id = BrokerId.longbridge

    def _get_longbridge_config(self) -> Any:
        from openbroker.config import settings
        from longbridge.openapi import Config

        kwargs = {}
        if settings.longbridge_http_url:
            kwargs["http_url"] = settings.longbridge_http_url

        config = Config.from_apikey(
            app_key=settings.longbridge_app_key,
            app_secret=settings.longbridge_app_secret,
            access_token=settings.longbridge_access_token,
            **kwargs
        )
        return config

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

    async def test_connection(self, account_id: str) -> bool:
        from longbridge.openapi import TradeContext
        try:
            config = self._get_longbridge_config()
            ctx = TradeContext(config)
            balances = ctx.account_balance()
            return bool(balances)
        except Exception:
            return False

    async def get_account_summary(self, account_id: str) -> AccountSummary:
        from longbridge.openapi import TradeContext
        try:
            config = self._get_longbridge_config()
            ctx = TradeContext(config)

            balances = ctx.account_balance()
            if not balances:
                raise ValueError("No account balance retrieved from Longbridge")

            target_bal = None
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

            cash = Decimal(str(target_bal.total_cash)) if target_bal.total_cash is not None else Decimal("0")
            buying_power = Decimal(str(target_bal.buy_power)) if target_bal.buy_power is not None else Decimal("0")
            base_currency = target_bal.currency if target_bal.currency else "USD"

            return AccountSummary(
                broker=BrokerId.longbridge,
                account_id=account_id,
                base_currency=base_currency,
                cash=cash,
                buying_power=buying_power,
                raw={"balances": self._to_dict(balances)},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get account summary from Longbridge: {str(e)}") from e

    async def list_positions(self, account_id: str) -> list[Position]:
        from longbridge.openapi import TradeContext
        try:
            config = self._get_longbridge_config()
            ctx = TradeContext(config)

            sdk_resp = ctx.stock_positions()
            if not sdk_resp or not sdk_resp.channels:
                return []

            unified_positions = []
            for chan in sdk_resp.channels:
                for pos in chan.positions:
                    symbol = pos.symbol if pos.symbol else ""
                    name = pos.symbol_name if pos.symbol_name else ""
                    currency = pos.currency if pos.currency else "HKD"

                    quantity = Decimal(str(pos.quantity)) if pos.quantity is not None else Decimal("0")
                    cost_price = Decimal(str(pos.cost_price)) if pos.cost_price is not None else Decimal("0")
                    market_value = quantity * cost_price

                    unified_positions.append(
                        Position(
                            broker=BrokerId.longbridge,
                            account_id=account_id,
                            symbol=symbol,
                            name=name,
                            quantity=quantity,
                            market_value=market_value,
                            currency=currency,
                            cost_basis=cost_price,
                        )
                    )
            return unified_positions
        except Exception as e:
            raise RuntimeError(f"Failed to list positions from Longbridge: {str(e)}") from e

    async def list_orders(self, account_id: str) -> list[BrokerOrderReceipt]:
        from longbridge.openapi import TradeContext
        from openbroker.config import settings

        if account_id != settings.longbridge_account:
            return []

        try:
            config = self._get_longbridge_config()
            ctx = TradeContext(config)

            sdk_orders = ctx.today_orders()
            if not sdk_orders:
                return []

            receipts = []
            for order in sdk_orders:
                status = OrderStatus.submitted
                sdk_status_name = ""
                if order.status:
                    sdk_status_name = getattr(order.status, "name", str(order.status)).upper()

                if sdk_status_name in ("REJECTED", "CANCELED", "EXPIRED", "UNKNOWN"):
                    status = OrderStatus.rejected
                else:
                    status = OrderStatus.submitted

                receipts.append(
                    BrokerOrderReceipt(
                        broker=BrokerId.longbridge,
                        broker_order_id=str(order.order_id) if order.order_id else "",
                        status=status,
                        raw=self._to_dict(order)
                    )
                )
            return receipts
        except Exception as e:
            raise RuntimeError(f"Failed to list orders from Longbridge: {str(e)}") from e

    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        from longbridge.openapi import TradeContext, OrderType as LBOrderType, OrderSide as LBOrderSide, TimeInForceType
        from openbroker.config import settings

        if settings.broker_mode != "live-trade":
            raise ValueError(f"Longbridge adapter cannot submit order when broker_mode is '{settings.broker_mode}'. Must be 'live-trade'.")

        if draft.request.account_id != settings.longbridge_account:
            raise ValueError(f"Account mismatch: draft account {draft.request.account_id} does not match adapter account {settings.longbridge_account}")

        if draft.request.quantity % 1 != 0:
            raise ValueError(f"Fractional quantities are not supported: {draft.request.quantity}")

        if draft.status != OrderStatus.confirmed:
            raise ValueError("Longbridge adapter only accepts confirmed order drafts")

        try:
            config = self._get_longbridge_config()
            ctx = TradeContext(config)

            side = LBOrderSide.Buy if draft.request.side == "buy" else LBOrderSide.Sell
            order_type = LBOrderType.LO
            submitted_price = Decimal(str(draft.request.limit_price)) if draft.request.limit_price is not None else None
            quantity = Decimal(str(draft.request.quantity))

            resp = ctx.submit_order(
                symbol=draft.request.symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                time_in_force=TimeInForceType.Day,
                submitted_price=submitted_price,
                remark=draft.request.client_memo or "OpenBroker Trade"
            )

            if not resp or not resp.order_id:
                raise RuntimeError("Failed to place order: Longbridge SDK did not return an order ID")

            return BrokerOrderReceipt(
                broker=BrokerId.longbridge,
                broker_order_id=str(resp.order_id),
                status=OrderStatus.submitted,
                raw=self._to_dict(resp),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to submit order to Longbridge OpenAPI: {str(e)}") from e
