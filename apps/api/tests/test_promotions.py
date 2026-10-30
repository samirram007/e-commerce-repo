"""Coupons: discount math, storefront redemption, limits and the admin API."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.test_storefront_payments import _setup_store

API = "/api/v1"
SHOP = f"{API}/storefront/shop"


def _coupon(client, ctx, **overrides):
    payload = {
        "code": f"SAVE{uuid.uuid4().hex[:6].upper()}",
        "kind": "percent",
        "value": "10",
        **overrides,
    }
    resp = client.post(f"{API}/promotions", headers=ctx["store"], json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _gst(client, ctx, percentage="18"):
    """Give the store a default sales tax so the tax-on-discount rule is visible."""
    resp = client.post(
        f"{API}/taxes",
        headers=ctx["store"],
        json={
            "code": f"GST{percentage}",
            "name": f"GST {percentage}%",
            "percentage": percentage,
            "is_default_sales": True,
        },
    )
    assert resp.status_code == 201, resp.text


def _apply(client, ctx, code):
    return client.post(f"{SHOP}/cart/coupon", headers=ctx["headers"], json={"code": code})


def _cart(client, ctx):
    resp = client.get(f"{SHOP}/cart", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _place(client, ctx, *, email=None, method="cod"):
    return client.post(
        f"{SHOP}/checkout",
        headers={**ctx["headers"], "Idempotency-Key": f"k-{uuid.uuid4()}"},
        json={
            "name": "Coupon Shopper",
            "email": email or f"coupon-{uuid.uuid4().hex[:8]}@example.com",
            "address": {"line1": "1 Test Road", "pincode": "560001", "country": "IN"},
            "payment_method": method,
        },
    )


def test_percent_coupon_discounts_cart_and_order(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")  # carts one ₹1000 service item
    _gst(client, ctx)
    coupon = _coupon(client, ctx, kind="percent", value="10", description="10% off")

    applied = _apply(client, ctx, coupon["code"].lower())  # case-insensitive for the shopper
    assert applied.status_code == 200, applied.text
    quote = applied.json()["quote"]
    assert quote["subtotal"] == "1000.00"
    assert quote["discount_total"] == "100.00"
    # tax follows the discounted taxable value: 18% of 900
    assert quote["tax_total"] == "162.00"
    assert quote["total"] == "1062.00"
    assert quote["coupon"]["valid"] is True and quote["coupon"]["code"] == coupon["code"]
    assert quote["lines"][0]["discount"] == "100.00"

    order = _place(client, ctx)
    assert order.status_code == 200, order.text
    placed = order.json()
    assert placed["discount_total"] == "100.0000"
    assert placed["coupon_code"] == coupon["code"]
    assert placed["total"] == "1062.0000"

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.promotions.models import CouponRedemption
    from app.modules.sales.models import OrderLine

    with get_session_factory()() as session:
        # the line carries the coupon's share so the invoice reproduces the total
        line = session.execute(
            select(OrderLine).where(OrderLine.order_id == placed["id"])
        ).scalars().one()
        assert line.discount == Decimal("100.0000")
        redemption = session.execute(
            select(CouponRedemption).where(CouponRedemption.order_id == placed["id"])
        ).scalars().one()
        assert redemption.amount == Decimal("100.0000")

    ledger = client.get(
        f"{API}/promotions/{coupon['id']}/redemptions", headers=ctx["store"]
    ).json()
    assert [row["order_id"] for row in ledger] == [placed["id"]]
    listed = client.get(f"{API}/promotions", headers=ctx["store"]).json()
    assert listed["total"] == 1 and listed["items"][0]["code"] == coupon["code"]
    assert listed["items"][0]["redemptions"] == 1
    assert Decimal(listed["items"][0]["redeemed_amount"]) == Decimal("100")


def test_fixed_coupon_cannot_exceed_the_subtotal(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    coupon = _coupon(client, ctx, kind="fixed", value="5000")
    quote = _apply(client, ctx, coupon["code"]).json()["quote"]
    assert quote["discount_total"] == "1000.00"
    assert quote["tax_total"] == "0.00"
    assert quote["total"] == "0.00"


def test_unusable_codes_explain_themselves(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")

    missing = _apply(client, ctx, "NOPE-NOT-A-CODE")
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "COUPON_NOT_FOUND"

    small = _coupon(client, ctx, min_subtotal="5000")
    too_small = _apply(client, ctx, small["code"])
    assert too_small.status_code == 400
    assert too_small.json()["error"]["code"] == "COUPON_MIN_SUBTOTAL"

    past = datetime.now(timezone.utc) - timedelta(days=1)
    expired = _coupon(client, ctx, ends_at=past.isoformat())
    assert _apply(client, ctx, expired["code"]).json()["error"]["code"] == "COUPON_EXPIRED"

    future = datetime.now(timezone.utc) + timedelta(days=1)
    later = _coupon(client, ctx, starts_at=future.isoformat())
    assert _apply(client, ctx, later["code"]).json()["error"]["code"] == "COUPON_NOT_STARTED"

    off = _coupon(client, ctx)
    client.delete(f"{API}/promotions/{off['id']}", headers=ctx["store"])
    assert _apply(client, ctx, off["code"]).json()["error"]["code"] == "COUPON_INACTIVE"

    # an invalid code never sticks to the cart
    assert _cart(client, ctx)["quote"]["coupon"] is None


def test_coupon_can_target_one_product(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    other = client.post(
        f"{API}/catalog/products",
        headers=ctx["store"],
        json={
            "sku": f"OTHER-{uuid.uuid4().hex[:6]}",
            "name": "Another service",
            "base_price": "100",
            "base_cost": "0",
            "stock_type": "service",
            "is_sellable": True,
        },
    ).json()
    client.post(
        f"{SHOP}/cart/items", headers=ctx["headers"],
        json={"product_id": other["id"], "qty": 1},
    )

    unlisted = _coupon(client, ctx, scope="product", product_id=other["id"], value="50")
    # 50% off the ₹100 line only
    quote = _apply(client, ctx, unlisted["code"]).json()["quote"]
    assert quote["discount_total"] == "50.00"

    elsewhere = _coupon(client, ctx, scope="product", product_id=str(uuid.uuid4()), value="50")
    assert _apply(client, ctx, elsewhere["code"]).json()["error"]["code"] == "COUPON_NOT_APPLICABLE"


def test_usage_limits_stop_double_redemption(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    email = f"limit-{uuid.uuid4().hex[:8]}@example.com"
    once = _coupon(client, ctx, max_per_customer=1)

    def buy():
        client.post(
            f"{SHOP}/cart/items", headers=ctx["headers"],
            json={"product_id": ctx["product"]["id"], "qty": 1},
        )
        assert _apply(client, ctx, once["code"]).status_code == 200
        return _place(client, ctx, email=email)

    assert buy().status_code == 200
    second = buy()
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "COUPON_ALREADY_USED"

    total_cap = _coupon(client, ctx, max_redemptions=1)
    client.post(
        f"{SHOP}/cart/items", headers=ctx["headers"],
        json={"product_id": ctx["product"]["id"], "qty": 1},
    )
    assert _apply(client, ctx, total_cap["code"]).status_code == 200
    assert _place(client, ctx).status_code == 200
    client.post(
        f"{SHOP}/cart/items", headers=ctx["headers"],
        json={"product_id": ctx["product"]["id"], "qty": 1},
    )
    assert _apply(client, ctx, total_cap["code"]).json()["error"]["code"] == "COUPON_USAGE_LIMIT"


def test_removing_the_code_restores_full_price(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    _gst(client, ctx)
    coupon = _coupon(client, ctx)
    assert _apply(client, ctx, coupon["code"]).json()["quote"]["discount_total"] == "100.00"

    cleared = client.delete(f"{SHOP}/cart/coupon", headers=ctx["headers"])
    assert cleared.status_code == 200
    quote = cleared.json()["quote"]
    assert quote["discount_total"] == "0.00" and quote["total"] == "1180.00"


def test_coupon_admin_validates_and_deactivates(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")

    over = client.post(
        f"{API}/promotions",
        headers=ctx["store"],
        json={"code": "TOOMUCH", "kind": "percent", "value": "150"},
    )
    assert over.status_code == 400 and over.json()["error"]["code"] == "COUPON_BAD_VALUE"

    no_target = client.post(
        f"{API}/promotions",
        headers=ctx["store"],
        json={"code": "NOSCOPE", "kind": "fixed", "value": "10", "scope": "category"},
    )
    assert no_target.status_code == 400 and no_target.json()["error"]["code"] == "COUPON_BAD_SCOPE"

    made = _coupon(client, ctx, code="WELCOME10")
    clash = client.post(
        f"{API}/promotions",
        headers=ctx["store"],
        json={"code": "welcome10", "kind": "fixed", "value": "10"},
    )
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "COUPON_CODE_TAKEN"

    patched = client.patch(
        f"{API}/promotions/{made['id']}", headers=ctx["store"], json={"value": "25", "is_active": False}
    )
    assert patched.status_code == 200
    assert Decimal(patched.json()["value"]) == Decimal("25") and patched.json()["is_active"] is False

    page = client.get(f"{API}/promotions", headers=ctx["store"], params={"search": "welcome"}).json()
    assert [row["code"] for row in page["items"]] == ["WELCOME10"] and page["total"] == 1
    unknown_sort = client.get(
        f"{API}/promotions", headers=ctx["store"], params={"sort": "value; DROP TABLE"}
    )
    assert unknown_sort.status_code == 400
    assert unknown_sort.json()["error"]["code"] == "INVALID_SORT_FIELD"


def test_discount_allocation_adds_up_exactly():
    """Percentage coupons split across lines must not lose or invent paisa."""
    from app.modules.promotions.models import Coupon
    from app.modules.promotions.service import QuoteLine, compute_discount

    coupon = Coupon(code="SPLIT", kind="percent", value=Decimal("33.33"), scope="order")
    lines = [
        QuoteLine(product_id="a", category_id=None, amount=Decimal("999.99")),
        QuoteLine(product_id="b", category_id=None, amount=Decimal("333.33")),
        QuoteLine(product_id="c", category_id=None, amount=Decimal("0.05")),
    ]
    total, allocations = compute_discount(coupon, lines)
    assert total == sum(allocations.values())
    assert total == Decimal("444.41")  # 33.33% of 1333.37, half-up
