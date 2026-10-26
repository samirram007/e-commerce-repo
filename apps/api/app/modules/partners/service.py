"""Partners service: customer/vendor CRUD, addresses, balances helpers."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.partners.models import Customer, PartnerAddress, Vendor


# ---- customers ----
def create_customer(session: Session, *, company_id: str, actor_user_id: str, data: dict) -> Customer:
    if session.scalar(select(Customer.id).where(Customer.company_id == company_id, Customer.code == data["code"])):
        raise ConflictError("CODE_TAKEN", f"Customer code '{data['code']}' already exists")
    customer = Customer(company_id=company_id, created_by=actor_user_id, **_filter(data, Customer))
    session.add(customer)
    session.flush()
    return customer


def update_customer(session: Session, customer: Customer, data: dict) -> Customer:
    for key, value in _filter(data, Customer).items():
        setattr(customer, key, value)
    session.flush()
    return customer


def get_customer(session: Session, company_id: str, customer_id: str) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None or customer.company_id != company_id:
        raise NotFoundError("Customer")
    return customer


def get_customer_by_user(session: Session, company_id: str, user_id: str) -> Customer | None:
    return session.scalar(
        select(Customer).where(Customer.company_id == company_id, Customer.user_id == user_id)
    )


def list_customers(session: Session, company_id: str, search: str | None = None):
    stmt = select(Customer).where(Customer.company_id == company_id).order_by(Customer.code)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where((Customer.name.ilike(like)) | (Customer.code.ilike(like)))
    return session.execute(stmt).scalars().all()


# ---- vendors ----
def create_vendor(session: Session, *, company_id: str, actor_user_id: str, data: dict) -> Vendor:
    if session.scalar(select(Vendor.id).where(Vendor.company_id == company_id, Vendor.code == data["code"])):
        raise ConflictError("CODE_TAKEN", f"Vendor code '{data['code']}' already exists")
    vendor = Vendor(company_id=company_id, created_by=actor_user_id, **_filter(data, Vendor))
    session.add(vendor)
    session.flush()
    return vendor


def update_vendor(session: Session, vendor: Vendor, data: dict) -> Vendor:
    for key, value in _filter(data, Vendor).items():
        setattr(vendor, key, value)
    session.flush()
    return vendor


def get_vendor(session: Session, company_id: str, vendor_id: str) -> Vendor:
    vendor = session.get(Vendor, vendor_id)
    if vendor is None or vendor.company_id != company_id:
        raise NotFoundError("Vendor")
    return vendor


def list_vendors(session: Session, company_id: str, search: str | None = None):
    stmt = select(Vendor).where(Vendor.company_id == company_id).order_by(Vendor.code)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where((Vendor.name.ilike(like)) | (Vendor.code.ilike(like)))
    return session.execute(stmt).scalars().all()


# ---- addresses ----
def add_address(session: Session, *, company_id: str, partner_type: str, partner_id: str, data: dict):
    if partner_type not in ("customer", "vendor"):
        raise NotFoundError("partner_type must be customer or vendor")
    address = PartnerAddress(company_id=company_id, partner_type=partner_type, partner_id=partner_id, **_filter(data, PartnerAddress))
    session.add(address)
    session.flush()
    return address


def list_addresses(session: Session, company_id: str, partner_type: str, partner_id: str):
    return list(
        session.execute(
            select(PartnerAddress).where(
                PartnerAddress.company_id == company_id,
                PartnerAddress.partner_type == partner_type,
                PartnerAddress.partner_id == partner_id,
            ).order_by(PartnerAddress.is_default.desc())
        ).scalars()
    )


_ADDRESS_FIELDS = {"address_type", "line1", "line2", "city", "region", "postal_code", "country", "is_default"}


def get_customer_or_vendor(session: Session, company_id: str, partner_type: str, partner_id: str):
    """IDOR guard: resolve+validate either partner type by id."""
    if partner_type == "customer":
        return get_customer(session, company_id, partner_id)
    if partner_type == "vendor":
        return get_vendor(session, company_id, partner_id)
    raise NotFoundError("Unsupported partner type")


def _filter(data: dict, model) -> dict:
    columns = set(model.__table__.columns.keys()) - {"id", "created_at", "updated_at", "company_id", "created_by"}
    return {k: v for k, v in data.items() if k in columns and v is not None}
