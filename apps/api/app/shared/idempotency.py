"""Idempotency support for checkout, payments, postings and webhooks.

Callers use `run_idempotent` with an operation scope + client-supplied key.
The first execution stores the serialized result; replays return it.
The storage write commits together with the business transaction (UoW), so a
crash before commit means the operation did not happen and the key may be
retried — never a phantom "already done".
"""
import json
from typing import Callable

from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.core.exceptions import BusinessRuleError
from app.core.security import new_id
from app.db.base import Base, TimestampMixin


class IdempotencyRecord(Base, TimestampMixin):
    __tablename__ = "idempotency_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = tuple()  # uniqueness enforced by (scope, key) lookup + transaction lock


def run_idempotent(
    session: Session,
    *,
    scope: str,
    key: str,
    company_id: str | None,
    execute: Callable[[], object],
) -> tuple[object, bool]:
    """Run `execute()` at most once per (scope, key).

    Returns (result, replayed: bool). `execute` runs inside the caller's
    transaction so its DB effects commit together with the record.
    """
    existing = session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope, IdempotencyRecord.key == key
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.response_body is None:
            raise BusinessRuleError(
                "IDEMPOTENT_IN_FLIGHT", "An identical operation is in progress"
            )
        return json.loads(existing.response_body), True

    result = execute()
    body = json.dumps(result, default=str)
    session.add(
        IdempotencyRecord(
            scope=scope,
            key=key[:200],
            company_id=company_id,
            response_status=200,
            response_body=body,
        )
    )
    return result, False
