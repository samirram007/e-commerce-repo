"""Auth/authorization FastAPI dependencies.

`current_user` decodes and validates the Bearer access token.
`current_company_ctx` resolves the active company from the X-Company-Id header,
verifying that the user is an authorized member (or platform admin). It also
exposes `permissions` and rejects requests that pass a company context they do
not have access to (IDOR protection at the request level).
`require_permissions` turns the resolved context into an enforcement gate.
"""
from typing import NamedTuple

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.unit_of_work import get_db
from app.modules.identity import service as identity_service
from app.modules.identity.models import User, UserCompany


class UserCtx(NamedTuple):
    id: str
    email: str
    full_name: str
    is_platform_admin: bool


class CompanyCtx(NamedTuple):
    user: UserCtx
    company_id: str | None
    is_company_admin: bool
    permissions: set[str]
    roles: set[str] = set()  # assignable role names granted for the active company


def current_user(request: Request, session: Session = Depends(get_db)) -> UserCtx:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("missing_token", "Missing bearer token")
    payload = decode_token(auth[7:], expected_type="access")
    user = session.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise AuthError("user_inactive", "Account not found or inactive")
    return UserCtx(
        id=user.id, email=user.email, full_name=user.full_name, is_platform_admin=user.is_platform_admin
    )


def current_company_ctx(
    session: Session = Depends(get_db),
    user: UserCtx = Depends(current_user),
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
) -> CompanyCtx:
    company_id = x_company_id
    is_admin = False
    roles: set[str] = set()
    if company_id:
        membership = session.scalar(
            select(UserCompany).where(
                UserCompany.user_id == user.id, UserCompany.company_id == company_id
            )
        )
        is_admin = membership is not None and bool(membership.is_company_admin)
        if membership is None and not user.is_platform_admin:
            raise ForbiddenError("You do not have access to this company")
        perms = identity_service.permissions_for(session, session.get(User, user.id), company_id)
        roles = identity_service.roles_for(session, session.get(User, user.id), company_id)
    else:
        perms = identity_service.permissions_for(session, session.get(User, user.id), None)
        roles = identity_service.roles_for(session, session.get(User, user.id), None)
    return CompanyCtx(
        user=user,
        company_id=company_id,
        is_company_admin=is_admin,
        permissions=perms,
        roles=roles,
    )


def require_permissions(perms: tuple[str, ...]):
    def checker(ctx: CompanyCtx = Depends(current_company_ctx)) -> CompanyCtx:
        if not ctx.company_id and not ctx.user.is_platform_admin and "*" not in ctx.permissions:
            raise ForbiddenError("Company context required")
        if "*" in ctx.permissions or ctx.user.is_platform_admin:
            return ctx
        missing = [p for p in perms if p not in ctx.permissions]
        if missing:
            raise ForbiddenError(f"Missing required permission: {', '.join(missing)}")
        return ctx

    return checker


def guard(*permission_names: str):
    """Router-friendly dependency factory: use as Depends(guard("perm"))."""
    return require_permissions(permission_names)


def require_roles(*role_names: str):
    """Dependency factory that gates on an assignable role (admins bypass).

    A user satisfies the gate when they hold *any* of the listed roles for the
    active company. Platform admins and company admins are treated as holding
    every role.
    """

    def checker(ctx: CompanyCtx = Depends(current_company_ctx)) -> CompanyCtx:
        if not ctx.company_id and not ctx.user.is_platform_admin:
            raise ForbiddenError("Company context required")
        if ctx.user.is_platform_admin or ctx.is_company_admin or "*" in ctx.permissions:
            return ctx
        if not role_names or ctx.roles.intersection(role_names):
            return ctx
        raise ForbiddenError(f"Missing required role: {', '.join(role_names)}")

    return checker


def guard_role(*role_names: str):
    """Router-friendly role gate: use as Depends(guard_role("admin"))."""
    return require_roles(*role_names)


def guard_any(*permission_names: str, roles: tuple[str, ...] = ()):
    """Gate satisfied by ANY listed permission OR ANY listed role (admins bypass).

    Use as `Depends(guard_any(P_MEMBERS_MANAGE, roles=("admin", "developer")))`.
    """

    def checker(ctx: CompanyCtx = Depends(current_company_ctx)) -> CompanyCtx:
        if not ctx.company_id and not ctx.user.is_platform_admin:
            raise ForbiddenError("Company context required")
        if ctx.user.is_platform_admin or ctx.is_company_admin or "*" in ctx.permissions:
            return ctx
        if all(p in ctx.permissions for p in permission_names):
            return ctx
        if roles and ctx.roles.intersection(roles):
            return ctx
        missing = [p for p in permission_names if p not in ctx.permissions]
        if missing:
            raise ForbiddenError(f"Missing required permission: {', '.join(missing)}")
        raise ForbiddenError(f"Missing required role: {', '.join(roles)}")

    return checker
