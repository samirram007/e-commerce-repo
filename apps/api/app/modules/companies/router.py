"""Company HTTP routes (platform admin creates companies; company admins manage them)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.core.permissions import P_COMPANY_SETTINGS, P_MEMBERS_MANAGE, PRIVILEGED_ROLES
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.companies import service as svc
from app.modules.companies.schemas import (
    CompanyCreateIn,
    CompanyOut,
    CompanyUpdateIn,
    ExchangeRateIn,
    MemberCreateIn,
    MemberOut,
    MemberUpdateIn,
)
from app.modules.identity import service as identity_svc
from app.modules.identity.dependencies import CompanyCtx, current_user, guard, guard_any

router = APIRouter()


@router.get("/companies", response_model=list[CompanyOut])
def list_my_companies(session: Session = Depends(get_db), user=Depends(current_user)):
    companies = svc.list_companies_for_user(session, user.id)
    return [CompanyOut.model_validate(c) for c in companies]


@router.get("/companies/all", response_model=list[CompanyOut])
def list_all_companies(
    session: Session = Depends(get_db), _: object = Depends(guard("platform.users.manage"))
):
    return [CompanyOut.model_validate(c) for c in svc.list_all_companies(session)]


@router.post("/companies", response_model=CompanyOut, status_code=201)
def create_company(
    payload: CompanyCreateIn,
    session: Session = Depends(get_db),
    user=Depends(current_user),
    _: object = Depends(guard("platform.users.manage")),
):
    company = svc.create_company(
        session,
        name=payload.name,
        legal_name=payload.legal_name,
        base_currency=payload.base_currency,
        timezone=payload.timezone,
        locale=payload.locale,
        address=payload.address,
        tax_identifier=payload.tax_identifier,
        owner_user_id=user.id,
    )
    log_action(session, action="company.created", entity_type="company", entity_id=company.id, actor_user_id=user.id)
    return CompanyOut.model_validate(company)


@router.get("/companies/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: str, ctx: CompanyCtx = Depends(guard(P_COMPANY_SETTINGS)), session: Session = Depends(get_db)
):
    _check_scope(ctx, company_id)
    return CompanyOut.model_validate(svc.get_company(session, company_id))


@router.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: str,
    payload: CompanyUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_COMPANY_SETTINGS)),
    session: Session = Depends(get_db),
):
    _check_scope(ctx, company_id)
    company = svc.get_company(session, company_id)
    before = {f: getattr(company, f) for f in payload.model_dump(exclude_unset=True)}
    company = svc.update_company(session, company, payload.model_dump(exclude_unset=True))
    log_action(
        session, action="company.updated", entity_type="company", entity_id=company.id,
        actor_user_id=ctx.user.id, before_data=str(before), after_data=str(payload.model_dump(exclude_unset=True)),
    )
    return CompanyOut.model_validate(company)


def _member_out(session: Session, membership) -> MemberOut:
    import json as _json

    from app.modules.identity.models import User

    user = session.get(User, membership.user_id)
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        email=user.email if user is not None else None,
        is_company_admin=membership.is_company_admin,
        role_names=_json.loads(membership.role_names),
    )


def _assert_may_assign(ctx: CompanyCtx, *, role_names: list[str], is_company_admin: bool | None) -> None:
    """Guard grant/update of elevated access (privileged roles or admin flag).

    A member may freely assign ordinary roles, but only a platform admin, a
    company admin, or an existing Admin/Developer holder may escalate.
    """
    elevated = bool(is_company_admin) or bool(set(role_names) & set(PRIVILEGED_ROLES))
    if not elevated:
        return
    if ctx.user.is_platform_admin or ctx.is_company_admin or ctx.roles.intersection(PRIVILEGED_ROLES):
        return
    raise ForbiddenError(
        "Only a company admin or an Admin/Developer role holder may grant elevated access"
    )


@router.get("/companies/{company_id}/members", response_model=list[MemberOut])
def list_members(
    company_id: str, ctx: CompanyCtx = Depends(guard(P_MEMBERS_MANAGE)), session: Session = Depends(get_db)
):
    _check_scope(ctx, company_id)
    return [_member_out(session, m) for m, _email in svc.list_members(session, company_id)]


@router.post("/companies/{company_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    company_id: str,
    payload: MemberCreateIn,
    ctx: CompanyCtx = Depends(guard_any(P_MEMBERS_MANAGE, roles=("admin", "developer"))),
    session: Session = Depends(get_db),
):
    _check_scope(ctx, company_id)
    role_names = identity_svc.validate_role_names(session, payload.role_names)
    _assert_may_assign(ctx, role_names=role_names, is_company_admin=payload.is_company_admin)
    m = svc.grant_membership(
        session,
        company_id=company_id,
        user_id=payload.user_id,
        is_company_admin=payload.is_company_admin,
        role_names=role_names,
    )
    log_action(session, action="member.granted", entity_type="user_company", entity_id=m.id, actor_user_id=ctx.user.id)
    return _member_out(session, m)


@router.patch("/companies/{company_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    company_id: str,
    user_id: str,
    payload: MemberUpdateIn,
    ctx: CompanyCtx = Depends(guard_any(P_MEMBERS_MANAGE, roles=("admin", "developer"))),
    session: Session = Depends(get_db),
):
    _check_scope(ctx, company_id)
    role_names = (
        identity_svc.validate_role_names(session, payload.role_names)
        if payload.role_names is not None
        else None
    )
    _assert_may_assign(
        ctx, role_names=role_names or [], is_company_admin=payload.is_company_admin
    )
    m = svc.update_membership(
        session,
        company_id=company_id,
        user_id=user_id,
        is_company_admin=payload.is_company_admin,
        role_names=role_names,
    )
    log_action(
        session, action="member.updated", entity_type="user_company", entity_id=m.id,
        actor_user_id=ctx.user.id, company_id=company_id,
    )
    return _member_out(session, m)


@router.delete("/companies/{company_id}/members/{user_id}", status_code=204)
def remove_member(
    company_id: str,
    user_id: str,
    ctx: CompanyCtx = Depends(guard_any(P_MEMBERS_MANAGE, roles=("admin", "developer"))),
    session: Session = Depends(get_db),
):
    _check_scope(ctx, company_id)
    svc.revoke_membership(session, company_id=company_id, user_id=user_id)
    log_action(
        session, action="member.revoked", entity_type="user_company", entity_id=user_id,
        actor_user_id=ctx.user.id, company_id=company_id,
    )
    return Response(status_code=204)


@router.post("/companies/{company_id}/exchange-rates", status_code=200)
def upsert_exchange_rate(
    company_id: str,
    payload: ExchangeRateIn,
    ctx: CompanyCtx = Depends(guard(P_COMPANY_SETTINGS)),
    session: Session = Depends(get_db),
):
    _check_scope(ctx, company_id)
    row = svc.set_exchange_rate(
        session,
        company_id=company_id,
        from_currency=payload.from_currency,
        rate_date=payload.rate_date,
        rate=payload.rate,
    )
    return {"id": row.id, "from_currency": row.from_currency, "rate_date": row.rate_date, "rate": float(row.rate)}


def _check_scope(ctx: CompanyCtx, company_id: str) -> None:
    """Platform admins may act cross-company; others must target their own company."""
    if not ctx.user.is_platform_admin and ctx.permissions != {"*"} and ctx.company_id != company_id:
        raise ForbiddenError("Operating on a different company requires platform administration")
