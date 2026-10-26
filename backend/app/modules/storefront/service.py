"""Storefront service: guest-safe catalog browsing, trending, product
interests (favorites/watchlist), delivery-zone (pincode) checks and the
anonymous token cart."""
import hashlib
import re
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape as xml_escape

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
from app.shared.money import dec, money

INTEREST_KINDS = {"favorite", "watchlist"}

#: Fallback (mock) payment methods used when Razorpay keys are not configured.
MOCK_PAYMENT_METHODS = [
    {"code": "card", "label": "Credit / Debit card (sandbox)", "provider": "mock"},
    {"code": "upi", "label": "UPI (sandbox)", "provider": "mock"},
]

COD_METHOD = {"code": "cod", "label": "Cash on delivery", "provider": "cash"}

#: Every method code the checkout may submit.
PAYMENT_METHOD_CODES = {"card", "upi", "cod", "razorpay"}


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
        "image_url": product_image_url(p.id),
    }


def product_image_url(product_id: str) -> str:
    """Public URL of the product image. Serves the uploaded photo when the
    product has one, otherwise a deterministic generated tile (see
    `placeholder_image_svg`)."""
    return f"/api/v1/storefront/shop/products/{product_id}/image"


# ---- catalog browse ----
def list_categories(session: Session, company_id: str) -> list[dict]:
    """Categories with sellable-product counts rolled up through children,
    so a parent card matches what opening that category actually shows."""
    cats = session.execute(
        select(Category).where(Category.company_id == company_id).order_by(Category.name)
    ).scalars().all()
    own: dict[str, int] = {}
    for category_id, count in session.execute(
        select(Product.category_id, func.count())
        .where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sellable.is_(True),
        )
        .group_by(Product.category_id)
    ).all():
        if category_id:
            own[category_id] = count

    children: dict[str, list[str]] = {}
    for c in cats:
        if c.parent_id:
            children.setdefault(c.parent_id, []).append(c.id)

    def subtree_count(category_id: str, depth: int = 0) -> int:
        total = own.get(category_id, 0)
        if depth > 10:  # defensive: category trees are small and shallow
            return total
        for child in children.get(category_id, []):
            total += subtree_count(child, depth + 1)
        return total

    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "product_count": subtree_count(c.id),
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


#: Emoji hint per category (lower-cased name) for the generated image tile.
_CATEGORY_EMOJI = {
    "phones": "\U0001f4f1",
    "laptops": "\U0001f4bb",
    "accessories": "\U0001f50c",
    "apparel": "\U0001f455",
    "home & kitchen": "\U0001f3e0",
    "grocery": "\U0001f6d2",
    "services": "\U0001f6e0\ufe0f",
    "audio": "\U0001f3a7",
    "wearables": "\u231a",
    "cameras": "\U0001f4f7",
    "tablets": "\U0001f4f2",
    "sports & outdoors": "\U0001f3c0",
    "fitness": "\U0001f3cb\ufe0f",
    "cycling": "\U0001f6b2",
    "beauty & personal care": "\U0001f9f4",
    "skincare": "\U0001f9fc",
    "toys & games": "\U0001f9f8",
    "stationery": "\u270f\ufe0f",
    "beverages": "\U0001f964",
    "snacks": "\U0001f37f",
}


def _resolve_product(session: Session, company_id: str, product_id: str) -> Product:
    product = session.get(Product, product_id)
    if product is None or product.company_id != company_id:
        raise NotFoundError("Product")
    return product


def placeholder_image_svg(session: Session, product: Product) -> bytes:
    """Deterministic product tile: hue seeded from the SKU, emoji from the
    category, product name beneath. Keeps the catalog visual without external
    image services; a real uploaded photo (image_file_id) takes precedence."""
    hue = int(hashlib.sha256((product.sku or product.id).encode()).hexdigest(), 16) % 360
    emoji = "\U0001f4e6"
    if product.category_id:
        category = session.get(Category, product.category_id)
        if category is not None:
            emoji = _CATEGORY_EMOJI.get(category.name.strip().lower(), emoji)
    name = xml_escape(product.name[:38])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue}, 62%, 76%)"/>'
        f'<stop offset="1" stop-color="hsl({(hue + 40) % 360}, 58%, 52%)"/>'
        '</linearGradient></defs>'
        '<rect width="600" height="600" fill="url(#g)"/>'
        f'<text x="300" y="300" font-size="190" text-anchor="middle">{emoji}</text>'
        f'<text x="300" y="430" font-size="30" text-anchor="middle" fill="rgba(255,255,255,0.95)" '
        'font-family="system-ui, sans-serif">'
        f'{name}</text>'
        '</svg>'
    )
    return svg.encode("utf-8")


def product_detail(session: Session, company_id: str, product_id: str, *, count_view: bool) -> dict:
    product = _resolve_product(session, company_id, product_id)
    if count_view:
        # bump view count for analytics
        product.view_count = (product.view_count or 0) + 1
        session.add(product)
        session.flush()
    result = {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "category_id": product.category_id,
        "price": str(product.base_price),
        "stock_type": product.stock_type,
        "view_count": product.view_count,
        "image_url": product_image_url(product.id),
    }
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
        **result,
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


# ---- pincode delivery (India) ----

#: Indian PIN codes are six digits and never start with 0. The first two
#: digits identify the postal circle, which maps onto a state/UT.
_PINCODE_STATE_RANGES = [
    (11, 11, "Delhi"),
    (12, 13, "Haryana"),
    (14, 16, "Punjab"),
    (17, 17, "Himachal Pradesh"),
    (18, 18, "Jammu & Kashmir"),
    (19, 19, "Ladakh"),
    (20, 28, "Uttar Pradesh / Uttarakhand"),
    (30, 34, "Rajasthan"),
    (36, 39, "Gujarat"),
    (40, 44, "Maharashtra"),
    (45, 48, "Madhya Pradesh"),
    (49, 49, "Chhattisgarh"),
    (50, 50, "Telangana"),
    (51, 53, "Andhra Pradesh"),
    (56, 59, "Karnataka"),
    (60, 64, "Tamil Nadu"),
    (67, 69, "Kerala"),
    (70, 74, "West Bengal"),
    (75, 77, "Odisha"),
    (78, 78, "Assam"),
    (79, 79, "North East"),
    (80, 85, "Bihar / Jharkhand"),
    (90, 99, "Army Postal Service"),
]

#: City/area hints for well-known sorting districts (first three digits).
_PINCODE_CITY = {
    "110": "New Delhi",
    "122": "Gurugram",
    "160": "Chandigarh",
    "171": "Shimla",
    "190": "Srinagar",
    "201": "Noida",
    "208": "Kanpur",
    "211": "Prayagraj",
    "221": "Varanasi",
    "226": "Lucknow",
    "248": "Dehradun",
    "250": "Meerut",
    "302": "Jaipur",
    "380": "Ahmedabad",
    "400": "Mumbai",
    "403": "Panaji",
    "411": "Pune",
    "422": "Nashik",
    "440": "Nagpur",
    "462": "Bhopal",
    "492": "Raipur",
    "500": "Hyderabad",
    "520": "Vijayawada",
    "530": "Visakhapatnam",
    "560": "Bengaluru",
    "570": "Mysuru",
    "600": "Chennai",
    "641": "Coimbatore",
    "673": "Kozhikode",
    "682": "Kochi",
    "695": "Thiruvananthapuram",
    "700": "Kolkata",
    "751": "Bhubaneswar",
    "781": "Guwahati",
    "800": "Patna",
    "834": "Ranchi",
}


def normalize_pincode(value: str | None) -> str:
    """Validate and normalise an Indian PIN code (spaces/dashes tolerated)."""
    digits = re.sub(r"[\s-]", "", (value or "").strip())
    if not re.fullmatch(r"[1-9]\d{5}", digits):
        raise BusinessRuleError(
            "BAD_PINCODE", "Enter a 6-digit Indian PIN code (it cannot start with 0)"
        )
    return digits


def normalize_zone_code(value: str | None) -> str:
    """A delivery rule covers either one PIN code (6 digits) or a prefix
    (2–5 digits), e.g. `40` for all of Mumbai/Konkan."""
    code = re.sub(r"[\s-]", "", (value or "").strip())
    if not re.fullmatch(r"[1-9]\d{1,5}", code):
        raise BusinessRuleError(
            "BAD_ZONE", "A delivery zone must be a PIN code or a 2–5 digit prefix"
        )
    return code


def _resolve_zone(session: Session, company_id: str, pincode: str) -> DeliveryZone | None:
    """Most specific delivery rule for a PIN code: exact code, else the
    longest matching prefix (so state-wide coverage needs one row, not 10⁵)."""
    zones = session.execute(
        select(DeliveryZone).where(DeliveryZone.company_id == company_id)
    ).scalars().all()
    exact = next((z for z in zones if z.pincode == pincode), None)
    if exact is not None:
        return exact
    prefixes = [
        z for z in zones if 2 <= len(z.pincode) < 6 and pincode.startswith(z.pincode)
    ]
    if not prefixes:
        return None
    return max(prefixes, key=lambda z: len(z.pincode))


def _pincode_state(pincode: str) -> str | None:
    circle = int(pincode[:2])
    for low, high, state in _PINCODE_STATE_RANGES:
        if low <= circle <= high:
            return state
    return None


def check_pincode(session: Session, company_id: str, pincode: str) -> dict:
    """Resolve an Indian PIN code: region, deliverability, ETA and COD."""
    pincode = normalize_pincode(pincode)
    zone = _resolve_zone(session, company_id, pincode)
    result = {
        "pincode": pincode,
        "valid": True,
        "state": _pincode_state(pincode),
        "city": _PINCODE_CITY.get(pincode[:3]),
        "deliverable": False,
        "eta_days": None,
        "cod_allowed": False,
        "configured": zone is not None,
    }
    if zone is not None:
        result.update(
            deliverable=zone.deliverable,
            eta_days=zone.eta_days,
            cod_allowed=zone.cod_allowed,
        )
    return result


def set_delivery_zone(
    session: Session, company_id: str, *, pincode: str, deliverable: bool, eta_days: int, cod_allowed: bool
) -> DeliveryZone:
    pincode = normalize_zone_code(pincode)
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
    """Cart payload for the storefront: product data plus the authoritative
    per-line pricing from `quote_cart` so the UI never computes totals itself."""
    cart = token_cart(session, company_id, token)
    rows = sales_svc.cart_items(session, cart.id)
    products = {
        p.id: p
        for p in session.execute(
            select(Product).where(Product.id.in_([i.product_id for i in rows]))
        ).scalars().all()
    } if rows else {}
    quote = sales_svc.quote_cart(session, cart)
    priced = {line["item_id"]: line for line in quote["lines"]}
    items = []
    for row in rows:
        product = products.get(row.product_id)
        line = priced.get(row.id, {})
        unit_price = line.get("unit_price") or (str(product.base_price) if product else "0")
        items.append(
            {
                "id": row.id,
                "product_id": row.product_id,
                "qty": str(row.qty),
                "name": product.name if product else "Item",
                "sku": product.sku if product else "",
                "price": unit_price,
                "unit_price": unit_price,
                "tax_amount": line.get("tax_amount", "0"),
                "line_total": line.get("line_total", "0"),
                "stock_type": product.stock_type if product else "stock",
                "image_url": product_image_url(product.id) if product else None,
            }
        )
    return {"id": cart.id, "status": cart.status, "token": token, "items": items, "quote": quote}


# ---- store info (public storefront bootstrap) ----
def store_info(session: Session, slug: str) -> dict:
    """Resolve a public storefront by its slug (no auth required).

    Leftover dev/test companies can share a slug, so pick the oldest match
    instead of letting the database return an arbitrary row.
    """
    company = session.scalar(
        select(Company)
        .where(
            Company.storefront_slug == slug.strip().lower(),
            Company.is_active.is_(True),
        )
        .order_by(Company.created_at, Company.id)
        .limit(1)
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
    """Available payment methods.

    Razorpay (cards/UPI/netbanking) is offered whenever keys are configured;
    without keys the storefront keeps its sandbox gateway so local development
    (and the demo seed) still works. COD depends on the pincode's zone.
    """
    from app.core.config import get_settings

    zone = None
    if pincode and pincode.strip():
        zone = _resolve_zone(session, company_id, normalize_pincode(pincode))
    out: list[dict] = []
    if get_settings().razorpay_configured:
        out.append(
            {
                "code": "razorpay",
                "label": "Cards / UPI / Netbanking",
                "provider": "razorpay",
                "available": True,
            }
        )
    else:
        out.extend({**method, "available": True} for method in MOCK_PAYMENT_METHODS)
        # Tells the checkout UI why the Razorpay window never opens: no keys.
        out.append(
            {
                "code": "razorpay",
                "label": "Cards / UPI / Netbanking",
                "provider": "razorpay",
                "available": False,
                "reason": "not_configured",
            }
        )
    cod_available = zone.cod_allowed if zone is not None else True
    out.append({**COD_METHOD, "available": cod_available})
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
    from app.modules.payments.models import PaymentRecord

    lines = sales_svc.get_order_lines(session, order.id)
    latest_payment = session.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == order.id, PaymentRecord.direction == "receipt")
        .order_by(PaymentRecord.occurred_at.desc())
    )
    return {
        "id": order.id,
        "payment_method": latest_payment.method if latest_payment else None,
        "payment_status": latest_payment.status if latest_payment else None,
        "doc_number": order.doc_number,
        "status": order.status,
        "payment_state": order.payment_state,
        "cancel_reason": order.cancel_reason,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
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
    raw_pincode = (address.get("pincode") or "").strip()
    pincode = normalize_pincode(raw_pincode) if raw_pincode else ""
    zones = session.execute(
        select(func.count()).select_from(DeliveryZone).where(DeliveryZone.company_id == company_id)
    ).scalar_one()
    zone = _resolve_zone(session, company_id, pincode) if pincode else None
    if zones and not pincode:
        raise BusinessRuleError("PINCODE_REQUIRED", "A delivery PIN code is required")
    if zones and (zone is None or not zone.deliverable):
        raise BusinessRuleError("NOT_DELIVERABLE", f"We do not deliver to {pincode}")

    method = (payload.get("payment_method") or "razorpay").lower()
    if method not in PAYMENT_METHOD_CODES:
        raise BusinessRuleError("BAD_PAYMENT_METHOD", f"Unknown payment method '{method}'")
    available = {
        m["code"]
        for m in payment_methods(session, company_id, pincode=pincode or None)
        if m["available"]
    }
    if method not in available:
        raise BusinessRuleError(
            "PAYMENT_METHOD_UNAVAILABLE", f"'{method}' is not available for this checkout"
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
    # COD confirms the order now and books an open cash receipt that the
    # delivery step settles. Online capture (Razorpay) happens in the browser
    # after the order exists; only the sandbox methods are charged here.
    if method == "cod" and order.status == "pending_payment":
        sales_svc.accept_cash_on_delivery(
            session, company_id=company_id, order=order, actor_user_id=None
        )
        payment_state = order.payment_state
    if method in {"card", "upi"} and order.status == "pending_payment":
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
    # Release stock held by abandoned gateway checkouts before listing, so a
    # shopper never sees a stale "pending payment" order that can still be paid.
    sales_svc.expire_unpaid_orders(session, company_id=company_id)
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
    if method not in {"card", "upi"}:
        raise BusinessRuleError(
            "BAD_PAYMENT_METHOD",
            "Sandbox payments only; use the Razorpay checkout for online payments",
        )
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


# ---- Razorpay online payments ----
def _owned_order(session: Session, company_id: str, cart_token: str, order_id: str) -> SalesOrder:
    """An order is only reachable through the cart token that placed it."""
    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        raise NotFoundError("Sales order")
    cart = session.get(Cart, order.cart_id) if order.cart_id else None
    if cart is None or cart.token != cart_token:
        raise BusinessRuleError("ORDER_NOT_OWNED", "This order belongs to another cart")
    return order


def _late_capture_refund(
    session: Session, *, order: SalesOrder, payment_id: str, amount, currency: str | None
) -> dict:
    """Give back money captured after the order expired or was cancelled.

    Books the capture as a receipt and the refund as a payment out, so the
    payment trail shows both legs. Replays are keyed by the Razorpay payment id
    (`Refund of <payment_id>`), so a duplicate webhook never refunds twice.
    """
    from app.modules.payments import service as payments
    from app.modules.payments.models import PaymentRecord

    already = session.scalar(
        select(PaymentRecord).where(
            PaymentRecord.provider == "razorpay",
            PaymentRecord.direction == "payment",
            PaymentRecord.notes == f"Refund of {payment_id}",
        )
    )
    if already is not None:
        order.payment_state = "refunded"
        session.flush()
        return {"refunded": True, "replayed": True, "refund_payment_id": already.id}

    captured = payments.record_captured_payment(
        session,
        company_id=order.company_id,
        actor_user_id=None,
        customer_id=order.customer_id,
        order_id=order.id,
        amount=amount,
        currency=currency or order.currency,
        method="razorpay",
        provider="razorpay",
        provider_ref=payment_id,
        notes=f"Late capture on cancelled order {order.doc_number}",
    )
    refund = payments.provider_refund(
        session,
        company_id=order.company_id,
        actor_user_id=None,
        original=captured,
        amount=amount,
    )
    refund.direction = "payment"
    order.payment_state = "refunded"
    session.flush()
    return {"refunded": True, "replayed": False, "refund_payment_id": refund.id}


def _razorpay_intent(session: Session, company_id: str, order_id: str):
    from app.modules.payments.models import PaymentRecord

    return session.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.company_id == company_id,
            PaymentRecord.order_id == order_id,
            PaymentRecord.provider == "razorpay",
            PaymentRecord.status == "pending",
        )
        .order_by(PaymentRecord.created_at.desc())
    )


def create_razorpay_order(
    session: Session, *, company_id: str, cart_token: str, order_id: str
) -> dict:
    """Server-side Razorpay order for a pending storefront order.

    The gateway order id is stored on a pending PaymentRecord so the browser
    cannot redirect a payment to a different order (or a different tenant).
    """
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.modules.companies.service import rate_for
    from app.modules.payments import razorpay
    from app.modules.payments.models import PaymentRecord

    settings = get_settings()
    if not settings.razorpay_configured:
        raise BusinessRuleError(
            "RAZORPAY_NOT_CONFIGURED",
            "Online payments are unavailable: set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET",
        )
    order = _owned_order(session, company_id, cart_token, order_id)
    if order.payment_state == "paid":
        raise BusinessRuleError("ORDER_ALREADY_PAID", "This order is already paid")
    if order.status != "pending_payment":
        raise BusinessRuleError(
            "ORDER_NOT_PAYABLE", f"Order status '{order.status}' cannot be paid"
        )

    intent = _razorpay_intent(session, company_id, order.id)
    if intent is not None:
        gateway_order_id = intent.provider_ref.removeprefix("order:")
    else:
        company = session.get(Company, company_id)
        gateway = razorpay.create_order(
            amount_paise=razorpay.amount_to_paise(order.total),
            currency=order.currency,
            receipt=order.doc_number,
            notes={"order_id": order.id, "company_id": company_id, "doc_number": order.doc_number},
        )
        gateway_order_id = gateway["id"]
        exchange_rate = dec(
            rate_for(
                session,
                company_id=company_id,
                from_currency=order.currency,
                base_currency=company.base_currency if company else order.currency,
                on_date=order.order_date,
            )
        )
        intent = PaymentRecord(
            company_id=company_id,
            direction="receipt",
            method="razorpay",
            provider="razorpay",
            provider_ref=f"order:{gateway_order_id}",
            status="pending",
            amount=dec(order.total),
            currency=order.currency,
            exchange_rate=exchange_rate,
            amount_base=money(dec(order.total) * exchange_rate, 2),
            customer_id=order.customer_id,
            order_id=order.id,
            occurred_at=datetime.now(timezone.utc),
            idempotency_scope="razorpay_intent",
            notes=f"Razorpay order {gateway_order_id}",
        )
        session.add(intent)
        session.flush()

    company = session.get(Company, company_id)
    return {
        "key_id": settings.razorpay_key_id,
        "razorpay_order_id": gateway_order_id,
        "amount": razorpay.amount_to_paise(order.total),
        "currency": order.currency,
        "order_id": order.id,
        "doc_number": order.doc_number,
        "store_name": company.name if company else "Store",
        "description": f"Order {order.doc_number}",
    }


def verify_razorpay_payment(
    session: Session, *, company_id: str, cart_token: str, order_id: str,
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str,
) -> dict:
    """Confirm Checkout success: signature → payment captured → order paid."""
    from app.modules.payments import razorpay

    order = _owned_order(session, company_id, cart_token, order_id)
    if order.payment_state == "paid":
        # verified callback and webhook may both arrive; second call is a no-op
        return _order_out(session, order)
    intent = _razorpay_intent(session, company_id, order.id)
    if intent is None or intent.provider_ref != f"order:{razorpay_order_id}":
        if order.status == "cancelled":
            # The hold expired before the shopper finished paying. The signature
            # proves the capture is genuine, so refund it instead of booking it.
            razorpay.verify_payment_signature(
                order_id=razorpay_order_id,
                payment_id=razorpay_payment_id,
                signature=razorpay_signature,
            )
            payment = razorpay.fetch_payment(razorpay_payment_id)
            if payment.get("order_id") not in (None, razorpay_order_id):
                raise BusinessRuleError(
                    "RAZORPAY_ORDER_MISMATCH", "Payment belongs to a different order"
                )
            refund = _late_capture_refund(
                session,
                order=order,
                payment_id=razorpay_payment_id,
                amount=dec(payment.get("amount") or 0) / dec(100),
                currency=payment.get("currency"),
            )
            return {**_order_out(session, order), **refund}
        raise BusinessRuleError(
            "RAZORPAY_NO_INTENT", "No Razorpay order is pending for this order"
        )
    razorpay.verify_payment_signature(
        order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=razorpay_signature,
    )
    order, payment = sales_svc.confirm_external_payment(
        session,
        company_id=company_id,
        actor_user_id=None,
        order_id=order.id,
        provider="razorpay",
        provider_ref=razorpay_payment_id,
        method="razorpay",
        existing_payment=intent,
    )
    return {**_order_out(session, order), "payment_id": payment.id if payment else None}


def handle_razorpay_webhook(session: Session, *, raw_body: bytes, signature: str | None) -> dict:
    """Verify and apply Razorpay webhooks (capture events) idempotently."""
    import json

    from app.modules.payments import razorpay

    razorpay.verify_webhook_signature(raw_body, signature)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except ValueError as exc:
        raise BusinessRuleError("RAZORPAY_BAD_PAYLOAD", "Webhook body is not JSON") from exc

    event = payload.get("event", "")
    bundles = payload.get("payload") or {}
    payment_entity = (bundles.get("payment") or {}).get("entity") or {}
    order_entity = (bundles.get("order") or {}).get("entity") or {}
    notes = {**(order_entity.get("notes") or {}), **(payment_entity.get("notes") or {})}
    company_id = notes.get("company_id")
    order_id = notes.get("order_id")
    razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")
    razorpay_payment_id = payment_entity.get("id")

    result = {"event": event, "handled": False, "order_id": order_id}
    if event not in {"payment.captured", "order.paid", "payment.failed"}:
        return {**result, "ignored": True}
    if not company_id or not order_id or not razorpay_order_id:
        return {**result, "ignored": True}

    order = session.get(SalesOrder, order_id)
    if order is None or order.company_id != company_id:
        return result
    if event == "payment.failed":
        return {**result, "payment_state": order.payment_state, "failed": True}
    if order.payment_state == "paid":
        return {**result, "handled": True, "replayed": True, "status": order.status}
    if order.status == "cancelled":
        # Captured after the order expired (or was cancelled): refund in full.
        amount = dec(payment_entity.get("amount") or 0) / dec(100)
        if not razorpay_payment_id or amount <= 0:
            return {**result, "ignored": True, "reason": "no_payment_entity"}
        refund = _late_capture_refund(
            session,
            order=order,
            payment_id=razorpay_payment_id,
            amount=amount,
            currency=payment_entity.get("currency"),
        )
        return {
            **result,
            **refund,
            "handled": True,
            "status": order.status,
            "payment_state": order.payment_state,
        }

    intent = _razorpay_intent(session, company_id, order.id)
    if intent is None or intent.provider_ref != f"order:{razorpay_order_id}":
        return result
    order, payment = sales_svc.confirm_external_payment(
        session,
        company_id=company_id,
        actor_user_id=None,
        order_id=order.id,
        provider="razorpay",
        provider_ref=razorpay_payment_id or razorpay_order_id,
        method="razorpay",
        existing_payment=intent,
    )
    return {
        **result,
        "handled": True,
        "status": order.status,
        "payment_state": order.payment_state,
        "payment_id": payment.id if payment else None,
    }


# ---- cancellation & returns ----
def guest_cancel_order(
    session: Session, *, company_id: str, cart_token: str, order_id: str
) -> dict:
    """Cancel an order: unpaid releases stock, paid refunds through the gateway."""
    from app.modules.returns import service as returns_svc

    order = _owned_order(session, company_id, cart_token, order_id)
    result = returns_svc.cancel_order_with_refund(
        session,
        company_id=company_id,
        order_id=order.id,
        actor_user_id=None,
        reason="Cancelled by the shopper",
        cancel_reason="cancelled_by_customer",
    )
    return {**_order_out(session, order), **result, "cancelled": True}


def _return_out(session: Session, row) -> dict:
    from app.modules.returns import service as returns_svc

    return {
        "id": row.id,
        "doc_number": row.doc_number,
        "order_id": row.order_id,
        "status": row.status,
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "credit_note_id": row.credit_note_id,
        "refund_payment_id": row.refund_payment_id,
        "notes": row.notes,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "qty": str(line.qty),
                "unit_price": str(line.unit_price),
                "disposition": line.disposition,
            }
            for line in returns_svc.return_lines(session, row.id)
        ],
    }


def guest_order_returns(
    session: Session, company_id: str, cart_token: str, order_id: str
) -> list[dict]:
    from app.modules.returns.models import SalesReturn

    order = _owned_order(session, company_id, cart_token, order_id)
    rows = session.execute(
        select(SalesReturn)
        .where(SalesReturn.company_id == company_id, SalesReturn.order_id == order.id)
        .order_by(SalesReturn.created_at.desc())
    ).scalars().all()
    return [_return_out(session, row) for row in rows]


def guest_request_return(
    session: Session, *, company_id: str, cart_token: str, order_id: str,
    lines: list[dict], notes: str | None = None,
) -> dict:
    """Shopper return request (pending ERP approval/completion)."""
    from app.modules.returns import service as returns_svc

    order = _owned_order(session, company_id, cart_token, order_id)
    row = returns_svc.request_order_return(
        session,
        company_id=company_id,
        order_id=order.id,
        actor_user_id=None,
        lines=lines,
        notes=notes,
    )
    return _return_out(session, row)
