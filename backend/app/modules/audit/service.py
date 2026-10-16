"""Audit service: append-only logging of significant actions.

Sensitive data (passwords, tokens, full payment data) is never written here —
callers pass entity ids and small before/after summaries only.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import AuditLog


def log_action(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None,
    actor_user_id: str | None,
    company_id: str | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> AuditLog:
    """Write one audit record within the caller's transaction (no extra commit)."""
    trimmed_before = _trim(before_data)
    trimmed_after = _trim(after_data)
    record = AuditLog(
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=_dumps(trimmed_before),
        after_data=_dumps(trimmed_after),
        created_by_ref=actor_user_id,
    )
    session.add(record)
    session.flush()
    return record


def _trim(data: dict | None) -> dict | None:
    if data is None:
        return None
    clean: dict = {}
    for key, value in list(data.items())[:20]:
        if any(secret in key.lower() for secret in ("password", "token", "secret", "card", "cvv")):
            clean[key] = "<redacted>"
        else:
            clean[key] = value
    return clean


def _dumps(data: dict | None) -> str | None:
    if data is None:
        return None
    try:
        return json.dumps(data, default=str)[:2000]
    except (TypeError, ValueError):
        return str(data)[:2000]


def list_audit(
    session: Session, *, company_id: str | None, limit: int = 200, offset: int = 0
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(offset)
    if company_id is not None:
        stmt = stmt.where(AuditLog.company_id == company_id)
    return list(session.execute(stmt).scalars())
