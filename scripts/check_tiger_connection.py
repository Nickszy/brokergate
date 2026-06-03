import sys
from pathlib import Path

# Add src to python path so we can import brokergate
sys.path.append(str(Path(__file__).parent.parent / "src"))

from brokergate.config import settings
from brokergate.adapters.tiger import TigerOpenApiAdapter


def main():
    print("=== Tiger OpenAPI Connection Check ===")
    print(f"BROKERGATE_TIGER_ENABLED: {settings.tiger_enabled}")
    print(f"BROKERGATE_TIGER_ACCOUNT: {settings.tiger_account}")
    print(f"BROKERGATE_TIGER_ID: {settings.tiger_id}")
    print(f"BROKERGATE_TIGER_LICENSE: {settings.tiger_license}")
    print(f"BROKERGATE_TIGER_CONFIG_DIR: {settings.tiger_config_dir}")
    print(f"BROKERGATE_TIGER_PRIVATE_KEY_PATH: {settings.tiger_private_key_path}")
    print(f"BROKERGATE_TIGER_TOKEN_PATH: {settings.tiger_token_path}")
    print(f"BROKERGATE_BROKER_MODE: {settings.broker_mode}")
    print("---------------------------------------")

    if not settings.tiger_enabled:
        print("Warning: Tiger OpenAPI is not enabled in settings (BROKERGATE_TIGER_ENABLED is False).")
        print("Enable it by setting BROKERGATE_TIGER_ENABLED=true in your .env file.")

    adapter = TigerOpenApiAdapter()

    try:
        print("Initializing Tiger TradeClient config...")
        config = adapter._get_tiger_config()
        print("Config successfully generated.")
    except Exception as e:
        print(f"Error generating Tiger configuration: {e}")
        sys.exit(1)

    print("Attempting to connect and fetch managed accounts...")
    try:
        from tigeropen.trade.trade_client import TradeClient
        trade_client = TradeClient(config)
        accounts = trade_client.get_managed_accounts()
        print(f"Success! Retrieved {len(accounts)} managed account(s):")
        for acc in accounts:
            print(f" - Account: {acc}")

        # Try fetching account summary/assets if account is set
        account_id = settings.tiger_account or (accounts[0] if accounts else None)
        if account_id:
            print(f"\nAttempting to query assets for account: {account_id}...")
            assets = trade_client.get_prime_assets(account=account_id)
            print("Successfully retrieved asset snapshot.")
            print(f"Assets representation: {assets}")
        else:
            print("\nNo account ID configured or retrieved. Skipping asset query.")

    except Exception as e:
        print(f"Failed to connect or fetch data from Tiger OpenAPI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
