"""Identity HTTP routes: bootstrap, auth, users, roles, audit listing."""
from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthError, ForbiddenError, NotFoundError
from app.core.security import create_access_token, decode_token, verify_password
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity import service as svc
from app.modules.identity.dependencies import (
    CompanyCtx,
    UserCtx,
    current_company_ctx,
    current_user,
    guard,
)
from app.modules.identity.models import RefreshSession, Role, User, UserCompany
from app.modules.identity.schemas import (
    CompanySummary,
    LoginIn,
    LoginOut,
    MeOut,
    RegisterAdminIn,
    RoleCreateIn,
    RoleOut,
    UserCreateIn,
    UserUpdateIn,
    UserOut,
)
from app.core.permissions import ALL_PERMISSIONS, ROLE_TEMPLATES, role_label

router = APIRouter()


@router.post("/auth/bootstrap", response_model=LoginOut, status_code=201)
def bootstrap(payload: RegisterAdminIn, session: Session = Depends(get_db)):
    """Create the very first platform admin. Disabled once any user exists."""
    if svc.has_any_user(session):
        raise ForbiddenError("Bootstrap already completed")
    user = svc.bootstrap_platform_admin(
        session, email=payload.email, password=payload.password, full_name=payload.full_name
    )
    svc.ensure_system_roles(session)
    access = create_access_token(user.id)
    return LoginOut(access_token=access, expires_in=get_settings().access_token_ttl_minutes * 60, user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, response: Response, session: Session = Depends(get_db)):
    user = svc.get_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthError("invalid_credentials", "Invalid email or password", status_code=401)
    if not user.is_active:
        raise AuthError("user_inactive", "Account is inactive")
    refresh, _ = svc.create_refresh_session(session, user)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "prod",
        max_age=get_settings().refresh_token_ttl_days * 86400,
        path="/api/v1/auth",
    )
    log_action(
        session, action="auth.login", entity_type="user", entity_id=user.id, actor_user_id=user.id
    )
    return LoginOut(access_token=create_access_token(user.id), expires_in=get_settings().access_token_ttl_minutes * 60, user=UserOut.model_validate(user))


@router.post("/auth/refresh", response_model=LoginOut)
def refresh(request: Request, response: Response, session: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise AuthError("missing_refresh", "No refresh token cookie")
    user, access, new_refresh = svc.rotate_refresh_token(session, token)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "prod",
        max_age=get_settings().refresh_token_ttl_days * 86400,
        path="/api/v1/auth",
    )
    return LoginOut(access_token=access, expires_in=get_settings().access_token_ttl_minutes * 60, user=UserOut.model_validate(user))


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: UserCtx = Depends(current_user),
    session: Session = Depends(get_db),
):
    """Revoke the presented refresh session (if still valid) and clear cookie."""
    from datetime import datetime, timezone

    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = decode_token(token, expected_type="refresh")
        except AuthError:
            payload = None  # already expired/invalid — still clear the cookie
        if payload:
            stmt = select(RefreshSession).where(
                RefreshSession.jti == payload.get("session_jti")
            )
            sess = session.execute(stmt).scalar_one_or_none()
            if sess is not None:
                sess.revoked_at = datetime.now(timezone.utc)
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return Response(status_code=204)


@router.get("/auth/me", response_model=MeOut)
def me(
    ctx: CompanyCtx = Depends(current_company_ctx),
    session: Session = Depends(get_db),
):
    memberships = session.execute(
        select(UserCompany, UserCompany.company_id).where(UserCompany.user_id == ctx.user.id)
    ).all()
    companies = [CompanySummary(id=company_id, name="", base_currency="") for _, company_id in memberships]
    if ctx.user.is_platform_admin:
        companies = []
        from app.modules.companies.service import list_all_companies
        for c in list_all_companies(session):
            companies.append(CompanySummary(id=c.id, name=c.name, base_currency=c.base_currency))
    return MeOut(
        user=UserOut(id=ctx.user.id, email=ctx.user.email, full_name=ctx.user.full_name, is_platform_admin=ctx.user.is_platform_admin, is_active=True),
        companies=companies,
        permissions=sorted(ctx.permissions),
        is_company_admin=ctx.is_company_admin,
        roles=sorted(ctx.roles),
    )


@router.get("/auth/permissions", response_model=dict)
def permissions_catalog():
    return {"permissions": ALL_PERMISSIONS, "roles": sorted(svc_role_names())}


def svc_role_names():
    from app.core.permissions import ROLE_TEMPLATES
    return list(ROLE_TEMPLATES.keys())


# ---- users (platform admin) ----
@router.get("/users", response_model=list[UserOut])
def list_users(
    _: CompanyCtx = Depends(guard("platform.users.manage")), session: Session = Depends(get_db)
):
    import json as _json

    users = session.execute(select(User).order_by(User.email)).scalars().all()
    role_map: dict[str, set[str]] = {}
    if users:
        rows = session.execute(
            select(UserCompany).where(UserCompany.user_id.in_([u.id for u in users]))
        ).scalars().all()
        for row in rows:
            role_map.setdefault(row.user_id, set()).update(_json.loads(row.role_names))
    out: list[UserOut] = []
    for user in users:
        item = UserOut.model_validate(user)
        item.roles = sorted(role_map.get(user.id, set()))
        out.append(item)
    return out


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreateIn,
    ctx: CompanyCtx = Depends(guard("platform.users.manage")),
    session: Session = Depends(get_db),
):
    role_names = svc.validate_role_names(session, payload.role_names)
    user = svc.create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        is_platform_admin=payload.is_platform_admin,
    )
    if payload.company_id:
        from app.modules.companies import service as companies_svc

        companies_svc.grant_membership(
            session,
            company_id=payload.company_id,
            user_id=user.id,
            is_company_admin=payload.is_company_admin,
            role_names=role_names,
        )
    log_action(session, action="user.created", entity_type="user", entity_id=user.id, actor_user_id=ctx.user.id)
    out = UserOut.model_validate(user)
    out.roles = role_names
    return out


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: str,
    payload: UserUpdateIn,
    ctx: CompanyCtx = Depends(guard("platform.users.manage")),
    session: Session = Depends(get_db),
):
    user = svc.update_user(
        session,
        user_id,
        full_name=payload.full_name,
        is_active=payload.is_active,
        is_platform_admin=payload.is_platform_admin,
        password=payload.password,
    )
    log_action(session, action="user.updated", entity_type="user", entity_id=user.id, actor_user_id=ctx.user.id)
    return UserOut.model_validate(user)


# ---- roles ----
@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: UserCtx = Depends(current_user), session: Session = Depends(get_db)):
    """List assignable roles.

    Readable by any authenticated user so membership UIs can populate role
    pickers; a system role's empty permission set falls back to its template.
    """
    import json as _json

    svc.ensure_system_roles(session)
    roles = session.execute(select(Role).order_by(Role.name)).scalars().all()
    return [
        RoleOut(
            id=r.id,
            name=r.name,
            label=role_label(r.name),
            permissions=_json.loads(r.permissions) or list(ROLE_TEMPLATES.get(r.name, [])),
            is_system=r.is_system,
        )
        for r in roles
    ]


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    payload: RoleCreateIn,
    ctx: CompanyCtx = Depends(guard("platform.users.manage")),
    session: Session = Depends(get_db),
):
    from app.core.exceptions import ConflictError

    svc.ensure_system_roles(session)
    if session.scalar(select(Role.id).where(Role.name == payload.name)):
        raise ConflictError("ROLE_EXISTS", "Role name already exists")
    unknown = set(payload.permissions) - set(ALL_PERMISSIONS)
    if unknown:
        raise NotFoundError(f"Unknown permissions: {sorted(unknown)}")
    import json as _json
    role = Role(name=payload.name, permissions=_json.dumps(sorted(payload.permissions)), is_system=False)
    session.add(role)
    session.flush()
    log_action(session, action="role.created", entity_type="role", entity_id=role.id, actor_user_id=ctx.user.id)
    return RoleOut(id=role.id, name=role.name, label=role_label(role.name), permissions=payload.permissions, is_system=False)
