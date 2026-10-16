"""Identity service: registration/bootstrap, login, sessions, permission resolution.

Authorization is enforced server-side; permission sets are computed from
platform-admin flag, company-admin flag, and role permissions.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, ConflictError, NotFoundError
from app.core.permissions import ROLE_TEMPLATES
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_id,
    verify_password,
)
from app.modules.identity.models import RefreshSession, Role, User, UserCompany


def count_users(session: Session) -> int:
    return session.scalar(select(User.id).limit(1)) is not None and 1 or 0


def has_any_user(session: Session) -> bool:
    return session.scalar(select(User.id).limit(1)) is not None


def bootstrap_platform_admin(session: Session, *, email: str, password: str, full_name: str) -> User:
    if has_any_user(session):
        raise ConflictError("ALREADY_BOOTSTRAPPED", "A platform admin already exists")
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        is_platform_admin=True,
    )
    session.add(user)
    session.flush()
    return user


def create_user(
    session: Session, *, email: str, password: str, full_name: str, is_platform_admin: bool
) -> User:
    email = email.lower()
    if session.scalar(select(User.id).where(User.email == email).limit(1)) is not None:
        raise ConflictError("EMAIL_TAKEN", "A user with this email already exists")
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_platform_admin=is_platform_admin,
    )
    session.add(user)
    session.flush()
    return user


def update_user(
    session: Session,
    user_id: str,
    *,
    full_name: str | None,
    is_active: bool | None,
    is_platform_admin: bool | None,
    password: str | None,
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("User")
    if full_name is not None:
        user.full_name = full_name
    if is_active is not None:
        user.is_active = is_active
    if is_platform_admin is not None:
        user.is_platform_admin = is_platform_admin
    if password:
        user.password_hash = hash_password(password)
    session.flush()
    return user


def get_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.lower()))


def create_refresh_session(
    session: Session, user: User, *, jti_ttl_days: int = 14, user_agent: str | None = None, ip: str | None = None
) -> tuple[str, RefreshSession]:
    jti = new_id() + new_id()
    from app.core.config import get_settings

    sess = RefreshSession(
        user_id=user.id,
        jti=jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=jti_ttl_days),
        user_agent=(user_agent or "")[:255],
        ip=(ip or "")[:64],
    )
    session.add(sess)
    token = create_refresh_token(user.id, jti)
    session.flush()
    return token, sess


def rotate_refresh_token(session: Session, refresh_token: str) -> tuple[User, str, str]:
    """Validate a refresh token, revoke it, and mint a new pair. Returns
    (user, new_access, new_refresh)."""
    payload = decode_token(refresh_token, expected_type="refresh")
    jti = payload.get("session_jti", "")
    sess = session.scalar(select(RefreshSession).where(RefreshSession.jti == jti))
    if sess is None or sess.revoked_at is not None or sess.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise AuthError("invalid_refresh", "Refresh session is invalid or expired", status_code=401)
    user = session.get(User, payload["sub"]) or session.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise AuthError("user_inactive", "Account is inactive", status_code=401)
    sess.revoked_at = datetime.now(timezone.utc)
    new_refresh, _ = create_refresh_session(session, user)
    access = create_access_token(user.id)
    return user, access, new_refresh


def revoke_user_sessions(session: Session, user_id: str) -> None:
    now = datetime.now(timezone.utc)
    stmt = select(RefreshSession).where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
    for sess in session.execute(stmt).scalars():
        sess.revoked_at = now


def list_user_companies(session: Session, user_id: str) -> list[tuple[UserCompany, str, str]]:
    """Returns (membership, company_id, company_name) — company name resolved
    via companies module table through a raw core query to avoid import cycles."""
    rows = session.execute(select(UserCompany).where(UserCompany.user_id == user_id)).scalars().all()
    out = []
    for row in rows:
        out.append((row, row.company_id, row.company_id))
    return out


def permissions_for(session: Session, user: User | None, company_id: str | None) -> set[str]:
    if user is None:
        return set()
    if user.is_platform_admin:
        return {"*"}
    if company_id is None:
        return set()
    membership = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user.id, UserCompany.company_id == company_id
        )
    )
    if membership is None:
        return set()
    if membership.is_company_admin:
        return {"*"}
    perms: set[str] = set()
    role_names: list[str] = json.loads(membership.role_names)
    if role_names:
        roles = session.execute(select(Role).where(Role.name.in_(role_names))).scalars().all()
        for role in roles:
            listed = json.loads(role.permissions)
            if listed:
                perms.update(listed)
            else:
                perms.update(ROLE_TEMPLATES.get(role.name, []))
    return perms


def roles_for(session: Session, user: User | None, company_id: str | None) -> set[str]:
    """Assignable role names held for a company.

    Platform admins are treated as holding every system role; a missing company
    context yields no roles (roles are always company-scoped).
    """
    if user is None:
        return set()
    if user.is_platform_admin:
        return set(ROLE_TEMPLATES)
    if company_id is None:
        return set()
    membership = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user.id, UserCompany.company_id == company_id
        )
    )
    if membership is None:
        return set()
    return {name for name in json.loads(membership.role_names) if name}


def validate_role_names(session: Session, role_names: list[str]) -> list[str]:
    """De-duplicate/sort role names, rejecting any that do not exist."""
    names = sorted({name for name in role_names if name})
    if not names:
        return []
    found = set(session.execute(select(Role.name).where(Role.name.in_(names))).scalars())
    unknown = [name for name in names if name not in found]
    if unknown:
        raise NotFoundError(f"Unknown roles: {', '.join(unknown)}")
    return names


def ensure_system_roles(session: Session) -> None:
    for name in ROLE_TEMPLATES:
        if session.scalar(select(Role.id).where(Role.name == name)) is None:
            session.add(Role(name=name, permissions="[]", is_system=True))
    session.flush()
