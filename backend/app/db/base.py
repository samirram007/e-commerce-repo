"""Declarative base, mixins, and model registration.

All models must be imported here so that Alembic autogenerate sees the full
metadata. Models across modules reference each other only via FK of primary
keys (string UUIDs) — never via cross-module ORM relationships, to avoid
circular imports.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class PKMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=utcnow, nullable=True
    )


class CreatedByMixin:
    """Records the acting user for audit purposes."""
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    blamable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DescMixin:
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


def str_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
