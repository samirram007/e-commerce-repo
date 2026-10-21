"""Storefront service: guest-safe catalog browsing, trending, product
interests (favorites/watchlist), delivery-zone (pincode) checks and the
anonymous token cart."""
import hashlib
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.catalog.models import (
    Category,
    DeliveryZone,
    Product,
    ProductInterest,
)
from app.modules.companies.models import Company
from app.modules.partners.models import Customer
from app.modules.sales import service as sales_svc
from app.modules.sales.models import Cart, SalesOrder
from app.modules.storefront.models import StorefrontAddress
from app.shared.money import dec

INTEREST_KINDS = {"favorite", "watchlist"}

#: Payment methods the mock storefront gateway can offer.
PAYMENT_METHODS = [
    {"code": "card", "label": "Credit / Debit card", "provider": "mock"},
    {"code": "upi", "label": "UPI", "provider": "mock"},
    {"code": "cod", "label": "Cash on delivery", "provider": "cash"},
]


def _product_brief(p: Product) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "description": p.description,
        "category_id": p.category_id,
        "price": str(p.base_price),
        "stock_type": p.stock_type,
        "view_count": p.view_count,
    }


# ---- catalog browse ----
def list_categories(session: Session, company_id: str) -> list[dict]:
    cats = session.execute(
        select(Category).where(Category.company_id == company_id).order_by(Category.name)
    ).scalars().all()
    counts: dict[str | None, int] = {}
    for p in session.execute(
        select(Product.category_id, func.count())
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
        )
        .group_by(Product.category_id)
    ).all():
        counts[p[0]] = p[1]
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "product_count": counts.get(c.id, 0) + counts.get(None, 0) if c.parent_id is None else counts.get(c.id, 0),
        }
        for c in cats
    ]


def _category_scope(session: Session, company_id: str, category_id: str) -> list[str]:
    """Category + all descendant categories (simple recursive walk; category
    trees are small)."""
    ids = [category_id]
    frontier = [category_id]
    while frontier:
        rows = session.execute(
            select(Category.id).where(Category.company_id == company_id, Category.parent_id.in_(frontier))
        ).scalars().all()
        ids.extend(new for new in rows if new not in ids)
        frontier = rows
    return ids


SORTS = {
    "popular": (Product.view_count.desc(), Product.name.asc()),
    "price_asc": (Product.base_price.asc(), Product.name.asc()),
    "price_desc": (Product.base_price.desc(), Product.name.asc()),
    "newest": (Product.created_at.desc(), Product.name.asc()),
    "name": (Product.name.asc(),),
}


def list_products(
    session: Session,
    company_id: str,
    *,
    q: str | None = None,
    category_id: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sort: str = "popular",
    limit: int = 24,
    offset: int = 0,
) -> dict:
    stmt = select(Product).where(
        Product.company_id == company_id,
        Product.is_active.is_(True),
        Product.is_sellable.is_(True),
    )
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where((Product.name.ilike(like)) | (Product.sku.ilike(like)) | (Product.barcode.ilike(like)))
    if category_id:
        stmt = stmt.where(Product.category_id.in_(_category_scope(session, company_id, category_id)))
    if min_price is not None:
        stmt = stmt.where(Product.base_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.base_price <= max_price)
    order = SORTS.get(sort, SORTS["popular"])
    stmt = stmt.order_by(*order)
    total = session.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0
    rows = session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return {"items": [_product_brief(r) for r in rows], "total": total}


def trending(session: Session, company_id: str, limit: int = 8) -> list[dict]:
    rows = session.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.view_count > 0,
        )
        .order_by(Product.view_count.desc())
        .limit(limit)
    ).scalars().all()
    return [_product_brief(r) for r in rows]


def product_detail(session: Session, company_id: str, product_id: str, *, count_view: bool) -> dict:
    product = session.get(Product, product_id)
    if product is None or product.company_id != company_id:
        raise NotFoundError("Product")
    if count_view:
        product.view_count += 1
        session.flush()
    category = session.get(Category, product.category_id) if product.category_id else None
    related = session.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.id != product.id,
            (
                (Product.category_id == product.category_id)
                if product.category_id is not None
                else Product.view_count >= 0
            ),
        )
        .order_by(Product.view_count.desc())
        .limit(8)
    ).scalars().all()
    return {
        **_product_brief(product),
        "category_name": category.name if category else None,
        "related": [_product_brief(r) for r in related],
    }


# ---- interests (favorites / watchlist) ----
def toggle_interest(
    session: Session, company_id: str, kind: str, product_id: str, *, user_id: str | None, anon_id: str | None
) -> bool:
    if kind not in INTEREST_KINDS:
        raise BusinessRuleError("BAD_INTEREST_KIND", f"kind must be one of {sorted(INTEREST_KINDS)}")
    product = session.get(Product, product_id)
    if product is None or product.company_id != company_id:
        raise NotFoundError("Product")
    stmt = select(ProductInterest).where(
        ProductInterest.company_id == company_id,
        ProductInterest.kind == kind,
        ProductInterest.product_id == product_id,
    )
    stmt = stmt.where(ProductInterest.user_id == user_id) if user_id else stmt.where(ProductInterest.anon_id == anon_id)
    existing = session.scalar(stmt)
    if existing is not None:
        session.delete(existing)
        session.flush()
        return False
    if user_id is None and not anon_id:
        raise BusinessRuleError("IDENTITY_REQUIRED", "Guest requests need an X-Anon-Id")
    session.add(ProductInterest(company_id=company_id, kind=kind, product_id=product_id, user_id=user_id, anon_id=anon_id))
    session.flush()
    return True


def list_interests(
    session: Session, company_id: str, *, user_id: str | None, anon_id: str | None
) -> dict:
    out = {"favorite": [], "watchlist": []}
    for kind in INTEREST_KINDS:
        rows = session.execute(
            select(ProductInterest).where(
                ProductInterest.company_id == company_id,
                ProductInterest.kind == kind,
            )
        ).scalars().all()
        rows = [r for r in rows if (r.user_id == user_id if user_id else r.anon_id == anon_id)]
        for row in rows:
            product = session.get(Product, row.product_id)
            if product is not None and product.is_active and product.is_sellable:
                out[kind].append(_product_brief(product))
    return out


def claim_anon_interests(session: Session, company_id: str, anon_id: str, user_id: str) -> int:
    """Re-home a guest's interests onto their user account at login. Returns
    the number of rows migrated."""
    rows = session.execute(
        select(ProductInterest).where(
            ProductInterest.company_id == company_id,
            ProductInterest.anon_id == anon_id,
        )
    ).scalars().all()
    moved = 0
    for row in rows:
        existing = session.scalar(
            select(ProductInterest).where(
                ProductInterest.company_id == row.company_id,
                ProductInterest.kind == row.kind,
                ProductInterest.product_id == row.product_id,
                ProductInterest.user_id == user_id,
            )
        )
        if existing is None:
            row.user_id = user_id
            row.anon_id = None
            moved += 1
        else:
            session.delete(row)
    session.flush()
    return moved


# ---- pincode delivery ----
def check_pincode(session: Session, company_id: str, pincode: str) -> dict:
    pincode = pincode.strip()
    zone = session.scalar(
        select(DeliveryZone).where(DeliveryZone.company_id == company_id, DeliveryZone.pincode == pincode)
    )
    if zone is not None:
        return {
            "pincode": pincode,
            "deliverable": zone.deliverable,
            "eta_days": zone.eta_days,
            "cod_allowed": zone.cod_allowed,
            "configured": True,
        }
    return {"pincode": pincode, "deliverable": False, "eta_days": None, "cod_allowed": False, "configured": False}


def set_delivery_zone(
    session: Session, company_id: str, *, pincode: str, deliverable: bool, eta_days: int, cod_allowed: bool
) -> DeliveryZone:
    pincode = pincode.strip()
    if not pincode:
        raise BusinessRuleError("PINCODE_REQUIRED", "pincode is required")
    if eta_days < 1:
        raise BusinessRuleError("BAD_ETA", "eta_days must be >= 1")
    zone = session.scalar(
        select(DeliveryZone).where(DeliveryZone.company_id == company_id, DeliveryZone.pincode == pincode)
    )
    if zone is None:
        zone = DeliveryZone(company_id=company_id, pincode=pincode)
        session.add(zone)
    zone.deliverable = deliverable
    zone.eta_days = eta_days
    zone.cod_allowed = cod_allowed
    session.flush()
    return zone


# ---- guest token cart ----
def token_cart(session: Session, company_id: str, token: str) -> Cart:
    if not token or len(token) < 8:
        raise BusinessRuleError("CART_TOKEN_INVALID", "A stable X-Cart-Token (>= 8 chars) is required")
    return sales_svc.get_or_create_cart(
        session, company_id=company_id, user_id=None, customer_id=None, token=token
    )


def guest_cart_out(session: Session, company_id: str, token: str) -> dict:
    cart = token_cart(session, company_id, token)
    items = sales_svc.cart_items(session, cart.id)
    products = {
        p.id: p
        for p in session.execute(
            select(Product).where(Product.id.in_([i.product_id for i in items]))
        ).scalars().all()
    } if items else {}
    quote = sales_svc.quote_cart(session, cart)
    return {
        "id": cart.id,
        "status": cart.status,
        "token": token,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "qty": str(i.qty),
                "name": products[i.product_id].name if i.product_id in products else "Item",
                "sku": products[i.product_id].sku if i.product_id in products else "",
                "price": str(products[i.product_id].base_price) if i.product_id in products else "0",
            }
            for i in items
        ],
        "quote": quote,
    }


# ---- store info (public storefront bootstrap) ----
def store_info(session: Session, slug: str) -> dict:
    """Resolve a public storefront by its slug (no auth required)."""
    company = session.scalar(
        select(Company).where(
            Company.storefront_slug == slug.strip().lower(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise NotFoundError("Store")
    return {
        "company_id": company.id,
        "slug": company.storefront_slug,
        "name": company.name,
        "currency": company.base_currency,
        "allow_guest_checkout": company.allow_guest_checkout,
    }


def payment_methods(session: Session, company_id: str, *, pincode: str | None = None) -> list[dict]:
    """Available payment methods; COD depends on the pincode's delivery zone."""
    zone = None
    if pincode:
        zone = session.scalar(
            select(DeliveryZone).where(
                DeliveryZone.company_id == company_id, DeliveryZone.pincode == pincode.strip()
            )
        )
    out = []
    for method in PAYMENT_METHODS:
        available = True
        if method["code"] == "cod" and zone is not None:
            available = zone.cod_allowed
        out.append({**method, "available": available})
    return out


# ---- shopper addresses ----
def owner_key(user_id: str | None, anon_id: str | None) -> str:
    """Stable owner key for shopper-scoped rows (addresses)."""
    if user_id:
        return f"user:{user_id}"
    if anon_id:
        return f"anon:{anon_id}"
    raise BusinessRuleError("IDENTITY_REQUIRED", "Sign in or send an X-Anon-Id header")


def _address_out(row: StorefrontAddress) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "name": row.name,
        "phone": row.phone,
        "line1": row.line1,
        "line2": row.line2,
        "city": row.city,
        "region": row.region,
        "pincode": row.pincode,
        "country": row.country,
        "is_default": row.is_default,
        "notes": row.notes,
    }


def list_addresses(session: Session, company_id: str, owner: str) -> list[dict]:
    rows = session.execute(
        select(StorefrontAddress)
        .where(StorefrontAddress.company_id == company_id, StorefrontAddress.owner_key == owner)
        .order_by(StorefrontAddress.is_default.desc(), StorefrontAddress.created_at)
    ).scalars().all()
    return [_address_out(row) for row in rows]


def save_address(
    session: Session, company_id: str, owner: str, data: dict, address_id: str | None = None
) -> dict:
    """Create or update one saved address for the shopper."""
    if address_id:
        row = session.get(StorefrontAddress, address_id)
        if row is None or row.company_id != company_id or row.owner_key != owner:
            raise NotFoundError("Address")
    else:
        row = StorefrontAddress(company_id=company_id, owner_key=owner)
        session.add(row)
    row.label = (data.get("label") or "Home")[:40]
    row.name = (data.get("name") or "")[:200]
    row.phone = data.get("phone") or None
    row.line1 = (data.get("line1") or "")[:200]
    row.line2 = data.get("line2") or None
    row.city = data.get("city") or None
    row.region = data.get("region") or None
    row.pincode = data.get("pincode") or None
    row.country = (data.get("country") or "IN")[:2].upper()
    row.notes = data.get("notes") or None
    row.is_default = bool(data.get("is_default"))
    session.flush()
    if row.is_default:
        for other in session.execute(
            select(StorefrontAddress).where(
                StorefrontAddress.company_id == company_id,
                StorefrontAddress.owner_key == owner,
                StorefrontAddress.id != row.id,
            )
        ).scalars().all():
            other.is_default = False
        session.flush()
    return _address_out(row)


def delete_address(session: Session, company_id: str, owner: str, address_id: str) -> None:
    row = session.get(StorefrontAddress, address_id)
    if row is None or row.company_id != company_id or row.owner_key != owner:
        raise NotFoundError("Address")
    session.delete(row)
    session.flush()


# ---- guest checkout ----
def _guest_customer(
    session: Session, company_id: str, *, name: str, email: str, phone: str | None
) -> Customer:
    """Find (or create) the customer record behind a guest checkout."""
    email = (email or "").strip().lower()
    existing = session.scalar(
        select(Customer).where(
            Customer.company_id == company_id, func.lower(Customer.email) == email
        )
    )
    if existing is not None:
        if name and not existing.name:
            existing.name = name
        if phone and not existing.phone:
            existing.phone = phone
        session.flush()
        return existing
    code = "WEB-" + hashlib.sha1(email.encode("utf-8")).hexdigest()[:10].upper()
    customer = Customer(
        company_id=company_id,
        code=code,
        name=name or email,
        email=email,
        phone=phone,
        notes="Guest checkout",
    )
    session.add(customer)
    session.flush()
    return customer


def _format_address(address: dict) -> str:
    parts = [
        address.get("line1") or "",
        address.get("line2") or "",
        address.get("city") or "",
        address.get("region") or "",
        address.get("pincode") or "",
        address.get("country") or "",
    ]
    return ", ".join(part for part in parts if part)


def _order_out(session: Session, order: SalesOrder) -> dict:
    lines = sales_svc.get_order_lines(session, order.id)
    return {
        "id": order.id,
        "doc_number": order.doc_number,
        "status": order.status,
        "payment_state": order.payment_state,
        "order_date": str(order.order_date),
        "currency": order.currency,
        "subtotal": str(order.subtotal),
        "tax_total": str(order.tax_total),
        "shipping_total": str(order.shipping_total),
        "total": str(order.total),
        "invoice_id": order.invoice_id,
        "shipping_address": order.shipping_address,
        "items": [
            {
                "product_id": line.product_id,
                "name": line.description_snapshot,
                "sku": line.sku_snapshot,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
            for line in lines
        ],
    }


def guest_checkout(
    session: Session, *, company_id: str, cart_token: str, payload: dict, idempotency_key: str
) -> dict:
    """Place an order for a guest shopper: validates delivery + payment,
    creates the customer + order and (optionally) charges the payment."""
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company")
    if not company.allow_guest_checkout:
        raise BusinessRuleError(
            "GUEST_CHECKOUT_DISABLED", "This store does not accept guest checkout"
        )
    cart = token_cart(session, company_id, cart_token)
    if not sales_svc.cart_items(session, cart.id):
        raise BusinessRuleError("EMPTY_CART", "Cart is empty")

    address = payload.get("address") or {}
    pincode = (address.get("pincode") or "").strip()
    zones = session.execute(
        select(func.count()).select_from(DeliveryZone).where(DeliveryZone.company_id == company_id)
    ).scalar_one()
    zone = None
    if pincode:
        zone = session.scalar(
            select(DeliveryZone).where(
                DeliveryZone.company_id == company_id, DeliveryZone.pincode == pincode
            )
        )
    if zones and (zone is None or not zone.deliverable):
        raise BusinessRuleError("NOT_DELIVERABLE", f"We do not deliver to {pincode}")

    method = (payload.get("payment_method") or "card").lower()
    if method not in {m["code"] for m in PAYMENT_METHODS}:
        raise BusinessRuleError("BAD_PAYMENT_METHOD", f"Unknown payment method '{method}'")
    if method == "cod" and zone is not None and not zone.cod_allowed:
        raise BusinessRuleError(
            "COD_NOT_AVAILABLE", "Cash on delivery is unavailable for this pincode"
        )

    customer = _guest_customer(
        session,
        company_id,
        name=(payload.get("name") or "").strip(),
        email=(payload.get("email") or "").strip(),
        phone=(payload.get("phone") or "").strip() or None,
    )
    if not customer.email:
        raise BusinessRuleError("EMAIL_REQUIRED", "An email address is required to place the order")

    address_text = _format_address(address)
    order, replayed = sales_svc.checkout_cart(
        session,
        company_id=company_id,
        actor_user_id=None,
        cart_id=cart.id,
        customer_id=customer.id,
        shipping_address=address_text,
        billing_address=address_text,
        shipping_total=dec(payload.get("shipping_total") or "0"),
        notes=payload.get("notes") or ("Cash on delivery" if method == "cod" else None),
        idempotency_key=idempotency_key,
    )
    payment_state = order.payment_state
    if method != "cod" and order.status == "pending_payment":
        order, _payment = sales_svc.pay_order(
            session,
            company_id=company_id,
            actor_user_id=None,
            order_id=order.id,
            method=method,
            provider_name="mock",
            idempotency_key=f"pay:{order.id}",
        )
        payment_state = order.payment_state
    return {
        **_order_out(session, order),
        "payment_method": method,
        "payment_state": payment_state,
        "email": customer.email,
        "replayed": replayed,
    }


def guest_orders(session: Session, company_id: str, cart_token: str) -> list[dict]:
    """Orders placed from this browser's cart token (continue purchase)."""
    cart_ids = session.execute(
        select(Cart.id).where(Cart.company_id == company_id, Cart.token == cart_token)
    ).scalars().all()
    if not cart_ids:
        return []
    orders = session.execute(
        select(SalesOrder)
        .where(SalesOrder.company_id == company_id, SalesOrder.cart_id.in_(cart_ids))
        .order_by(SalesOrder.created_at.desc())
    ).scalars().all()
    return [_order_out(session, order) for order in orders]


def guest_pay_order(
    session: Session, *, company_id: str, cart_token: str, order_id: str, method: str
) -> dict:
    """Pay a pending order later (continue purchase of an unpaid order)."""
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    cart = session.get(Cart, order.cart_id) if order.cart_id else None
    if cart is None or cart.token != cart_token:
        raise BusinessRuleError("ORDER_NOT_OWNED", "This order belongs to another cart")
    if method not in {m["code"] for m in PAYMENT_METHODS} or method == "cod":
        raise BusinessRuleError("BAD_PAYMENT_METHOD", "Choose an online payment method")
    order, _payment = sales_svc.pay_order(
        session,
        company_id=company_id,
        actor_user_id=None,
        order_id=order.id,
        method=method,
        provider_name="mock",
        idempotency_key=f"pay:{order.id}",
    )
    return {**_order_out(session, order), "payment_method": method}
