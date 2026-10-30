"""Storefront payments: COD, intent → confirm, cancellation, returns and expiry.

Provider adapters (Razorpay/Stripe signatures, webhooks) are covered in
`test_payment_gateways.py`; with no gateway configured these tests run on the
offline mock gateway.
"""
import uuid

_SEQ = [0]


def _setup_store(client, admin_headers, *, price="1000"):
    """Company + sellable service product + guest cart (services need no stock)."""
    _SEQ[0] += 1
    seq = _SEQ[0]
    cid = client.post(
        "/api/v1/companies",
        headers=admin_headers,
        json={"name": f"Payments Co {seq}", "base_currency": "INR"},
    ).json()["id"]
    store = {"Authorization": admin_headers["Authorization"], "X-Company-Id": cid}
    product = client.post(
        "/api/v1/catalog/products",
        headers=store,
        json={
            "sku": f"PAY-SVC-{seq:03d}",
            "name": f"Consulting Hour {seq}",
            "base_price": price,
            "base_cost": "0",
            "stock_type": "service",
            "is_sellable": True,
        },
    ).json()

    from datetime import date

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.accounting.service import create_default_chart
    from app.modules.companies.models import Company
    from app.modules.fiscal_years import service as fiscal
    from app.modules.identity.models import User
    from app.modules.storefront import service as storefront

    with get_session_factory()() as session:
        company = session.get(Company, cid)
        company.allow_guest_checkout = True
        storefront.set_delivery_zone(
            session, cid, pincode="560001", deliverable=True, eta_days=2, cod_allowed=True
        )
        # paying an order issues + posts an invoice, so the company needs a
        # chart of accounts and a fiscal year covering today
        actor = session.execute(select(User)).scalars().first()
        create_default_chart(session, company=company)
        fiscal.create_fiscal_year(
            session,
            company_id=cid,
            start_date=date(date.today().year, 1, 1),
            end_date=date(date.today().year + 1, 12, 31),
            actor_user_id=actor.id if actor else None,
        )
        session.commit()

    headers = {"X-Company-Id": cid, "X-Cart-Token": f"pay-token-{seq:04d}-0001"}
    client.post(
        "/api/v1/storefront/shop/cart/items",
        headers=headers,
        json={"product_id": product["id"], "qty": 1},
    )
    return {"cid": cid, "store": store, "product": product, "headers": headers}


def _place(client, ctx, *, method="card", pincode="560001"):
    return client.post(
        "/api/v1/storefront/shop/checkout",
        headers={**ctx["headers"], "Idempotency-Key": f"k-{uuid.uuid4()}"},
        json={
            "name": "Paying Shopper",
            "email": f"payer-{uuid.uuid4().hex[:8]}@example.com",
            "address": {"line1": "1 Test Road", "pincode": pincode, "country": "IN"},
            "payment_method": method,
        },
    )


class _ProbeAtResponseStart:
    """ASGI wrapper that runs `probe` as soon as the app starts replying.

    That instant is *before* FastAPI tears the request's dependencies down, so it
    is exactly where the storefront's follow-up request can land.
    """

    def __init__(self, app, probe):
        self.app = app
        self.probe = probe

    async def __call__(self, scope, receive, send):
        async def send_with_probe(message):
            if message["type"] == "http.response.start":
                self.probe()
            await send(message)

        await self.app(scope, receive, send_with_probe)


def _place_paid(client, ctx, *, method="card"):
    """Place an online order and confirm it through the browser callback."""
    order = _place(client, ctx, method=method).json()
    assert order["status"] == "pending_payment" and order["payment"]["provider"] == "mock"
    confirmed = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/payment/confirm",
        headers=ctx["headers"],
        json={"payment_id": f"mock_pay_{uuid.uuid4().hex[:8]}"},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def test_checkout_commits_the_order_before_the_response_is_sent(client, admin_headers):
    """Checkout must be durable before its reply leaves the app.

    The shopper's browser confirms the payment against this row the moment it
    has the reply, and FastAPI runs `get_db`'s commit *after* the
    response is flushed — so the follow-up request could reach another connection
    first and fail with "Sales order not found".
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    from app.db.session import get_session_factory
    from app.main import app
    from app.modules.sales.models import SalesOrder

    def order_count() -> int:
        with get_session_factory()() as session:
            return session.scalar(select(func.count()).select_from(SalesOrder)) or 0

    ctx = _setup_store(client, admin_headers)
    before = order_count()
    seen: list[int] = []

    with TestClient(_ProbeAtResponseStart(app, lambda: seen.append(order_count()))) as probing:
        placed = probing.post(
            "/api/v1/storefront/shop/checkout",
            headers={**ctx["headers"], "Idempotency-Key": f"k-{uuid.uuid4()}"},
            json={
                "name": "Probe Shopper",
                "email": f"probe-{uuid.uuid4().hex[:8]}@example.com",
                "address": {"line1": "1 Test Road", "pincode": "560001", "country": "IN"},
                "payment_method": "card",
            },
        )

    assert placed.status_code == 200, placed.text
    assert seen, "the probe never saw the reply"
    # Every other connection must already see the new order at that point: that
    # is what lets the payment confirm find it.
    assert seen[0] == before + 1


def test_cancel_unpaid_order_releases_and_cancels(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    order = _place(client, ctx, method="cod").json()
    assert order["status"] == "confirmed" and order["payment_state"] == "unpaid"

    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/cancel", headers=ctx["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "cancelled" and body["payment_state"] == "unpaid"
    assert body["refund_payment_id"] is None
    assert body["cancel_reason"] == "cancelled_by_customer"

    # nothing was collected, so the open cash receipt is closed out
    from app.db.session import get_session_factory
    from app.modules.payments.models import PaymentRecord

    with get_session_factory()() as session:
        assert not session.query(PaymentRecord).filter(
            PaymentRecord.order_id == order["id"], PaymentRecord.status == "pending"
        ).all()

    again = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/cancel", headers=ctx["headers"]
    )
    assert again.status_code == 400 and again.json()["error"]["code"] == "ALREADY_CANCELLED"


def test_cash_on_delivery_collects_on_delivery_and_is_returnable(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    order = _place(client, ctx, method="cod").json()
    assert order["status"] == "confirmed" and order["payment_state"] == "unpaid"
    assert order["payment_method"] == "cod" and order["payment_status"] == "pending"
    assert order["invoice_id"] is None  # no revenue before the cash arrives

    from app.db.session import get_session_factory
    from app.modules.fulfillment import service as fulfillment
    from app.modules.payments.models import PaymentRecord
    from app.modules.sales.models import SalesOrder

    with get_session_factory()() as session:
        shipment = fulfillment.create_shipment(
            session, company_id=ctx["cid"], actor_user_id=None, order_id=order["id"]
        )
        for status in ("picked", "packed", "dispatched", "in_transit", "delivered"):
            fulfillment.transition_shipment(session, ctx["cid"], shipment.id, status, None)
        session.commit()

        row = session.get(SalesOrder, order["id"])
        assert row.status == "delivered"
        assert row.payment_state == "paid"
        assert row.invoice_id is not None
        paid = session.query(PaymentRecord).filter(
            PaymentRecord.order_id == row.id, PaymentRecord.status == "succeeded"
        ).one()
        assert paid.provider == "cash" and str(paid.amount) == "1000.0000"

    # delivered + paid: the shopper can request a return, and completion refunds cash
    created = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}]},
    )
    assert created.status_code == 201, created.text

    from app.modules.returns import service as returns

    with get_session_factory()() as session:
        return_row = returns.get_return(session, ctx["cid"], created.json()["id"])
        returns.approve_return(session, return_row, None)
        returns.complete_return(session, return_row, actor_user_id=None)
        session.commit()
        refund = session.get(PaymentRecord, return_row.refund_payment_id)
        assert refund.provider == "cash" and refund.direction == "payment"


def test_cancel_paid_order_refunds_and_credits(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="900")
    order = _place_paid(client, ctx)
    assert order["payment_state"] == "paid"

    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/cancel", headers=ctx["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "cancelled" and body["payment_state"] == "refunded"
    assert body["refund_payment_id"] and body["credit_note_id"]

    from app.db.session import get_session_factory
    from app.modules.payments.models import PaymentRecord

    with get_session_factory()() as session:
        refund = session.get(PaymentRecord, body["refund_payment_id"])
        assert refund is not None and refund.direction == "payment"
        assert refund.status == "succeeded"
        assert str(refund.amount) == "900.0000"


def test_returns_require_delivery_and_create_request(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="700")
    order = _place_paid(client, ctx)

    early = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}]},
    )
    assert early.status_code == 400 and early.json()["error"]["code"] == "NOT_DELIVERED"

    from app.db.session import get_session_factory
    from app.modules.sales.models import SalesOrder

    with get_session_factory()() as session:
        row = session.get(SalesOrder, order["id"])
        row.status = "delivered"
        session.commit()

    created = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}], "notes": "Wrong size"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "requested" and body["doc_number"]
    assert len(body["lines"]) == 1

    over = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 5}]},
    )
    assert over.status_code == 400 and over.json()["error"]["code"] == "OVER_RETURN"

    listed = client.get(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns", headers=ctx["headers"]
    ).json()
    assert [r["id"] for r in listed] == [body["id"]]


def test_returns_completion_refunds_customer(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="450")
    order = _place_paid(client, ctx)

    from app.db.session import get_session_factory
    from app.modules.returns import service as returns
    from app.modules.sales.models import SalesOrder

    with get_session_factory()() as session:
        row = session.get(SalesOrder, order["id"])
        row.status = "delivered"
        session.commit()

    created = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns",
        headers=ctx["headers"],
        json={"lines": [{"product_id": ctx["product"]["id"], "qty": 1}]},
    ).json()

    with get_session_factory()() as session:
        return_row = returns.get_return(session, ctx["cid"], created["id"])
        returns.approve_return(session, return_row, None)
        returns.complete_return(session, return_row, actor_user_id=None)
        session.commit()
        assert return_row.status == "completed"
        assert return_row.refund_payment_id and return_row.credit_note_id

    listed = client.get(
        f"/api/v1/storefront/shop/orders/{order['id']}/returns", headers=ctx["headers"]
    ).json()
    assert listed[0]["status"] == "completed"


def test_unpaid_gateway_order_expires_and_releases_hold(client, admin_headers):
    """Abandoned online checkouts must not hold stock (or stay payable) forever."""
    ctx = _setup_store(client, admin_headers, price="500")
    order = _place(client, ctx).json()
    assert order["status"] == "pending_payment"

    from datetime import datetime, timedelta, timezone

    from app.db.session import get_session_factory
    from app.modules.sales import service as sales
    from app.modules.sales.models import SalesOrder

    # checkout opened a provider intent and the shopper walked away
    assert order["payment"]["payment_id"]

    # a fresh order is inside the window and must be left alone
    with get_session_factory()() as session:
        assert sales.expire_unpaid_orders(session, company_id=ctx["cid"]) == 0
        session.rollback()

    with get_session_factory()() as session:
        row = session.get(SalesOrder, order["id"])
        row.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
        session.commit()

    # the storefront read sweeps expired gateway holds before listing
    listed = client.get("/api/v1/storefront/shop/orders", headers=ctx["headers"]).json()
    mine = next(o for o in listed if o["id"] == order["id"])
    assert mine["status"] == "cancelled" and mine["payment_state"] == "unpaid"
    assert mine["payment_status"] == "voided"
    assert mine["cancel_reason"] == "payment_timeout"

    # replaying the sweep is a no-op, and the order can no longer be paid
    with get_session_factory()() as session:
        assert sales.expire_unpaid_orders(session, company_id=ctx["cid"]) == 0
        session.rollback()
    pay = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/pay",
        headers=ctx["headers"],
        json={"method": "card"},
    )
    assert pay.status_code == 400
    late = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/payment/confirm",
        headers=ctx["headers"],
        json={"payment_id": "mock_late"},
    )
    assert late.status_code == 400
