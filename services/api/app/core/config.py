from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:////data/gymops.db"
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 15.0
    hermes_oauth_enabled: bool = False
    hermes_command: str = "hermes"
    hermes_provider: str | None = None
    hermes_model: str | None = None
    hermes_timeout_seconds: float = 45.0
    api_secret_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
