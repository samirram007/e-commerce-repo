"""Identity models: users, roles, company memberships, refresh sessions."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # JSON list of permission strings; empty means use ROLE_TEMPLATES[name]
    permissions: Mapped[str] = mapped_column(String(4000), nullable=False, default="[]")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserCompany(Base, TimestampMixin):
    """Explicit per-company access grant; no implicit tenant access."""
    __tablename__ = "user_companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    is_company_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role_names: Mapped[str] = mapped_column(String(500), nullable=False, default="[]")

    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_user_companies_pair"),)


class RefreshSession(Base, TimestampMixin):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class UserPreference(Base, TimestampMixin):
    """Signed-in user's personal display preferences (theme, accent color).

    One row per user; company-agnostic because these are device-agnostic
    look-and-feel choices, not tenant-scoped business settings.
    """

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # light | dark | system
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    # hex accent color, e.g. #2f54eb
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="")
    # compact | comfortable — table/control density
    density: Mapped[str] = mapped_column(String(16), nullable=False, default="comfortable")


class AuditLog(Base, TimestampMixin):
    """Append-only audit trail for significant actions (identity keeps it so
    the audit module has no import cycle; writes go through audit.log_action)."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    before_data: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    after_data: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
