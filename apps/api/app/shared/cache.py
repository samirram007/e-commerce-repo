"""Backend cache abstraction — application code never calls Redis directly.

Strategy (AGENT.md §7.2): only stable reference data and expensive reports are
cached, always keyed with company/fiscal-year scope; TTL is a safety net and
invalidation happens after commit via explicit `invalidate_version` calls.
If Redis is unreachable the cache degrades to no-op (database reads remain
authoritative). Stock, balances, permissions and fiscal status are NOT cached
by default.
"""
import json
import logging
from typing import Any

logger = logging.getLogger("erp.cache")

try:  # optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

_client: Any = None
_enabled: bool = False


def init_cache() -> None:
    from app.core.config import get_settings

    global _client, _enabled
    settings = get_settings()
    _enabled = settings.cache_enable and redis is not None
    if _enabled:
        try:
            _client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
            _client.ping()
        except Exception as exc:  # degrade safely
            logger.warning("Redis unavailable; cache disabled (%s)", exc)
            _client, _enabled = None, False


def _scoped_key(key: str) -> str:
    return f"erp:v1:{key}"


def get_json(key: str) -> Any | None:
    if not _enabled:
        return None
    try:
        raw = _client.get(_scoped_key(key))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set_json(key: str, value: Any, ttl_seconds: int = 300) -> None:
    if not _enabled:
        return
    try:
        _client.setex(_scoped_key(key), ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.warning("cache set failed (ignored): %s", key)


def bump_version(scope: str) -> None:
    """Invalidate by versioning: expire any data derived from `scope` next read."""
    if not _enabled:
        return
    try:
        _client.incr(_scoped_key(f"ver:{scope}"))
    except Exception:
        logger.warning("cache bump failed (ignored): %s", scope)


def version_of(scope: str) -> str:
    if not _enabled:
        return "0"
    try:
        return str(_client.get(_scoped_key(f"ver:{scope}")) or "0")
    except Exception:
        return "0"


def build_key(*parts: Any, scope_version: str | None = None) -> str:
    parts_str = ":".join(str(p) for p in parts)
    if scope_version is not None:
        return f"{parts_str}:v{scope_version}"
    return parts_str
