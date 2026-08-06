from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    anthropic_api_key: str = ""
    richpanel_api_token: str = ""
    richpanel_base_url: str = "https://api.richpanel.com"
    database_path: str = "data/support_agent.db"
    dry_run: bool = True
    sync_interval_seconds: int = 180
    host: str = "127.0.0.1"
    port: int = 8788
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    anthropic_model: str = "claude-sonnet-4-20250514"


@lru_cache
def get_settings() -> Settings:
    return Settings()
