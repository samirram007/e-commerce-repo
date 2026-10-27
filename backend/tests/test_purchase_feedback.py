"""Purchase feedback and the return policy window.

Covers verified-purchase reviews (only paid orders, one per item, moderated
before publication, aggregated onto the product's rating), private order
experience feedback, and the shopper return window measured from delivery.
"""
import uuid
from datetime import datetime, timedelta, timezone

from tests.test_storefront_payments import _setup_store

API = "/api/v1"
SHOP = f"{API}/storefront/shop"


def _cart(client, ctx):
    resp = client.get(f"{SHOP}/cart", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _add(client, ctx, product_id, qty="1"):
    resp = client.post(
        f"{SHOP}/cart/items", headers=ctx["headers"], json={"product_id": product_id, "qty": qty}
    )
    assert resp.status_code == 200, resp.text


def _place(client, ctx, *, method="card", email=None):
    return client.post(
        f"{SHOP}/checkout",
        headers={**ctx["headers"], "Idempotency-Key": f"fb-{uuid.uuid4()}"},
        json={
            "name": "Feedback Shopper",
            "email": email or f"fb-{uuid.uuid4().hex[:8]}@example.com",
            "address": {"line1": "1 Test Road", "pincode": "560001", "country": "IN"},
            "payment_method": method,
        },
    )


def _state(client, ctx, order_id):
    resp = client.get(f"{SHOP}/orders/{order_id}/feedback", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _review(client, ctx, order_id, product_id, rating=5, **extra):
    return client.post(
        f"{SHOP}/orders/{order_id}/reviews",
        headers=ctx["headers"],
        json={"product_id": product_id, "rating": rating, **extra},
    )


def _paid_order(client, ctx):
    _add(client, ctx, ctx["product"]["id"])
    resp = _place(client, ctx, method="card")  # the sandbox gateway captures immediately
    assert resp.status_code == 200, resp.text
    order = resp.json()
    assert order["payment_state"] == "paid"
    return order


def _deliver(order_id: str, *, days_ago: int) -> None:
    """Mark an order delivered `days_ago` days back (delivery sets delivered_at)."""
    from sqlalchemy import text

    from app.db.session import get_session_factory

    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with get_session_factory()() as session:
        session.execute(
            text("UPDATE sales_orders SET status = 'delivered', delivered_at = :when WHERE id = :id"),
            {"when": when, "id": order_id},
        )
        session.commit()


def test_review_needs_a_paid_purchase(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _add(client, ctx, ctx["product"]["id"])
    order = _place(client, ctx, method="cod").json()
    assert order["payment_state"] != "paid"

    resp = _review(client, ctx, order["id"], ctx["product"]["id"])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NOT_PURCHASED"


def test_verified_review_is_moderated_then_published_with_rating(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    order = _paid_order(client, ctx)
    product_id = ctx["product"]["id"]

    state = _state(client, ctx, order["id"])
    assert state["can_review"] is True
    assert [(item["product_id"], item["reviewed"]) for item in state["items"]] == [(product_id, False)]

    created = _review(
        client, ctx, order["id"], product_id, rating=4, title="Great quality", body="Arrived in two days"
    )
    assert created.status_code == 201, created.text
    review = created.json()
    assert review["status"] == "pending" and review["rating"] == 4
    assert review["summary"]["count"] == 0  # pending reviews are not published

    duplicate = _review(client, ctx, order["id"], product_id)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALREADY_REVIEWED"

    # the storefront shows nothing until the store approves it
    published = client.get(f"{SHOP}/products/{product_id}/reviews", headers=ctx["headers"]).json()
    assert published["items"] == [] and published["summary"]["count"] == 0

    queue = client.get(f"{API}/feedback/reviews", headers=ctx["store"], params={"status": "pending"})
    assert queue.status_code == 200, queue.text
    assert queue.json()["counts"]["pending"] == 1
    assert queue.json()["items"][0]["product_name"] == ctx["product"]["name"]

    approved = client.patch(
        f"{API}/feedback/reviews/{review['id']}", headers=ctx["store"], json={"status": "approved"}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    published = client.get(f"{SHOP}/products/{product_id}/reviews", headers=ctx["headers"]).json()
    assert published["summary"] == {"average": "4.00", "count": 1}
    assert published["items"][0]["title"] == "Great quality"
    assert "moderation_note" not in published["items"][0]  # store-only field

    # the product's star rating follows the approved reviews
    detail = client.get(f"{SHOP}/products/{product_id}", headers=ctx["headers"]).json()
    assert float(detail["rating_avg"]) == 4.0

    # rejecting it (or deleting it) pulls the rating back down
    rejected = client.patch(
        f"{API}/feedback/reviews/{review['id']}", headers=ctx["store"], json={"status": "rejected"}
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert client.get(f"{SHOP}/products/{product_id}/reviews", headers=ctx["headers"]).json()["summary"]["count"] == 0


def test_review_rating_is_validated(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    order = _paid_order(client, ctx)
    too_many = _review(client, ctx, order["id"], ctx["product"]["id"], rating=6)
    assert too_many.status_code == 422


def test_order_experience_feedback_is_private_and_edited_in_place(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    order = _paid_order(client, ctx)

    empty = client.post(f"{SHOP}/orders/{order['id']}/feedback", headers=ctx["headers"], json={})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "EMPTY_FEEDBACK"

    resp = client.post(
        f"{SHOP}/orders/{order['id']}/feedback",
        headers=ctx["headers"],
        json={"delivery_rating": 5, "packaging_rating": 4, "service_rating": 5, "comment": "Well packed"},
    )
    assert resp.status_code == 201, resp.text
    first = resp.json()
    assert first["delivery_rating"] == 5 and first["comment"] == "Well packed"

    again = client.post(
        f"{SHOP}/orders/{order['id']}/feedback",
        headers=ctx["headers"],
        json={"delivery_rating": 3, "comment": "Late on the second try"},
    )
    assert again.status_code == 201
    assert again.json()["id"] == first["id"]  # one row per order, updated
    assert again.json()["delivery_rating"] == 3

    state = _state(client, ctx, order["id"])
    assert state["order_feedback"]["delivery_rating"] == 3

    listed = client.get(f"{API}/feedback/orders", headers=ctx["store"])
    assert listed.status_code == 200
    assert [row["order_id"] for row in listed.json()] == [order["id"]]


def test_return_window_is_enforced_from_delivery(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    settings = client.put(
        f"{API}/storefront/admin/settings",
        headers=ctx["store"],
        json={"return_window_days": 7},
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["return_window_days"] == 7

    order = _paid_order(client, ctx)
    _deliver(order["id"], days_ago=10)

    expired = client.post(
        f"{SHOP}/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}]},
    )
    assert expired.status_code == 400, expired.text
    assert expired.json()["error"]["code"] == "RETURN_WINDOW_EXPIRED"

    # the shopper's order carries the deadline so the page can show it
    listed = client.get(f"{SHOP}/orders", headers=ctx["headers"]).json()
    row = next(item for item in listed if item["id"] == order["id"])
    assert row["delivered_at"] is not None
    assert row["return_by"] is not None

    # a freshly delivered order is inside the window
    fresh = _paid_order(client, ctx)
    _deliver(fresh["id"], days_ago=1)
    ok = client.post(
        f"{SHOP}/orders/{fresh['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}]},
    )
    assert ok.status_code == 201, ok.text
