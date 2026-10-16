"""Centralized application settings (loaded from backend/.env or environment)."""
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"  # dev | test | prod
    log_level: str = "INFO"
    secret_key: str = "dev-secret-change-me"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    database_url: str = "sqlite:///./erp_dev.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    cache_enable: bool = False

    cors_origins: list[str] = ["http://localhost:5173"]

    media_dir: str = "./media"
    max_upload_mb: int = 10

    seed_demo_data: bool = False
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "ChangeMe!123"

    currency_precision: int = 2  # default display/rounding exponent

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def settings_refresh() -> Settings:
    """Reset cache (used by tests to change configuration per test run)."""
    get_settings.cache_clear()
    return get_settings()
