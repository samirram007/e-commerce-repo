"""Catalog HTTP routes: categories, UoM, products, price lists."""
import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import P_CATALOG_MANAGE, P_CATALOG_VIEW, P_FILES_UPLOAD
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.catalog import service as svc
from app.modules.catalog.models import PriceListItem, Product
from app.modules.identity.dependencies import CompanyCtx, guard
from app.shared.files import save_file

router = APIRouter()


# ---- schemas ----
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    parent_id: str | None


class UomIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=50)


class UomOut(BaseModel):
    id: str
    code: str
    name: str


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = None
    uom_id: str | None = None
    barcode: str | None = Field(default=None, max_length=64)
    # HSN (goods) / SAC (services) code printed on GST invoices
    hsn_sac: str | None = Field(default=None, max_length=12)
    stock_type: str = "stock"
    track_batches: bool = False
    track_serials: bool = False
    base_cost: Decimal = Decimal("0")
    base_price: Decimal = Decimal("0")
    # shipping: third-party carriers rate a parcel by weight and size
    weight_kg: Decimal | None = Field(default=None, ge=0)
    length_cm: Decimal | None = Field(default=None, ge=0)
    width_cm: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    default_tax_rate_id: str | None = None
    is_active: bool = True
    is_sellable: bool = True
    is_purchasable: bool = True


class ProductUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: str | None = None
    uom_id: str | None = None
    barcode: str | None = None
    hsn_sac: str | None = None
    stock_type: str | None = None
    track_batches: bool | None = None
    track_serials: bool | None = None
    base_cost: Decimal | None = None
    base_price: Decimal | None = None
    weight_kg: Decimal | None = Field(default=None, ge=0)
    length_cm: Decimal | None = Field(default=None, ge=0)
    width_cm: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    default_tax_rate_id: str | None = None
    is_active: bool | None = None
    is_sellable: bool | None = None
    is_purchasable: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    name: str
    description: str | None
    category_id: str | None
    uom_id: str | None
    barcode: str | None
    hsn_sac: str | None
    stock_type: str
    track_batches: bool
    track_serials: bool
    base_cost: Decimal
    base_price: Decimal
    # shipping (used when a third-party carrier rates the parcel)
    weight_kg: Decimal | None = None
    length_cm: Decimal | None = None
    width_cm: Decimal | None = None
    height_cm: Decimal | None = None
    default_tax_rate_id: str | None
    image_file_id: str | None
    is_active: bool
    is_sellable: bool
    is_purchasable: bool


class PriceIn(BaseModel):
    product_id: str
    price: Decimal = Field(gt=0)
    effective_from: datetime.date | None = None


# ---- categories ----
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(ctx: CompanyCtx = Depends(guard(P_CATALOG_VIEW)), session: Session = Depends(get_db)):
    return [CategoryOut(id=c.id, name=c.name, parent_id=c.parent_id) for c in svc.list_categories(session, ctx.company_id)]


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryIn, ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE)), session: Session = Depends(get_db)):
    c = svc.create_category(session, company_id=ctx.company_id, name=payload.name, parent_id=payload.parent_id)
    return CategoryOut(id=c.id, name=c.name, parent_id=c.parent_id)


# ---- UoM ----
@router.get("/uoms", response_model=list[UomOut])
def list_uoms(ctx: CompanyCtx = Depends(guard(P_CATALOG_VIEW)), session: Session = Depends(get_db)):
    from app.modules.catalog.models import UnitOfMeasure
    from sqlalchemy import select

    rows = session.execute(select(UnitOfMeasure).where(UnitOfMeasure.company_id == ctx.company_id).order_by(UnitOfMeasure.code)).scalars().all()
    return [UomOut(id=u.id, code=u.code, name=u.name) for u in rows]


@router.post("/uoms", response_model=UomOut, status_code=201)
def create_uom(payload: UomIn, ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE)), session: Session = Depends(get_db)):
    u = svc.create_uom(session, company_id=ctx.company_id, code=payload.code, name=payload.name)
    return UomOut(id=u.id, code=u.code, name=u.name)


# ---- products ----
@router.get("/products")
def list_products(
    search: str | None = None,
    category_id: str | None = None,
    stock_type: str | None = None,
    is_active: bool | None = None,
    ctx: CompanyCtx = Depends(guard(P_CATALOG_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.list_products(
        session,
        ctx.company_id,
        search=search,
        category_id=category_id,
        stock_type=stock_type,
        is_active=is_active,
    )
    return {"items": [ProductOut.model_validate(p) for p in rows], "total": len(rows), "page": 1, "page_size": len(rows)}


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str, ctx: CompanyCtx = Depends(guard(P_CATALOG_VIEW)), session: Session = Depends(get_db)):
    return ProductOut.model_validate(svc.get_product(session, ctx.company_id, product_id))


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE)), session: Session = Depends(get_db)):
    product = svc.create_product(session, company_id=ctx.company_id, actor_user_id=ctx.user.id, data=payload.model_dump())
    log_action(session, action="product.created", entity_type="product", entity_id=product.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"sku": product.sku})
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdateIn, ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE)), session: Session = Depends(get_db)):
    product = svc.get_product(session, ctx.company_id, product_id)
    before = {"base_price": str(product.base_price), "is_active": product.is_active}
    product = svc.update_product(session, product, payload.model_dump(exclude_unset=True))
    log_action(session, action="product.updated", entity_type="product", entity_id=product.id, actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data=before)
    return ProductOut.model_validate(product)


@router.post("/products/{product_id}/image")
def upload_product_image(
    product_id: str,
    file: UploadFile,
    ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE, P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    product = svc.get_product(session, ctx.company_id, product_id)
    record = save_file(
        session,
        file,
        company_id=ctx.company_id,
        purpose="product_image",
        created_by=ctx.user.id,
        allowed_types={"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"},
    )
    product.image_file_id = record.id
    session.flush()
    return {"file_id": record.id, "product_id": product.id}


# ---- price list ----
@router.post("/price-lists/{price_list_id}/prices")
def set_price(price_list_id: str, payload: PriceIn, ctx: CompanyCtx = Depends(guard(P_CATALOG_MANAGE)), session: Session = Depends(get_db)):
    row = svc.set_price(
        session,
        price_list_id=price_list_id,
        product_id=svc.get_product(session, ctx.company_id, payload.product_id).id,
        price=payload.price,
        effective_from=payload.effective_from.date() if payload.effective_from else None,
    )
    return {"id": row.id, "price": str(row.price), "effective_from": str(row.effective_from)}
