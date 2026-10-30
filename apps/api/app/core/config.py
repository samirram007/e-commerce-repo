"""Centralized application settings (loaded from apps/api/.env files or environment).

Environment file contract (priority: process env > dotenv files in order,
*last* file in a tuple wins):

1. Real environment variables   — always win (CI, containers, secrets manager)
2. ``.env``                     — local/generic overrides, gitignored
3. ``.env.{APP_ENV}``           — environment defaults, committed
4. Class defaults

Selection by ``APP_ENV``:

- ``dev``    → ``.env.development`` defaults; your local ``.env`` overrides them.
- ``test``   → ``.env.testing`` FORCE-wins over any local ``.env`` so a stray
               local file can never point tests at a dev/prod database.
              (``tests/conftest.py`` additionally sets os.environ before imports.)
- ``prod``   → ``.env.production`` force-wins over any local ``.env``; secrets
              come from real process env in a proper deployment.
- ``prod`` refuses placeholder SECRET_KEY values (fail fast, see guard below).
"""
import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_app_env = os.environ.get("APP_ENV", "dev")

_env_file: tuple[str, ...]
if _app_env == "test":
    _env_file = (".env", ".env.testing")
elif _app_env == "prod":
    _env_file = (".env", ".env.production")
else:
    _env_file = (".env.development", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"  # dev | test | prod
    log_level: str = "INFO"
    secret_key: str = "dev-secret-change-me"
    #: Fernet key for payment provider secrets at rest (see shared/crypto.py).
    payment_encryption_key: str | None = None
    #: Public base URL of this API — used to build provider webhook URLs.
    public_api_base_url: str = "http://localhost:8000"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    database_url: str = "mysql+pymysql://root:Samir@007@localhost:3307/erp"
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

    cookie_secure: bool | None = None  # None → secure when APP_ENV=prod

    # ---- storefront order expiry (abandoned gateway checkouts) ----
    # unpaid orders older than this are cancelled and their stock released
    order_payment_timeout_minutes: int = 30
    # how often the background sweeper runs; <= 0 disables it
    order_expiry_sweep_seconds: int = 300

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @model_validator(mode="after")
    def production_secret_guard(self) -> "Settings":
        """Refuse to run in prod with a default/published secret key."""
        if self.is_prod:
            weak = {
                "",
                "change-me-to-a-long-random-string",
                "dev-secret-change-me",
                "test-secret",
            }
            if self.secret_key.strip().lower() in weak:
                raise ValueError(
                    "APP_ENV=prod requires a strong SECRET_KEY "
                    "(set via environment or .env.production)"
                )
            if not (self.payment_encryption_key or "").strip():
                raise ValueError(
                    "APP_ENV=prod requires PAYMENT_ENCRYPTION_KEY (generate one "
                    "with: python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\"). Losing it makes "
                    "every saved payment secret unreadable."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def settings_refresh() -> Settings:
    """Reset cache (used by tests to change configuration per test run)."""
    get_settings.cache_clear()
    return get_settings()
