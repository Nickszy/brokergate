from uuid import uuid4
from decimal import Decimal
from typing import Any

from openbroker.adapters.base import BrokerAdapter
from openbroker.models import AccountSummary, BrokerId, BrokerOrderReceipt, OrderDraft, OrderStatus, Position


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

    async def list_orders(self, account_id: str) -> list[BrokerOrderReceipt]:
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
        from openbroker.config import settings
        from pathlib import Path
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
        from tigeropen.trade.trade_client import TradeClient
        try:
            config = self._get_tiger_config()
            trade_client = TradeClient(config)
            accounts = trade_client.get_managed_accounts()
            return bool(accounts)
        except Exception:
            return False

    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary:
        from tigeropen.trade.trade_client import TradeClient
        try:
            config = self._get_tiger_config()
            trade_client = TradeClient(config)
            
            assets_list = trade_client.get_prime_assets(account=account_id)
            if not assets_list:
                raise ValueError(f"No asset information returned for account {account_id}")
            
            assets = assets_list[0] if isinstance(assets_list, list) else assets_list
            segment = assets.segments.get('S')
            if not segment:
                raise ValueError(f"No stock segment ('S') found in assets for account {account_id}")
            
            cash = Decimal(str(segment.cash_balance)) if segment.cash_balance is not None else Decimal("0")
            buying_power = Decimal(str(segment.buying_power)) if segment.buying_power is not None else Decimal("0")
            
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
        from tigeropen.trade.trade_client import TradeClient
        try:
            config = self._get_tiger_config()
            trade_client = TradeClient(config)
            
            positions_list = trade_client.get_positions(account=account_id)
            if not positions_list:
                return []
            
            unified_positions = []
            for pos in positions_list:
                contract = pos.contract
                symbol = contract.symbol if contract else ""
                name = contract.name if contract else ""
                currency = contract.currency if contract else "USD"
                
                quantity = Decimal(str(pos.quantity)) if pos.quantity is not None else Decimal("0")
                market_value = Decimal(str(pos.market_value)) if pos.market_value is not None else Decimal("0")
                cost_basis = Decimal(str(pos.average_cost)) if pos.average_cost is not None else Decimal("0")
                
                unified_positions.append(
                    Position(
                        broker=BrokerId.tiger,
                        account_id=account_id,
                        symbol=symbol,
                        name=name,
                        quantity=quantity,
                        market_value=market_value,
                        currency=currency,
                        cost_basis=cost_basis,
                    )
                )
            return unified_positions
        except Exception as e:
            raise RuntimeError(f"Failed to list positions from Tiger OpenAPI: {str(e)}") from e

    async def list_orders(self, account_id: str) -> list[BrokerOrderReceipt]:
        from tigeropen.trade.trade_client import TradeClient
        try:
            config = self._get_tiger_config()
            trade_client = TradeClient(config)

            # P2: Pass account parameter to filter on Tiger server side
            sdk_orders = trade_client.get_orders(account=account_id)
            if not sdk_orders:
                return []

            receipts = []
            for order in sdk_orders:
                # P2: Double-check filter locally
                if order.account != account_id:
                    continue
                status = OrderStatus.submitted
                sdk_status_name = ""
                if order.status:
                    if hasattr(order.status, "name"):
                        sdk_status_name = order.status.name.upper()
                    else:
                        sdk_status_name = str(order.status).upper()

                if sdk_status_name in ("REJECTED", "INACTIVE", "INVALID", "EXPIRED"):
                    status = OrderStatus.rejected
                else:
                    status = OrderStatus.submitted

                receipts.append(
                    BrokerOrderReceipt(
                        broker=BrokerId.tiger,
                        broker_order_id=str(order.id) if order.id else "",
                        status=status,
                        raw=self._to_dict(order)
                    )
                )
            return receipts
        except Exception as e:
            raise RuntimeError(f"Failed to list orders from Tiger OpenAPI: {str(e)}") from e

    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
        from tigeropen.trade.trade_client import TradeClient
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import limit_order
        from openbroker.config import settings

        # P0: Mode boundary protection check
        if settings.broker_mode != "live-trade":
            raise ValueError(f"Tiger adapter cannot submit order when broker_mode is '{settings.broker_mode}'. Must be 'live-trade'.")

        if draft.status != OrderStatus.confirmed:
            raise ValueError("Tiger adapter only accepts confirmed order drafts")

        try:
            config = self._get_tiger_config()
            trade_client = TradeClient(config)

            # P0: Account mismatch protection check
            if draft.request.account_id != config.account:
                raise ValueError(f"Account mismatch: draft account {draft.request.account_id} does not match adapter account {config.account}")

            # P1: Quantity integrity check
            if draft.request.quantity % 1 != 0:
                raise ValueError(f"Fractional quantities are not supported: {draft.request.quantity}")

            currency = draft.request.currency.upper()
            exchange = "SMART" if currency == "USD" else "SEHK"
            contract = stock_contract(
                symbol=draft.request.symbol,
                currency=currency,
                exchange=exchange
            )

            action = draft.request.side.upper()
            limit_price = float(draft.request.limit_price) if draft.request.limit_price is not None else None
            quantity = int(draft.request.quantity)

            order = limit_order(
                account=draft.request.account_id,
                contract=contract,
                action=action,
                quantity=quantity,
                limit_price=limit_price
            )

            trade_client.place_order(order)

            if not order.id:
                raise RuntimeError("Failed to place order: Tiger SDK did not return an order ID")

            return BrokerOrderReceipt(
                broker=BrokerId.tiger,
                broker_order_id=str(order.id),
                status=OrderStatus.submitted,
                raw=self._to_dict(order),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to submit order to Tiger OpenAPI: {str(e)}") from e
