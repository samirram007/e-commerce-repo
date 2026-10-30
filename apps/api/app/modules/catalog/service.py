"""Catalog service: product CRUD, categories, UoM, price resolution."""
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.catalog.models import (
    Category,
    PriceList,
    PriceListItem,
    Product,
    UnitConversion,
    UnitOfMeasure,
)
from app.shared.money import dec, qty as q4

VALID_STOCK_TYPES = {"stock", "service", "non_inventory"}
#: HSN is 4/6/8 digits, SAC is 6 digits; both are plain digit codes.
HSN_SAC_PATTERN = re.compile(r"^\d{4,8}$")


# ---- categories ----
def create_category(session: Session, *, company_id: str, name: str, parent_id: str | None) -> Category:
    if parent_id is not None:
        parent = session.get(Category, parent_id)
        if parent is None or parent.company_id != company_id:
            raise NotFoundError("Parent category")
    category = Category(company_id=company_id, name=name, parent_id=parent_id)
    session.add(category)
    session.flush()
    return category


def list_categories(session: Session, company_id: str) -> list[Category]:
    return list(
        session.execute(select(Category).where(Category.company_id == company_id).order_by(Category.name)).scalars()
    )


# ---- UoM ----
def create_uom(session: Session, *, company_id: str, code: str, name: str) -> UnitOfMeasure:
    if session.scalar(select(UnitOfMeasure.id).where(UnitOfMeasure.company_id == company_id, UnitOfMeasure.code == code)):
        raise ConflictError("UOM_EXISTS", f"UoM '{code}' already exists")
    uom = UnitOfMeasure(company_id=company_id, code=code, name=name)
    session.add(uom)
    session.flush()
    return uom


def ensure_uom(session: Session, *, company_id: str, code: str, name: str | None = None) -> UnitOfMeasure:
    uom = session.scalar(select(UnitOfMeasure).where(UnitOfMeasure.company_id == company_id, UnitOfMeasure.code == code))
    if uom is None:
        uom = create_uom(session, company_id=company_id, code=code, name=name or code)
    return uom


def add_conversion(session: Session, *, company_id: str, from_uom_id: str, to_uom_id: str, factor) -> UnitConversion:
    for uom_id in (from_uom_id, to_uom_id):
        uom = session.get(UnitOfMeasure, uom_id)
        if uom is None or uom.company_id != company_id:
            raise NotFoundError("Unit of measure")
    if dec(factor) <= 0:
        raise BusinessRuleError("BAD_CONVERSION_FACTOR", "Conversion factor must be > 0")
    conversion = UnitConversion(
        company_id=company_id, from_uom_id=from_uom_id, to_uom_id=to_uom_id, factor=dec(factor)
    )
    session.add(conversion)
    session.flush()
    return conversion


def convert_quantity(session: Session, *, company_id: str, value, from_uom_id: str, to_uom_id: str) -> Decimal:
    """Only explicit conversion rules are honored — directions are looked up as
    declared; unsupported pairs raise instead of guessing."""
    value = dec(value)
    if from_uom_id == to_uom_id:
        return q4(value)
    rule = session.scalar(
        select(UnitConversion).where(
            UnitConversion.company_id == company_id,
            UnitConversion.from_uom_id == from_uom_id,
            UnitConversion.to_uom_id == to_uom_id,
        )
    )
    forward = True
    if rule is None:
        rule = session.scalar(
            select(UnitConversion).where(
                UnitConversion.company_id == company_id,
                UnitConversion.from_uom_id == to_uom_id,
                UnitConversion.to_uom_id == from_uom_id,
            )
        )
        forward = False
    if rule is None:
        raise BusinessRuleError(
            "NO_UNIT_CONVERSION", f"No conversion rule between UoMs {from_uom_id} and {to_uom_id}"
        )
    factor = dec(rule.factor)
    return q4(value * factor if forward else value / factor)


# ---- products ----
def create_product(session: Session, *, company_id: str, actor_user_id: str, data: dict) -> Product:
    sku = data.get("sku")
    if not sku:
        raise BusinessRuleError("SKU_REQUIRED", "sku is required")
    if session.scalar(select(Product.id).where(Product.company_id == company_id, Product.sku == sku)):
        raise ConflictError("SKU_TAKEN", f"A product with SKU '{sku}' already exists")
    stock_type = data.get("stock_type", "stock")
    if stock_type not in VALID_STOCK_TYPES:
        raise BusinessRuleError("BAD_STOCK_TYPE", f"stock_type must be one of {sorted(VALID_STOCK_TYPES)}")
    product = Product(company_id=company_id, created_by=actor_user_id, **_product_fields(data))
    session.add(product)
    session.flush()
    return product


def update_product(session: Session, product: Product, data: dict) -> Product:
    fields = _product_fields(data, updating=True)
    for key, value in fields.items():
        setattr(product, key, value)
    session.flush()
    return product


def _product_fields(data: dict, updating: bool = False) -> dict:
    allowed = {
        "sku", "name", "description", "category_id", "uom_id", "barcode", "hsn_sac",
        "stock_type", "track_batches", "track_serials", "base_cost", "base_price",
        "weight_kg", "length_cm", "width_cm", "height_cm",
        "default_tax_rate_id", "is_active", "is_sellable", "is_purchasable",
    }
    raw = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "hsn_sac" in raw:
        raw["hsn_sac"] = str(raw["hsn_sac"]).strip() or None
        if raw["hsn_sac"] is not None and not HSN_SAC_PATTERN.match(raw["hsn_sac"]):
            raise BusinessRuleError(
                "BAD_HSN_SAC", "hsn_sac must be a 4 to 8 digit HSN/SAC code"
            )
        if raw["hsn_sac"] is None:
            raw.pop("hsn_sac")
    for measure in ("weight_kg", "length_cm", "width_cm", "height_cm"):
        if measure in raw:
            value = dec(raw[measure])
            if value < 0:
                raise BusinessRuleError("BAD_MEASURE", f"{measure} cannot be negative")
            raw[measure] = q4(value) if measure == "weight_kg" else value
    if "base_cost" in raw:
        raw["base_cost"] = dec(raw["base_cost"])
    if "base_price" in raw:
        raw["base_price"] = dec(raw["base_price"])
    if updating and raw.get("stock_type"):
        if raw["stock_type"] not in VALID_STOCK_TYPES:
            raise BusinessRuleError("BAD_STOCK_TYPE", f"stock_type must be one of {sorted(VALID_STOCK_TYPES)}")
    return raw


def get_product(session: Session, company_id: str, product_id: str) -> Product:
    product = session.get(Product, product_id)
    if product is None or product.company_id != company_id:
        raise NotFoundError("Product")
    return product


def list_products(
    session: Session,
    company_id: str,
    *,
    search: str | None = None,
    category_id: str | None = None,
    stock_type: str | None = None,
    is_active: bool | None = None,
    active_only: bool = False,
):
    stmt = select(Product).where(Product.company_id == company_id)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            (Product.name.ilike(like)) | (Product.sku.ilike(like)) | (Product.barcode.ilike(like))
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if stock_type:
        stmt = stmt.where(Product.stock_type == stock_type)
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    stmt = stmt.order_by(Product.sku)
    return session.execute(stmt).scalars().all()


# ---- price lists ----
def ensure_default_price_list(session: Session, *, company_id: str, currency: str) -> PriceList:
    pl = session.scalar(select(PriceList).where(PriceList.company_id == company_id, PriceList.is_default.is_(True)))
    if pl is None:
        pl = PriceList(company_id=company_id, name="Default", currency=currency, is_default=True)
        session.add(pl)
        session.flush()
    return pl


def set_price(
    session: Session, *, price_list_id: str, product_id: str, price, effective_from: date | None = None
) -> PriceListItem:
    pl = session.get(PriceList, price_list_id)
    if pl is None:
        raise NotFoundError("Price list")
    from datetime import date as date_t

    on_date = effective_from or date_t.today()
    row = PriceListItem(
        price_list_id=price_list_id,
        product_id=product_id,
        price=dec(price),
        effective_from=on_date,
    )
    session.add(row)
    session.flush()
    return row


def resolve_price(session: Session, product: Product, *, currency: str, on_date: date) -> Decimal:
    """Default list price resolution; falls back to product.base_price."""
    pl = session.scalar(
        select(PriceList).where(PriceList.company_id == product.company_id, PriceList.currency == currency, PriceList.is_default.is_(True))
    )
    if pl is not None:
        row = session.scalar(
            select(PriceListItem)
            .where(
                PriceListItem.price_list_id == pl.id,
                PriceListItem.product_id == product.id,
                PriceListItem.effective_from <= on_date,
            )
            .order_by(PriceListItem.effective_from.desc())
            .limit(1)
        )
        if row is not None and (row.effective_to is None or row.effective_to >= on_date):
            return dec(row.price)
    return dec(product.base_price)
