"""Partners HTTP routes: customers, vendors, addresses."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.permissions import P_PARTNERS_MANAGE
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.partners import service as svc
from app.modules.partners.models import Customer, Vendor

router = APIRouter()


class CustomerIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    phone: str | None = None
    tax_identifier: str | None = None
    payment_term_days: int = 0
    credit_limit: Decimal = Decimal("0")
    user_id: str | None = None
    is_active: bool = True
    notes: str | None = None


class CustomerUpdateIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_identifier: str | None = None
    payment_term_days: int | None = None
    credit_limit: Decimal | None = None
    is_active: bool | None = None
    notes: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    email: str | None
    phone: str | None
    tax_identifier: str | None
    payment_term_days: int
    credit_limit: Decimal
    is_active: bool
    notes: str | None


class VendorIn(CustomerIn):
    pass


class VendorUpdateIn(CustomerUpdateIn):
    pass


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    email: str | None
    phone: str | None
    tax_identifier: str | None
    payment_term_days: int
    is_active: bool
    notes: str | None


class AddressIn(BaseModel):
    address_type: str = "billing"
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    is_default: bool = False


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    partner_type: str
    partner_id: str
    address_type: str
    line1: str
    line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country: str | None
    is_default: bool


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(search: str | None = None, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    return [CustomerOut.model_validate(c) for c in svc.list_customers(session, ctx.company_id, search=search)]


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerIn, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    customer = svc.create_customer(session, company_id=ctx.company_id, actor_user_id=ctx.user.id, data=payload.model_dump())
    log_action(session, action="customer.created", entity_type="customer", entity_id=customer.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"code": customer.code})
    return CustomerOut.model_validate(customer)


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    return CustomerOut.model_validate(svc.get_customer(session, ctx.company_id, customer_id))


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: str, payload: CustomerUpdateIn, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    customer = svc.get_customer(session, ctx.company_id, customer_id)
    customer = svc.update_customer(session, customer, payload.model_dump(exclude_unset=True))
    log_action(session, action="customer.updated", entity_type="customer", entity_id=customer.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return CustomerOut.model_validate(customer)


@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(search: str | None = None, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    return [VendorOut.model_validate(v) for v in svc.list_vendors(session, ctx.company_id, search=search)]


@router.post("/vendors", response_model=VendorOut, status_code=201)
def create_vendor(payload: VendorIn, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    vendor = svc.create_vendor(session, company_id=ctx.company_id, actor_user_id=ctx.user.id, data=payload.model_dump())
    log_action(session, action="vendor.created", entity_type="vendor", entity_id=vendor.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"code": vendor.code})
    return VendorOut.model_validate(vendor)


@router.get("/vendors/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    return VendorOut.model_validate(svc.get_vendor(session, ctx.company_id, vendor_id))


@router.patch("/vendors/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: str, payload: VendorUpdateIn, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    vendor = svc.get_vendor(session, ctx.company_id, vendor_id)
    vendor = svc.update_vendor(session, vendor, payload.model_dump(exclude_unset=True))
    log_action(session, action="vendor.updated", entity_type="vendor", entity_id=vendor.id, actor_user_id=ctx.user.id, company_id=ctx.company_id)
    return VendorOut.model_validate(vendor)


@router.post("/addresses", response_model=AddressOut, status_code=201)
def add_address(
    partner_type: str,
    partner_id: str,
    payload: AddressIn,
    ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)),
    session: Session = Depends(get_db),
):
    svc.get_customer_or_vendor(session, ctx.company_id, partner_type, partner_id)
    address = svc.add_address(
        session, company_id=ctx.company_id, partner_type=partner_type, partner_id=partner_id, data=payload.model_dump()
    )
    return AddressOut.model_validate(address)


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(partner_type: str, partner_id: str, ctx: CompanyCtx = Depends(guard(P_PARTNERS_MANAGE)), session: Session = Depends(get_db)):
    svc.get_customer_or_vendor(session, ctx.company_id, partner_type, partner_id)
    return [AddressOut.model_validate(a) for a in svc.list_addresses(session, ctx.company_id, partner_type, partner_id)]
