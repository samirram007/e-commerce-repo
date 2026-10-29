"""Storefront service: guest-safe catalog browsing, trending, product
interests (favorites/watchlist), delivery-zone (pincode) checks and the
anonymous token cart — plus the public shop content (hero, testimonials,
FAQ, policies, settings)."""
import hashlib
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.modules.catalog.models import (
    Category,
    DeliveryZone,
    Product,
    ProductImage,
    ProductInterest,
)
from app.modules.companies.models import Company
from app.modules.partners.models import Customer
from app.modules.sales import service as sales_svc
from app.modules.payments.models import PaymentRecord
from app.modules.sales.models import Cart, SalesOrder
from app.modules.storefront.models import (
    StorefrontAddress,
    StorefrontFaq,
    StorefrontHeroSlide,
    StorefrontPolicy,
    StorefrontSettings,
    StorefrontTestimonial,
)
from app.shared.money import dec

INTEREST_KINDS = {"favorite", "watchlist"}

#: Payment methods the mock storefront gateway can offer.
PAYMENT_METHODS = [
    {"code": "card", "label": "Credit / Debit card", "provider": "mock"},
    {"code": "upi", "label": "UPI", "provider": "mock"},
    {"code": "cod", "label": "Cash on delivery", "provider": "cash"},
]

#: Absolute-path prefix for the headerless public image route.
MEDIA_PREFIX = "/api/v1/storefront/shop/media"


def media_url(company_id: str, file_id: str | None) -> str | None:
    """Public URL for a stored file (None when there is no file)."""
    if not file_id:
        return None
    return f"{MEDIA_PREFIX}/{company_id}/{file_id}"


def discount_percent(price, compare_at) -> int | None:
    """Server-computed saving percentage (rounded down), or None."""
    if compare_at is None:
        return None
    was = dec(compare_at)
    now = dec(price)
    if was <= 0 or was <= now:
        return None
    return int(((was - now) / was * 100).to_integral_value(rounding=ROUND_DOWN))


def _product_images(p: Product, session: Session, categories: dict | None = None) -> dict:
    """Serializer for cards/lists. Cover image first, then the gallery."""
    gallery = session.execute(
        select(ProductImage)
        .where(ProductImage.product_id == p.id)
        .order_by(ProductImage.sort_order, ProductImage.created_at)
    ).scalars().all()
    images: list[dict] = []
    cover = media_url(p.company_id, p.image_file_id)
    if cover:
        images.append({"id": None, "url": cover, "alt": p.name})
    for row in gallery:
        if row.file_id == p.image_file_id:
            continue
        images.append({"id": row.id, "url": media_url(p.company_id, row.file_id), "alt": row.alt})
    category = categories.get(p.category_id) if categories and p.category_id else None
    if categories is not None and p.category_id and category is None:
        category = session.get(Category, p.category_id)
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "description": p.description,
        "category_id": p.category_id,
        "category_name": category.name if category else None,
        "category_slug": category.slug if category else None,
        "price": str(p.base_price),
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "discount_percent": discount_percent(p.base_price, p.compare_at_price),
        "badge": p.badge,
        "rating_avg": str(p.rating_avg) if p.rating_avg is not None else None,
        "rating_count": p.rating_count,
        "tone": p.tone,
        "slug": p.slug,
        "stock_type": p.stock_type,
        "view_count": p.view_count,
        "image_url": cover,
        "images": images,
    }


def _product_brief(p: Product, session: Session, categories: dict | None = None) -> dict:
    return _product_images(p, session, categories)


def _category_map(session: Session, company_id: str) -> dict[str, Category]:
    rows = session.execute(
        select(Category).where(Category.company_id == company_id)
    ).scalars().all()
    return {c.id: c for c in rows}


def _available_qty(session: Session, company_id: str, product: Product) -> str | None:
    """Live stock from the inventory module (never a product column)."""
    if product.stock_type != "stock":
        return None
    from app.modules.inventory.models import StockOnHand
    from app.modules.inventory.service import available_qty as on_hand_available

    total = Decimal("0")
    rows = session.execute(
        select(StockOnHand).where(
            StockOnHand.company_id == company_id, StockOnHand.product_id == product.id
        )
    ).scalars().all()
    for row in rows:
        total += on_hand_available(row)
    return str(total)


# ---- catalog browse ----
def _category_out(session: Session, c: Category, counts: dict) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "blurb": c.blurb,
        "tone": c.tone,
        "image_url": media_url(c.company_id, c.image_file_id),
        "parent_id": c.parent_id,
        "product_count": counts.get(c.id, 0) + counts.get(None, 0) if c.parent_id is None else counts.get(c.id, 0),
        "sort_order": c.sort_order,
    }


def _category_counts(session: Session, company_id: str) -> dict:
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
    return counts


def list_categories(session: Session, company_id: str, *, slug: str | None = None) -> list[dict]:
    stmt = select(Category).where(
        Category.company_id == company_id, Category.is_active.is_(True)
    )
    if slug:
        stmt = stmt.where(Category.slug == slug.strip().lower())
    cats = session.execute(stmt.order_by(Category.sort_order, Category.name)).scalars().all()
    counts = _category_counts(session, company_id)
    return [_category_out(session, c, counts) for c in cats]


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
    category: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    on_sale: bool = False,
    badge: str | None = None,
    sort: str = "popular",
    limit: int = 24,
    offset: int = 0,
) -> dict:
    """Paginated product listing. `category` accepts a category id OR slug."""
    stmt = select(Product).where(
        Product.company_id == company_id,
        Product.is_active.is_(True),
        Product.is_sellable.is_(True),
    )
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where((Product.name.ilike(like)) | (Product.sku.ilike(like)) | (Product.barcode.ilike(like)))
    if category:
        row = session.get(Category, category)
        if row is None or row.company_id != company_id:
            row = session.scalar(
                select(Category).where(
                    Category.company_id == company_id, Category.slug == category.strip().lower()
                )
            )
        if row is None:
            raise NotFoundError("Category")
        stmt = stmt.where(Product.category_id.in_(_category_scope(session, company_id, row.id)))
    if min_price is not None:
        stmt = stmt.where(Product.base_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.base_price <= max_price)
    if on_sale:
        stmt = stmt.where(
            Product.compare_at_price.isnot(None), Product.compare_at_price > Product.base_price
        )
    if badge:
        stmt = stmt.where(Product.badge == badge)
    order = SORTS.get(sort, SORTS["popular"])
    stmt = stmt.order_by(*order)
    total = session.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0
    rows = session.execute(stmt.limit(limit).offset(offset)).scalars().all()
    categories = _category_map(session, company_id)
    return {
        "items": [_product_brief(r, session, categories) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
    categories = _category_map(session, company_id)
    return [_product_brief(r, session, categories) for r in rows]


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
    categories = _category_map(session, company_id)
    return {
        **_product_brief(product, session, categories),
        "category_name": category.name if category else None,
        "highlights": list(product.highlights or []),
        "colors": list(product.colors or []),
        "available_qty": _available_qty(session, company_id, product),
        "related": [_product_brief(r, session, categories) for r in related],
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
    categories = _category_map(session, company_id)
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
                out[kind].append(_product_brief(product, session, categories))
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
                "image_url": media_url(company_id, products[i.product_id].image_file_id) if i.product_id in products else None,
                "tone": products[i.product_id].tone if i.product_id in products else None,
            }
            for i in items
        ],
        "quote": quote,
    }


# ---- public shop content (hero, testimonials, FAQ, policies, settings) ----
def _hero_out(s: StorefrontHeroSlide) -> dict:
    return {
        "id": s.id,
        "eyebrow": s.eyebrow,
        "title": s.title,
        "text": s.text,
        "cta": s.cta,
        "category_slug": s.category_slug,
        "tone": s.tone,
        "image_url": media_url(s.company_id, s.image_file_id),
    }


def _testimonial_out(t: StorefrontTestimonial) -> dict:
    return {"id": t.id, "name": t.name, "city": t.city, "text": t.quote}


def list_hero_slides(session: Session, company_id: str) -> list[dict]:
    rows = session.execute(
        select(StorefrontHeroSlide)
        .where(
            StorefrontHeroSlide.company_id == company_id,
            StorefrontHeroSlide.is_active.is_(True),
        )
        .order_by(StorefrontHeroSlide.sort_order, StorefrontHeroSlide.created_at)
    ).scalars().all()
    return [_hero_out(row) for row in rows]


def list_testimonials(session: Session, company_id: str) -> list[dict]:
    rows = session.execute(
        select(StorefrontTestimonial)
        .where(
            StorefrontTestimonial.company_id == company_id,
            StorefrontTestimonial.is_active.is_(True),
        )
        .order_by(StorefrontTestimonial.sort_order, StorefrontTestimonial.created_at)
    ).scalars().all()
    return [_testimonial_out(row) for row in rows]


def list_faqs(session: Session, company_id: str) -> list[dict]:
    rows = session.execute(
        select(StorefrontFaq)
        .where(
            StorefrontFaq.company_id == company_id,
            StorefrontFaq.is_active.is_(True),
        )
        .order_by(StorefrontFaq.group_name, StorefrontFaq.sort_order, StorefrontFaq.created_at)
    ).scalars().all()
    return [
        {"id": row.id, "group": row.group_name, "question": row.question, "answer": row.answer}
        for row in rows
    ]


def _policy_out(p: StorefrontPolicy, *, with_sections: bool) -> dict:
    out = {"slug": p.slug, "title": p.title, "updated": p.updated}
    if with_sections:
        out["sections"] = list(p.sections or [])
    return out


def list_policies(session: Session, company_id: str) -> list[dict]:
    rows = session.execute(
        select(StorefrontPolicy)
        .where(
            StorefrontPolicy.company_id == company_id,
            StorefrontPolicy.is_active.is_(True),
        )
        .order_by(StorefrontPolicy.sort_order, StorefrontPolicy.title)
    ).scalars().all()
    return [_policy_out(row, with_sections=False) for row in rows]


def get_policy(session: Session, company_id: str, slug: str) -> dict:
    row = session.scalar(
        select(StorefrontPolicy).where(
            StorefrontPolicy.company_id == company_id,
            StorefrontPolicy.slug == slug.strip().lower(),
            StorefrontPolicy.is_active.is_(True),
        )
    )
    if row is None:
        raise NotFoundError("Policy")
    return _policy_out(row, with_sections=True)


def get_settings_row(session: Session, company_id: str) -> StorefrontSettings | None:
    return session.scalar(
        select(StorefrontSettings).where(StorefrontSettings.company_id == company_id)
    )


def settings_out(row: StorefrontSettings | None, company_id: str) -> dict:
    """Store settings as the public shop consumes them (money as strings)."""
    if row is None:
        return {
            "free_shipping_threshold": None,
            "flat_shipping_fee": None,
            "contact_phone": None,
            "contact_email": None,
            "contact_address": None,
            "map_image_url": None,
            "announcements": [],
            "perks": [],
            "about_values": [],
            "about_stats": [],
            "footer_about": None,
        }
    return {
        "free_shipping_threshold": str(row.free_shipping_threshold) if row.free_shipping_threshold is not None else None,
        "flat_shipping_fee": str(row.flat_shipping_fee) if row.flat_shipping_fee is not None else None,
        "contact_phone": row.contact_phone,
        "contact_email": row.contact_email,
        "contact_address": row.contact_address,
        "map_image_url": media_url(company_id, row.map_image_file_id),
        "announcements": list(row.announcements or []),
        "perks": list(row.perks or []),
        "about_values": list(row.about_values or []),
        "about_stats": list(row.about_stats or []),
        "footer_about": row.footer_about,
    }


def compute_shipping(session: Session, company_id: str, subtotal) -> Decimal:
    """Authoritative shipping quote from the store settings.

    Free when no rules are configured, free above the threshold, otherwise the
    flat fee.
    """
    settings = get_settings_row(session, company_id)
    if settings is None:
        return Decimal("0")
    subtotal = dec(subtotal)
    threshold = (
        dec(settings.free_shipping_threshold)
        if settings.free_shipping_threshold is not None
        else None
    )
    if threshold is not None and subtotal >= threshold:
        return Decimal("0")
    if settings.flat_shipping_fee is None:
        return Decimal("0")
    return dec(settings.flat_shipping_fee)


def home(session: Session, company_id: str) -> dict:
    """One call that feeds the whole home page."""
    categories = list_categories(session, company_id)
    bestsellers = session.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.rating_count > 0,
        )
        .order_by(Product.rating_count.desc(), Product.name.asc())
        .limit(10)
    ).scalars().all()
    new_arrivals = session.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.badge == "New",
        )
        .order_by(Product.created_at.desc(), Product.name.asc())
        .limit(8)
    ).scalars().all()
    sale_rows = session.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
            Product.compare_at_price.isnot(None),
            Product.compare_at_price > Product.base_price,
        )
        .order_by(Product.view_count.desc())
        .limit(24)
    ).scalars().all()
    category_map = _category_map(session, company_id)
    deal = None
    for candidate in sale_rows:
        off = discount_percent(candidate.base_price, candidate.compare_at_price)
        if off is not None and (deal is None or off > deal[0]):
            deal = (off, candidate)
    return {
        "hero": list_hero_slides(session, company_id),
        "categories": categories,
        "bestsellers": [_product_brief(p, session, category_map) for p in bestsellers],
        "new_arrivals": [_product_brief(p, session, category_map) for p in new_arrivals],
        "deal": _product_brief(deal[1], session, category_map) if deal else None,
        "testimonials": list_testimonials(session, company_id),
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
        "settings": settings_out(get_settings_row(session, company.id), company.id),
    }


def payment_methods(session: Session, company_id: str, *, pincode: str | None = None) -> list[dict]:
    """Available payment methods; COD depends on the pincode's delivery zone.

    For online methods the gateway resolved *right now* is reported as
    `provider` + `mode` (so checkout can show a TEST badge and open the right
    widget). When no gateway can serve the method the row is marked
    `available=false`. Secrets are never included.
    """
    from app.core.exceptions import AppError
    from app.modules.payments.gateways import resolve_gateway

    zone = None
    if pincode:
        zone = session.scalar(
            select(DeliveryZone).where(
                DeliveryZone.company_id == company_id, DeliveryZone.pincode == pincode.strip()
            )
        )
    out = []
    for method in PAYMENT_METHODS:
        if method["code"] == "cod":
            # Cash on delivery stays offline — no gateway involved.
            available = zone.cod_allowed if zone is not None else True
            out.append({**method, "provider": "cash", "mode": None, "available": available})
            continue
        try:
            adapter, creds, _config = resolve_gateway(session, company_id, method["code"])
        except AppError:
            out.append({**method, "mode": None, "available": False})
            continue
        out.append(
            {
                **method,
                "provider": adapter.name,
                "mode": creds.mode if creds else None,
                "available": True,
            }
        )
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
    if get_settings_row(session, company_id) is not None:
        # The store's shipping rules are authoritative; ignore any client value.
        shipping_total = compute_shipping(
            session, company_id, sales_svc.quote_cart(session, cart)["subtotal"]
        )
    else:
        shipping_total = dec(payload.get("shipping_total") or "0")
    order, replayed = sales_svc.checkout_cart(
        session,
        company_id=company_id,
        actor_user_id=None,
        cart_id=cart.id,
        customer_id=customer.id,
        shipping_address=address_text,
        billing_address=address_text,
        shipping_total=shipping_total,
        notes=payload.get("notes") or ("Cash on delivery" if method == "cod" else None),
        idempotency_key=idempotency_key,
    )
    payment_state = order.payment_state
    payment_out = None
    if method != "cod" and order.status == "pending_payment":
        # Online methods no longer charge synchronously: create the provider
        # intent and hand the browser everything it needs; the order is only
        # marked paid after verify_client_payment or a webhook confirms it.
        payment_out = _start_payment(
            session, company_id=company_id, actor_user_id=None, order=order, method=method
        )
        payment_state = order.payment_state
    return {
        **_order_out(session, order),
        "payment_method": method,
        "payment_state": payment_state,
        "payment": payment_out,
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
    """Start (or restart) payment for a pending order — continue purchase."""
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    cart = session.get(Cart, order.cart_id) if order.cart_id else None
    if cart is None or cart.token != cart_token:
        raise BusinessRuleError("ORDER_NOT_OWNED", "This order belongs to another cart")
    if order.status != "pending_payment":
        raise BusinessRuleError(
            "ORDER_NOT_PAYABLE", f"Order status '{order.status}' cannot be paid"
        )
    if method not in {m["code"] for m in PAYMENT_METHODS} or method == "cod":
        raise BusinessRuleError("BAD_PAYMENT_METHOD", "Choose an online payment method")
    payment = _start_payment(
        session, company_id=company_id, actor_user_id=None, order=order, method=method
    )
    return {**_order_out(session, order), "payment_method": method, "payment": payment}


def _start_payment(
    session: Session, *, company_id: str, actor_user_id: str | None, order: SalesOrder, method: str
) -> dict:
    """Create the provider intent for an order and persist the pending receipt."""
    from app.modules.payments import service as payments_svc
    from app.modules.payments.gateways import resolve_gateway

    adapter, creds, _config = resolve_gateway(session, company_id, method)
    record, intent = payments_svc.create_provider_intent(
        session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        customer_id=order.customer_id,
        order_id=order.id,
        receipt=order.doc_number,
        amount=order.total,
        currency=order.currency,
        method=method,
        adapter=adapter,
        creds=creds,
        idempotency_key=f"intent:{order.id}",
    )
    return {
        "provider": adapter.name,
        "mode": creds.mode,
        "payment_id": record.id,
        "client_payload": intent.client_payload,
    }


def confirm_payment(
    session: Session, *, company_id: str, cart_token: str, order_id: str, payload: dict
) -> dict:
    """Shopper's browser reports the completed payment; verify it with the
    provider, then complete the order through the shared idempotent path
    (invoice + journal posted exactly once, no matter whether the webhook or
    this callback arrives first)."""
    from app.modules.payments import service as payments_svc
    from app.modules.payments.gateways import get_gateway_by_name

    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    cart = session.get(Cart, order.cart_id) if order.cart_id else None
    if cart is None or cart.token != cart_token:
        raise BusinessRuleError("ORDER_NOT_OWNED", "This order belongs to another cart")

    record = payments_svc.pending_for_order(session, order.id)
    if record is None:
        settled = session.scalar(
            select(PaymentRecord).where(
                PaymentRecord.order_id == order.id,
                PaymentRecord.direction == "receipt",
                PaymentRecord.status == "succeeded",
            ).order_by(PaymentRecord.occurred_at.desc())
        )
        if settled is not None and order.status == "paid":
            # Webhook already finalized this order — replay the happy path.
            return {
                **_order_out(session, order),
                "payment_state": order.payment_state,
                "payment": {
                    "provider": settled.provider,
                    "mode": settled.mode,
                    "status": settled.status,
                },
            }
        raise BusinessRuleError("NO_PENDING_PAYMENT", "There is no pending payment for this order")

    adapter, creds, _config = get_gateway_by_name(
        session, company_id, record.provider, mode=record.mode
    )
    verify = adapter.verify_client_payment(creds, payload=payload)
    if not verify.succeeded:
        raise BusinessRuleError(
            "PAYMENT_VERIFICATION_FAILED",
            verify.message or "The payment could not be verified with the provider",
        )
    order, record = sales_svc.confirm_order_payment(
        session,
        company_id=company_id,
        actor_user_id=None,
        order_id=order.id,
        payment=record,
        charge_ref=verify.provider_ref,
    )
    return {
        **_order_out(session, order),
        "payment_state": order.payment_state,
        "payment": {
            "provider": record.provider,
            "mode": record.mode,
            "status": record.status,
        },
    }
