"""SQLAlchemy engines/sessions.

SQLite is supported for dev/testing; PostgreSQL is recommended for production.
Currently uses portable SQLAlchemy constructs only; keep dialect-specific SQL
isolated in this module if ever needed.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def engine_kwargs(url: str) -> dict:
    settings = get_settings()
    if url.startswith("sqlite"):
        base: dict = {"connect_args": {"check_same_thread": False}}
    elif url.startswith("postgresql"):
        base = {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_pre_ping": True,
        }
    else:  # e.g. mysql
        base = {"pool_pre_ping": True}
    return {"future": True, **base}


_engine = sessionmaker = None  # type: ignore[assignment]  # placeholder guard


def build_engine(url: str | None = None):
    from sqlalchemy import create_engine

    url = url or get_settings().database_url
    return create_engine(url, **engine_kwargs(url))


_engine_cache: dict[str, sessionmaker] = {}


def get_session_factory(url: str | None = None):
    """Cached sessionmaker keyed by URL (tests may override DATABASE_URL)."""
    from sqlalchemy.orm import sessionmaker as sm

    url = url or get_settings().database_url
    if url not in _engine_cache:
        _engine_cache[url] = sm(bind=build_engine(url), expire_on_commit=False, autoflush=False)
    return _engine_cache[url]
