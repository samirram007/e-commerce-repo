"""Company service: CRUD, membership grants, exchange rates."""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import new_id
from app.modules.companies.models import Company, ExchangeRate
from app.modules.identity.models import UserCompany


def create_company(
    session: Session,
    *,
    name: str,
    legal_name: str = "",
    base_currency: str = "INR",
    timezone: str = "UTC",
    locale: str = "en-IN",
    address: str | None = None,
    tax_identifier: str | None = None,
    owner_user_id: str,
    addresses: list[CompanyAddressIn] | None = None,
) -> Company:
    from app.modules.accounting.service import create_default_chart

    existing = session.scalar(select(Company.id).where(Company.name == name))
    if existing is not None:
        raise ConflictError("COMPANY_EXISTS", f"A company named '{name}' already exists")
    from app.modules.companies.service import ensure_currency

    ensure_currency(session, base_currency)
    company = Company(
        name=name,
        legal_name=legal_name or name,
        base_currency=base_currency,
        timezone=timezone,
        locale=locale,
        address=address,
        tax_identifier=tax_identifier,
        created_by=owner_user_id,
    )
    session.add(company)
    session.flush()
    # Handle addresses if provided
    if addresses:
        for addr in addresses:
            from app.modules.companies.models import CompanyAddress
            company_address = CompanyAddress(
                company_id=company.id,
                address_type=addr.address_type,
                line1=addr.line1,
                line2=addr.line2,
                city=addr.city,
                region=addr.region,
                postal_code=addr.postal_code,
                country=addr.country,
                tax_identifier=addr.tax_identifier,
                is_default=addr.is_default,
            )
            session.add(company_address)
    create_default_chart(session, company=company)
    membership = UserCompany(
        user_id=owner_user_id, company_id=company.id, is_company_admin=True, role_names="[]"
    )
    session.add(membership)
    session.flush()
    return company


def list_companies_for_user(session: Session, user_id: str) -> list[Company]:
    memberships = session.execute(
        select(UserCompany).where(UserCompany.user_id == user_id)
    ).scalars().all()
    ids = [m.company_id for m in memberships]
    if not ids:
        return []
    return list(session.execute(select(Company).where(Company.id.in_(ids))).scalars())


def list_all_companies(session: Session) -> list[Company]:
    return list(session.execute(select(Company).order_by(Company.name)).scalars())


def get_company(session: Session, company_id: str) -> Company:
    company = session.get(Company, company_id)
    if company is None or not company.is_active:
        raise NotFoundError("Company")
    return company


def update_company(session: Session, company: Company, updates: dict) -> Company:
    addresses = updates.pop("addresses", None)
    for field, value in updates.items():
        if value is not None:
            setattr(company, field, value)
    session.flush()
    # Handle address updates
    if addresses is not None:
        # Remove existing addresses not in the new list
        from app.modules.companies.models import CompanyAddress
        existing = session.execute(
            select(CompanyAddress).where(CompanyAddress.company_id == company.id)
        ).scalars().all()
        existing_ids = {a.id for a in existing}
        new_ids = set()
        for addr_data in addresses:
            # Need to identify existing vs new; for now replace all
            if addr_data.id and addr_data.id in existing_ids:
                new_ids.add(addr_data.id)
                # Update existing
                existing_addr = session.get(CompanyAddress, addr_data.id)
                if existing_addr:
                    existing_addr.address_type = addr_data.address_type
                    existing_addr.line1 = addr_data.line1
                    existing_addr.line2 = addr_data.line2
                    existing_addr.city = addr_data.city
                    existing_addr.region = addr_data.region
                    existing_addr.postal_code = addr_data.postal_code
                    existing_addr.country = addr_data.country
                    existing_addr.tax_identifier = addr_data.tax_identifier
                    existing_addr.is_default = addr_data.is_default
            else:
                # New address - add it
                new_addr = CompanyAddress(
                    company_id=company.id,
                    address_type=addr_data.address_type,
                    line1=addr_data.line1,
                    line2=addr_data.line2,
                    city=addr_data.city,
                    region=addr_data.region,
                    postal_code=addr_data.postal_code,
                    country=addr_data.country,
                    tax_identifier=addr_data.tax_identifier,
                    is_default=addr_data.is_default,
                )
                session.add(new_addr)
                new_ids.add(new_addr.id)
        # Delete addresses not in the new list
        for addr in existing:
            if addr.id not in new_ids:
                session.delete(addr)
        session.flush()
    return company


def grant_membership(
    session: Session, *, company_id: str, user_id: str, is_company_admin: bool, role_names: list[str]
) -> UserCompany:
    existing = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id
        )
    )
    if existing is not None:
        raise ConflictError("MEMBER_EXISTS", "User is already a member of this company")
    membership = UserCompany(
        user_id=user_id,
        company_id=company_id,
        is_company_admin=is_company_admin,
        role_names=json.dumps(role_names),
    )
    session.add(membership)
    session.flush()
    return membership


def update_membership(
    session: Session, *, company_id: str, user_id: str, is_company_admin: bool | None, role_names: list[str] | None
) -> UserCompany:
    membership = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id
        )
    )
    if membership is None:
        raise NotFoundError("Membership")
    if is_company_admin is not None:
        membership.is_company_admin = is_company_admin
    if role_names is not None:
        membership.role_names = json.dumps(role_names)
    session.flush()
    return membership


def revoke_membership(session: Session, *, company_id: str, user_id: str) -> None:
    membership = session.scalar(
        select(UserCompany).where(
            UserCompany.user_id == user_id, UserCompany.company_id == company_id
        )
    )
    if membership is None:
        raise NotFoundError("Membership")
    session.delete(membership)
    session.flush()


def list_members(session: Session, company_id: str) -> list[tuple[UserCompany, str]]:
    rows = session.execute(
        select(UserCompany).where(UserCompany.company_id == company_id)
    ).scalars().all()
    email_map: dict[str, str] = {}
    if rows:
        from app.modules.identity.models import User

        user_ids = [r.user_id for r in rows]
        for u in session.execute(select(User).where(User.id.in_(user_ids))).scalars():
            email_map[u.id] = u.email
    return [(r, email_map.get(r.user_id)) for r in rows]


def ensure_currency(session: Session, code: str, name: str = "", precision: int = 2) -> None:
    from app.modules.companies.models import Currency

    if session.get(Currency, code) is None:
        session.add(Currency(code=code, name=name or code, precision=precision))
        session.flush()


def set_exchange_rate(
    session: Session, *, company_id: str, from_currency: str, rate_date: date, rate
) -> ExchangeRate:
    from app.modules.companies.models import Currency

    if session.get(Currency, from_currency) is None:
        raise NotFoundError("Currency")
    row = session.scalar(
        select(ExchangeRate).where(
            ExchangeRate.company_id == company_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.rate_date == rate_date,
        )
    )
    if row is None:
        row = ExchangeRate(
            company_id=company_id, from_currency=from_currency, to_currency="BASE", rate_date=rate_date
        )
        session.add(row)
    row.rate = rate
    row.company_id = company_id
    session.flush()
    return row


def rate_for(session: Session, *, company_id: str, from_currency: str, base_currency: str, on_date: date) -> float:
    """Latest known rate on/on before `on_date`; 1.0 when same currency."""
    if from_currency == base_currency:
        return 1.0
    row = session.scalar(
        select(ExchangeRate)
        .where(
            ExchangeRate.company_id == company_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.rate_date <= on_date,
        )
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    if row is None:
        raise BusinessRuleError(
            "MISSING_EXCHANGE_RATE",
            f"No exchange rate for {from_currency}->{base_currency} on/before {on_date}",
        )
    return float(row.rate)
