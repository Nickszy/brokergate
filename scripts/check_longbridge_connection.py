import sys
from pathlib import Path

# Add src to python path so we can import brokergate
sys.path.append(str(Path(__file__).parent.parent / "src"))

from brokergate.config import settings
from brokergate.adapters.longbridge import LongbridgeOpenApiAdapter


def main():
    print("=== Longbridge OpenAPI Connection Check ===")
    print(f"BROKERGATE_LONGBRIDGE_ENABLED: {settings.longbridge_enabled}")
    print(f"BROKERGATE_LONGBRIDGE_ACCOUNT: {settings.longbridge_account}")
    print(f"BROKERGATE_LONGBRIDGE_APP_KEY: {settings.longbridge_app_key}")
    print(f"BROKERGATE_LONGBRIDGE_APP_SECRET: {settings.longbridge_app_secret[:6]}... (hidden)")
    print(f"BROKERGATE_LONGBRIDGE_ACCESS_TOKEN: {settings.longbridge_access_token[:15]}... (hidden)")
    print(f"BROKERGATE_BROKER_MODE: {settings.broker_mode}")
    print("-------------------------------------------")

    if not settings.longbridge_enabled:
        print("Warning: Longbridge OpenAPI is not enabled in settings.")

    adapter = LongbridgeOpenApiAdapter()

    try:
        print("Initializing Longbridge Config...")
        config = adapter._get_longbridge_config()
        print("Config successfully generated.")
    except Exception as e:
        print(f"Error generating Longbridge configuration: {e}")
        sys.exit(1)

    print("Attempting to connect and fetch account balances...")
    try:
        from longbridge.openapi import TradeContext
        ctx = TradeContext(config)
        balances = ctx.account_balance()
        print(f"Success! Retrieved {len(balances)} currency balance segments:")
        for bal in balances:
            print(f" - Currency: {bal.currency}")
            print(f"   Total Cash: {bal.total_cash}")
            print(f"   Buying Power: {bal.buy_power}")

        print("\nAttempting to query positions...")
        positions_resp = ctx.stock_positions()
        total_positions = sum(len(chan.positions) for chan in positions_resp.channels) if positions_resp.channels else 0
        print(f"Retrieved {total_positions} positions:")
        if positions_resp.channels:
            for chan in positions_resp.channels:
                for pos in chan.positions:
                    print(f" - Symbol: {pos.symbol} ({pos.symbol_name})")
                    print(f"   Quantity: {pos.quantity}")
                    print(f"   Cost Price: {pos.cost_price}")

    except Exception as e:
        print(f"Failed to connect or fetch data from Longbridge OpenAPI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
