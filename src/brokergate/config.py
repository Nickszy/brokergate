from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = Field("local", validation_alias=AliasChoices("BROKERGATE_ENV", "OPENBROKER_ENV"))
    host: str = Field("0.0.0.0", validation_alias=AliasChoices("BROKERGATE_HOST", "OPENBROKER_HOST"))
    port: int = Field(8000, validation_alias=AliasChoices("BROKERGATE_PORT", "OPENBROKER_PORT"))
    api_key: str = Field(
        "change-me",
        validation_alias=AliasChoices("BROKERGATE_API_KEY", "OPENBROKER_API_KEY"),
    )
    confirmation_required: bool = Field(
        True,
        validation_alias=AliasChoices(
            "BROKERGATE_CONFIRMATION_REQUIRED",
            "OPENBROKER_CONFIRMATION_REQUIRED",
        ),
    )
    broker_mode: str = Field(
        "paper",
        validation_alias=AliasChoices("BROKERGATE_BROKER_MODE", "OPENBROKER_BROKER_MODE"),
    )

    # Tiger OpenAPI settings
    tiger_enabled: bool = Field(
        False,
        validation_alias=AliasChoices("BROKERGATE_TIGER_ENABLED", "OPENBROKER_TIGER_ENABLED"),
    )
    tiger_account: str = Field(
        "",
        validation_alias=AliasChoices("BROKERGATE_TIGER_ACCOUNT", "OPENBROKER_TIGER_ACCOUNT"),
    )
    tiger_id: str = Field(
        "",
        validation_alias=AliasChoices("BROKERGATE_TIGER_ID", "OPENBROKER_TIGER_ID"),
    )
    tiger_license: str = Field(
        "",
        validation_alias=AliasChoices("BROKERGATE_TIGER_LICENSE", "OPENBROKER_TIGER_LICENSE"),
    )
    tiger_config_dir: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_TIGER_CONFIG_DIR",
            "OPENBROKER_TIGER_CONFIG_DIR",
        ),
    )
    tiger_private_key_path: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_TIGER_PRIVATE_KEY_PATH",
            "OPENBROKER_TIGER_PRIVATE_KEY_PATH",
        ),
    )
    tiger_token_path: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_TIGER_TOKEN_PATH",
            "OPENBROKER_TIGER_TOKEN_PATH",
        ),
    )

    # Longbridge OpenAPI settings
    longbridge_enabled: bool = Field(
        False,
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_ENABLED",
            "OPENBROKER_LONGBRIDGE_ENABLED",
        ),
    )
    longbridge_app_key: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_APP_KEY",
            "OPENBROKER_LONGBRIDGE_APP_KEY",
        ),
    )
    longbridge_app_secret: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_APP_SECRET",
            "OPENBROKER_LONGBRIDGE_APP_SECRET",
        ),
    )
    longbridge_access_token: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_ACCESS_TOKEN",
            "OPENBROKER_LONGBRIDGE_ACCESS_TOKEN",
        ),
    )
    longbridge_account: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_ACCOUNT",
            "OPENBROKER_LONGBRIDGE_ACCOUNT",
        ),
    )
    longbridge_http_url: str = Field(
        "",
        validation_alias=AliasChoices(
            "BROKERGATE_LONGBRIDGE_HTTP_URL",
            "OPENBROKER_LONGBRIDGE_HTTP_URL",
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
