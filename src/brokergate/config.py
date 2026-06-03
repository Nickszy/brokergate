from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str = "change-me"
    confirmation_required: bool = True
    broker_mode: str = "paper"

    # Tiger OpenAPI settings
    tiger_enabled: bool = False
    tiger_account: str = ""
    tiger_id: str = ""
    tiger_license: str = ""
    tiger_config_dir: str = ""
    tiger_private_key_path: str = ""
    tiger_token_path: str = ""

    # Longbridge OpenAPI settings
    longbridge_enabled: bool = False
    longbridge_app_key: str = ""
    longbridge_app_secret: str = ""
    longbridge_access_token: str = ""
    longbridge_account: str = ""
    longbridge_http_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BROKERGATE_",
        extra="ignore",
    )


settings = Settings()

