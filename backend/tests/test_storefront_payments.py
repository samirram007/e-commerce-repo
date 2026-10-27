"""Storefront payments: Razorpay order/verify/webhook, cancellation and returns."""
import hashlib
import hmac
import uuid

import pytest

_SEQ = [0]


def _sig(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


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


def _place(client, ctx, *, method="razorpay", pincode="560001"):
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


def test_checkout_commits_the_order_before_the_response_is_sent(client, admin_headers, razorpay_stub):
    """Checkout must be durable before its reply leaves the app.

    The shopper's browser asks for the Razorpay order that reads this row the
    moment it has the reply, and FastAPI runs `get_db`'s commit *after* the
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
                "payment_method": "razorpay",
            },
        )

    assert placed.status_code == 200, placed.text
    assert seen, "the probe never saw the reply"
    # Every other connection must already see the new order at that point: that
    # is what lets the razorpay follow-up find it.
    assert seen[0] == before + 1


@pytest.fixture
def razorpay_stub(monkeypatch):
    """Configure fake Razorpay keys and stub the Orders API (no network)."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_key", raising=False)
    monkeypatch.setattr(settings, "razorpay_key_secret", "rzp_test_secret", raising=False)
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "whsec_test", raising=False)

    created: list[dict] = []

    def fake_create_order(**kwargs):
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        created.append({"id": order_id, **kwargs})
        return {"id": order_id, "amount": kwargs["amount_paise"], "currency": kwargs["currency"]}

    refunds: list[dict] = []

    def fake_refund(payment_id, *, amount_paise, notes=None):
        refund_id = f"rfnd_{uuid.uuid4().hex[:14]}"
        refunds.append({"id": refund_id, "payment_id": payment_id, "amount_paise": amount_paise})
        return {"id": refund_id, "payment_id": payment_id, "amount": amount_paise, "status": "processed"}

    payments_seen: dict[str, dict] = {}

    def fake_fetch_payment(payment_id):
        if payment_id not in payments_seen:
            raise AssertionError(f"unexpected fetch_payment({payment_id})")
        return payments_seen[payment_id]

    monkeypatch.setattr("app.modules.payments.razorpay.create_order", fake_create_order)
    monkeypatch.setattr("app.modules.payments.razorpay.refund", fake_refund)
    monkeypatch.setattr("app.modules.payments.razorpay.fetch_payment", fake_fetch_payment)
    return {
        "secret": "rzp_test_secret",
        "webhook": "whsec_test",
        "created": created,
        "refunds": refunds,
        "payments": payments_seen,
    }


def test_razorpay_order_and_signature_confirms_payment(client, admin_headers, razorpay_stub):
    ctx = _setup_store(client, admin_headers, price="1250")
    methods = client.get(
        "/api/v1/storefront/shop/payment-methods", headers=ctx["headers"]
    ).json()
    # keys configured: checkout offers Razorpay instead of the sandbox methods
    assert any(m["code"] == "razorpay" and m["available"] for m in methods)
    assert not any(m["code"] in {"card", "upi"} for m in methods)

    placed = _place(client, ctx)
    assert placed.status_code == 200, placed.text
    order = placed.json()
    assert order["status"] == "pending_payment" and order["payment_state"] == "unpaid"

    gateway = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    )
    assert gateway.status_code == 200, gateway.text
    payload = gateway.json()
    assert payload["razorpay_order_id"].startswith("order_")
    assert payload["amount"] == 125000 and payload["currency"] == "INR"
    assert payload["key_id"] == "rzp_test_key"
    rz_order_id = payload["razorpay_order_id"]

    # creating again reuses the same gateway order (no duplicate intent)
    again = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    ).json()
    assert again["razorpay_order_id"] == rz_order_id
    assert len(razorpay_stub["created"]) == 1

    payment_id = "pay_test_success"
    signature = _sig(razorpay_stub["secret"], f"{rz_order_id}|{payment_id}")
    verified = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay/verify",
        headers=ctx["headers"],
        json={
            "razorpay_order_id": rz_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        },
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["status"] == "paid" and body["payment_state"] == "paid"
    assert body["invoice_id"]

    # replaying the verified callback does not book a second payment
    replay = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay/verify",
        headers=ctx["headers"],
        json={
            "razorpay_order_id": rz_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        },
    )
    assert replay.status_code == 200 and replay.json()["payment_state"] == "paid"

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.payments.models import PaymentRecord

    with get_session_factory()() as session:
        payments = session.execute(
            select(PaymentRecord).where(
                PaymentRecord.order_id == order["id"], PaymentRecord.status == "succeeded"
            )
        ).scalars().all()
        assert len(payments) == 1
        assert payments[0].provider == "razorpay"
        assert payments[0].provider_ref == payment_id


def test_razorpay_rejects_forged_signature(client, admin_headers, razorpay_stub):
    ctx = _setup_store(client, admin_headers)
    order = _place(client, ctx).json()
    rz_order_id = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    ).json()["razorpay_order_id"]

    forged = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay/verify",
        headers=ctx["headers"],
        json={
            "razorpay_order_id": rz_order_id,
            "razorpay_payment_id": "pay_forged",
            "razorpay_signature": "0" * 64,
        },
    )
    assert forged.status_code == 400
    assert forged.json()["error"]["code"] == "RAZORPAY_BAD_SIGNATURE"

    orders = client.get("/api/v1/storefront/shop/orders", headers=ctx["headers"]).json()
    assert orders[0]["payment_state"] == "unpaid"


def test_razorpay_webhook_capture_is_idempotent(client, admin_headers, razorpay_stub):
    ctx = _setup_store(client, admin_headers, price="500")
    order = _place(client, ctx).json()
    rz_order_id = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    ).json()["razorpay_order_id"]

    notes = {"company_id": ctx["cid"], "order_id": order["id"]}
    body = (
        '{"event":"payment.captured","payload":{'
        '"payment":{"entity":{"id":"pay_webhook_1","order_id":"%s","notes":%s}},'
        '"order":{"entity":{"id":"%s","notes":%s}}}}'
        % (rz_order_id, __import__("json").dumps(notes), rz_order_id, __import__("json").dumps(notes))
    ).encode()

    def post_webhook(signature: str | None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Razorpay-Signature"] = signature
        return client.post(
            "/api/v1/storefront/shop/payments/razorpay/webhook", headers=headers, content=body
        )

    unsigned = post_webhook(None)
    assert unsigned.status_code == 400 and unsigned.json()["error"]["code"] == "RAZORPAY_BAD_SIGNATURE"

    signature = _sig(razorpay_stub["webhook"], body.decode())
    first = post_webhook(signature)
    assert first.status_code == 200, first.text
    assert first.json()["handled"] is True

    orders = client.get("/api/v1/storefront/shop/orders", headers=ctx["headers"]).json()
    assert orders[0]["payment_state"] == "paid"

    replay = post_webhook(signature)
    assert replay.status_code == 200
    assert replay.json().get("replayed") is True

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.payments.models import PaymentRecord

    with get_session_factory()() as session:
        rows = session.execute(
            select(PaymentRecord).where(
                PaymentRecord.order_id == order["id"], PaymentRecord.status == "succeeded"
            )
        ).scalars().all()
        assert len(rows) == 1


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
    order = _place(client, ctx, method="card").json()
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
    order = _place(client, ctx, method="card").json()

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
    order = _place(client, ctx, method="card").json()

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


def test_unpaid_gateway_order_expires_and_releases_hold(client, admin_headers, razorpay_stub):
    """Abandoned Razorpay checkouts must not hold stock (or stay payable) forever."""
    ctx = _setup_store(client, admin_headers, price="500")
    order = _place(client, ctx).json()
    assert order["status"] == "pending_payment"

    from datetime import datetime, timedelta, timezone

    from app.db.session import get_session_factory
    from app.modules.sales import service as sales
    from app.modules.sales.models import SalesOrder

    # the shopper opened Razorpay and walked away, leaving an open intent
    gateway = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    )
    assert gateway.status_code == 200, gateway.text

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
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    )
    assert pay.status_code == 400


def _expire_order(ctx, order_id: str) -> None:
    """Backdate an order past the payment timeout and run the sweeper."""
    from datetime import datetime, timedelta, timezone

    from app.db.session import get_session_factory
    from app.modules.sales import service as sales
    from app.modules.sales.models import SalesOrder

    with get_session_factory()() as session:
        row = session.get(SalesOrder, order_id)
        row.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
        session.commit()
    with get_session_factory()() as session:
        assert sales.expire_unpaid_orders(session, company_id=ctx["cid"]) == 1
        session.commit()


def test_late_webhook_capture_on_expired_order_is_refunded(client, admin_headers, razorpay_stub):
    import json

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.payments.models import PaymentRecord
    from app.modules.sales.models import SalesOrder

    ctx = _setup_store(client, admin_headers, price="750")
    order = _place(client, ctx).json()
    rz_order_id = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    ).json()["razorpay_order_id"]
    _expire_order(ctx, order["id"])

    notes = {"company_id": ctx["cid"], "order_id": order["id"]}
    payment_id = "pay_late_1"
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": rz_order_id,
                        "amount": 75000,
                        "currency": "INR",
                        "notes": notes,
                    }
                },
                "order": {"entity": {"id": rz_order_id, "notes": notes}},
            },
        }
    ).encode()

    def post_webhook():
        return client.post(
            "/api/v1/storefront/shop/payments/razorpay/webhook",
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": _sig(razorpay_stub["webhook"], body.decode()),
            },
            content=body,
        )

    first = post_webhook()
    assert first.status_code == 200, first.text
    out = first.json()
    assert out["handled"] is True and out["refunded"] is True
    assert razorpay_stub["refunds"][0]["payment_id"] == payment_id
    assert razorpay_stub["refunds"][0]["amount_paise"] == 75000

    # the order records the money in and straight back out
    with get_session_factory()() as session:
        rows = list(
            session.execute(
                select(PaymentRecord).where(PaymentRecord.order_id == order["id"])
            ).scalars()
        )
        # the voided gateway intent, the late capture, and the refund back out
        legs = sorted((row.direction, row.status) for row in rows)
        assert legs == [
            ("payment", "succeeded"),
            ("receipt", "succeeded"),
            ("receipt", "voided"),
        ]
        order_row = session.get(SalesOrder, order["id"])
        assert order_row.status == "cancelled" and order_row.payment_state == "refunded"

    # a duplicate delivery never refunds twice
    replay = post_webhook()
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert len(razorpay_stub["refunds"]) == 1


def test_late_checkout_callback_refunds_expired_order(client, admin_headers, razorpay_stub):
    ctx = _setup_store(client, admin_headers, price="640")
    order = _place(client, ctx).json()
    rz_order_id = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    ).json()["razorpay_order_id"]
    _expire_order(ctx, order["id"])

    payment_id = "pay_late_2"
    razorpay_stub["payments"][payment_id] = {
        "id": payment_id,
        "order_id": rz_order_id,
        "amount": 64000,
        "currency": "INR",
        "status": "captured",
    }
    url = f"/api/v1/storefront/shop/orders/{order['id']}/razorpay/verify"

    forged = client.post(
        url,
        headers=ctx["headers"],
        json={
            "razorpay_order_id": rz_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": "0" * 64,
        },
    )
    assert forged.status_code == 400
    assert forged.json()["error"]["code"] == "RAZORPAY_BAD_SIGNATURE"
    assert razorpay_stub["refunds"] == []

    verified = client.post(
        url,
        headers=ctx["headers"],
        json={
            "razorpay_order_id": rz_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": _sig(razorpay_stub["secret"], f"{rz_order_id}|{payment_id}"),
        },
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["refunded"] is True
    assert body["payment_state"] == "refunded" and body["status"] == "cancelled"
    assert razorpay_stub["refunds"][0]["amount_paise"] == 64000


def test_razorpay_demo_mode_runs_without_gateway_credentials(monkeypatch):
    """The demo key drives checkout end to end with no Razorpay account."""
    from app.core.config import settings_refresh
    from app.core.exceptions import BusinessRuleError
    from app.modules.payments import razorpay

    monkeypatch.setenv("RAZORPAY_DEMO", "1")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_demo_storefront")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "demo_secret")
    settings_refresh()
    try:
        assert razorpay.is_demo()
        order = razorpay.create_order(amount_paise=50000, currency="INR", receipt="SO-1")
        assert order["id"].startswith("order_demo_")
        assert order["amount"] == 50000

        # the in-app demo checkout's fields are accepted ...
        assert razorpay.verify_payment_signature(
            order_id=order["id"], payment_id="pay_demo_abc123", signature="demo"
        )
        # ... a real payment id signed with the demo signature is not
        with pytest.raises(BusinessRuleError):
            razorpay.verify_payment_signature(
                order_id=order["id"], payment_id="pay_real_abc123", signature="demo"
            )
    finally:
        monkeypatch.undo()
        settings_refresh()


def test_demo_gateway_pays_order_end_to_end(client, admin_headers, monkeypatch):
    """A demo Razorpay key completes checkout without gateway credentials."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_demo_storefront", raising=False)
    monkeypatch.setattr(settings, "razorpay_key_secret", "demo_secret", raising=False)
    monkeypatch.setattr(settings, "razorpay_demo", False, raising=False)

    ctx = _setup_store(client, admin_headers, price="500")

    methods = client.get(
        "/api/v1/storefront/shop/payment-methods", headers=ctx["headers"]
    ).json()
    assert any(m["code"] == "razorpay" and m["available"] for m in methods)

    placed = _place(client, ctx, method="razorpay")
    assert placed.status_code == 200, placed.text
    order = placed.json()
    assert order["payment_state"] == "unpaid"

    intent = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay", headers=ctx["headers"]
    )
    assert intent.status_code == 200, intent.text
    payload = intent.json()
    assert payload["demo"] is True
    assert payload["razorpay_order_id"].startswith("order_demo_")

    verified = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/razorpay/verify",
        headers=ctx["headers"],
        json={
            "razorpay_order_id": payload["razorpay_order_id"],
            "razorpay_payment_id": "pay_demo_abc123",
            "razorpay_signature": "demo",
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["payment_state"] == "paid"
