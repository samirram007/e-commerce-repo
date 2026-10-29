"""Configurable payment gateways.

Covers: secret encryption + masking, key/mode validation, mode-aware gateway
resolution (including refunds against the original mode), Razorpay/Stripe
signature verification with mocked HTTP, and the checkout confirm/webhook
idempotency contract (exactly one succeeded payment + invoice, ever).
"""
import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal

import httpx
import pytest

from app.modules.payments.adapters import (
    GatewayCredentials,
    IntentResult,
    RazorpayAdapter,
    StripeAdapter,
)
from app.shared.crypto import decrypt_secret, encrypt_secret

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

_COMPANY_SEQ = [0]


def _ensure_fiscal_year(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code in (201, 409), resp.text


def _allow_guest_checkout(client, auth_headers, company_id):
    resp = client.patch(
        f"/api/v1/companies/{company_id}",
        headers=auth_headers,
        json={"allow_guest_checkout": True},
    )
    assert resp.status_code == 200, resp.text


def _seed_stock(client, auth_headers, master_data, qty="100"):
    resp = client.post(
        "/api/v1/inventory/adjustments",
        headers=auth_headers,
        json={
            "location_id": master_data["bin_id"],
            "product_id": master_data["product_id"],
            "quantity": qty,
            "direction": "increase",
            "reason": "opening stock",
        },
    )
    assert resp.status_code in (200, 201), resp.text


def guest_headers(cid: str, token: str = "cart-payments-1") -> dict:
    return {
        "X-Company-Id": cid,
        "X-Cart-Token": token,
        "X-Anon-Id": "anon-payments",
    }


def guest_checkout(client, auth_headers, master_data, cid: str, *, key: str = "pay-key-1",
                   method: str = "card", token: str = "cart-payments-1"):
    headers = guest_headers(cid, token)
    resp = client.post(
        "/api/v1/storefront/shop/cart/items",
        headers=headers,
        json={"product_id": master_data["product_id"], "qty": "1"},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/api/v1/storefront/shop/checkout",
        headers={**headers, "Idempotency-Key": key},
        json={
            "name": "Guest Buyer",
            "email": "buyer@example.com",
            "phone": "9876543210",
            "address": {
                "line1": "1 Test Street",
                "city": "Testville",
                "region": "Delhi",
                "pincode": "110001",
            },
            "payment_method": method,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json(), headers


def put_gateway(client, auth_headers, provider: str, **payload):
    return client.put(f"/api/v1/payments/gateways/{provider}", headers=auth_headers, json=payload)


def stripe_sig(secret: str, body: bytes, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


RAZORPAY_TEST_KEYS = {
    "test_public_key": "rzp_test_1DP5mmOlF5G5ag",
    "test_secret": "testsecretkey123456",
    "test_webhook_secret": "whsec_test_abc",
}
STRIPE_TEST_KEYS = {
    "test_public_key": "pk_test_51EXAMPLE",
    "test_secret": "sk_test_51EXAMPLESECRET",
    "test_webhook_secret": "whsec_stripe_test",
}


# --------------------------------------------------------------------------- #
# encryption + masking
# --------------------------------------------------------------------------- #
def test_secret_encryption_round_trip():
    token = encrypt_secret("sk_live_supersecret")
    assert token != "sk_live_supersecret"
    assert decrypt_secret(token) == "sk_live_supersecret"


def test_gateway_api_never_returns_secrets(client, auth_headers):
    resp = put_gateway(
        client, auth_headers, "razorpay",
        is_enabled=True, supported_methods=["card", "upi"], priority=5, **RAZORPAY_TEST_KEYS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_enabled"] is True
    assert body["mode"] == "test"
    assert body["test"]["has_secret"] is True
    assert body["test"]["secret_hint"] == "3456"  # last 4 only
    assert body["test"]["has_webhook_secret"] is True
    assert body["webhook_url"].endswith(
        f"/api/v1/payments/webhooks/razorpay/{auth_headers['X-Company-Id']}"
    )

    listing = client.get("/api/v1/payments/gateways", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    # no secret material anywhere in any response
    assert "testsecretkey123456" not in listing.text
    assert "whsec_test_abc" not in listing.text
    assert "rzp_test_1DP5mmOlF5G5ag" in listing.text  # publishable key is fine

    providers = {g["provider"] for g in listing.json()}
    assert providers == {"razorpay", "stripe", "mock"}
    placeholder = next(g for g in listing.json() if g["provider"] == "stripe")
    assert placeholder["is_enabled"] is False and placeholder["configured"] is False


def test_omitted_secret_keeps_existing_and_null_clears(client, auth_headers):
    put_gateway(client, auth_headers, "stripe", is_enabled=True, **STRIPE_TEST_KEYS)
    # omitted secret → stored value survives
    resp = put_gateway(
        client, auth_headers, "stripe", is_enabled=True,
        test_public_key=STRIPE_TEST_KEYS["test_public_key"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["test"]["has_secret"] is True
    # explicit null → cleared
    resp = put_gateway(
        client, auth_headers, "stripe", is_enabled=False,
        test_secret=None, test_webhook_secret=None,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["test"]["has_secret"] is False
    assert resp.json()["test"]["has_webhook_secret"] is False


# --------------------------------------------------------------------------- #
# key/mode validation + mode switching
# --------------------------------------------------------------------------- #
def test_key_prefix_mode_mismatch_rejected(client, auth_headers):
    resp = put_gateway(
        client, auth_headers, "razorpay", is_enabled=True,
        test_public_key="rzp_live_notallowed", test_secret="whatever",
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "KEY_MODE_MISMATCH"

    resp = put_gateway(
        client, auth_headers, "stripe", is_enabled=True,
        live_public_key="pk_test_wrongmode", live_secret="sk_test_wrongmode",
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "KEY_MODE_MISMATCH"


def test_switch_to_live_requires_live_keys(client, auth_headers):
    put_gateway(client, auth_headers, "razorpay", is_enabled=True, **RAZORPAY_TEST_KEYS)

    resp = client.post(
        "/api/v1/payments/gateways/razorpay/mode",
        headers=auth_headers, json={"mode": "live"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "LIVE_KEYS_REQUIRED"

    # save live keys first, then the switch works
    resp = put_gateway(
        client, auth_headers, "razorpay", is_enabled=True,
        live_public_key="rzp_live_abc123", live_secret="livesecret_abc123",
        live_webhook_secret="whsec_live",
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/api/v1/payments/gateways/razorpay/mode",
        headers=auth_headers, json={"mode": "live"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["mode"] == "live"

    # ...and back
    resp = client.post(
        "/api/v1/payments/gateways/razorpay/mode",
        headers=auth_headers, json={"mode": "test"},
    )
    assert resp.json()["mode"] == "test"


def test_unknown_provider_rejected(client, auth_headers):
    resp = put_gateway(client, auth_headers, "paypal", is_enabled=True)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_PROVIDER"


@pytest.fixture()
def db_session(engine):
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_gateway(company_id: str) -> dict:
    return {
        "company_id": company_id,
        "provider": "razorpay",
        "is_enabled": True,
        "mode": "test",
        "supported_methods": ["card", "upi"],
        "priority": 10,
        "test_public_key": "rzp_test_abcd1234",
        "test_secret_encrypted": encrypt_secret("rzp_test_secret_value"),
        "test_webhook_secret_encrypted": encrypt_secret("rzp_test_whsec"),
        "live_public_key": "rzp_live_abcd1234",
        "live_secret_encrypted": encrypt_secret("rzp_live_secret_value"),
        "live_webhook_secret_encrypted": encrypt_secret("rzp_live_whsec"),
    }


def test_mode_switch_changes_resolved_credentials(db_session, company_id):
    from app.modules.payments.gateways import resolve_gateway
    from app.modules.payments.models import PaymentGatewayConfig

    db_session.add(PaymentGatewayConfig(**_seed_gateway(company_id)))
    db_session.flush()

    adapter, creds, config = resolve_gateway(db_session, company_id, "card")
    assert adapter.name == "razorpay"
    assert creds.mode == "test"
    assert creds.public_key == "rzp_test_abcd1234"
    assert creds.secret_key == "rzp_test_secret_value"
    assert creds.webhook_secret == "rzp_test_whsec"

    config.mode = "live"
    db_session.flush()
    adapter, creds, _ = resolve_gateway(db_session, company_id, "card")
    assert creds.mode == "live"
    assert creds.secret_key == "rzp_live_secret_value"

    # unsupported method never falls through to this provider (dev/test
    # resolves an unhandled method to the offline mock gateway)
    adapter, creds, config = resolve_gateway(db_session, company_id, "netbanking")
    assert adapter.name == "mock"
    assert config is None


def test_refund_uses_original_payment_mode(monkeypatch, db_session, company_id):
    """A test-mode charge must be refunded with test keys even after the
    company has flipped to live."""
    from app.modules.payments import service as payments_svc
    from app.modules.payments.adapters import ProviderChargeResult
    from app.modules.payments.gateways import get_gateway_by_name
    from app.modules.payments.models import PaymentGatewayConfig, PaymentRecord
    from datetime import datetime, timezone

    db_session.add(PaymentGatewayConfig(**_seed_gateway(company_id)))
    db_session.flush()

    original = PaymentRecord(
        company_id=company_id,
        direction="receipt",
        method="card",
        provider="razorpay",
        provider_ref="order_original_1",
        mode="test",
        status="succeeded",
        amount=Decimal("10.00"),
        currency="USD",
        exchange_rate=Decimal("1"),
        amount_base=Decimal("10.00"),
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(original)
    db_session.flush()

    seen = {}

    def fake_refund(self, creds, *, provider_ref, amount, currency, idempotency_key):
        seen["mode"] = creds.mode
        seen["public_key"] = creds.public_key
        seen["provider_ref"] = provider_ref
        return ProviderChargeResult("razorpay", "rfnd_1", True)

    monkeypatch.setattr(RazorpayAdapter, "refund", fake_refund)

    # company now runs live
    config = db_session.query(PaymentGatewayConfig).filter_by(company_id=company_id).one()
    config.mode = "live"
    db_session.flush()

    refund = payments_svc.provider_refund(
        db_session, company_id=company_id, actor_user_id=None,
        original=original, amount=Decimal("10.00"),
    )
    assert seen["mode"] == "test"
    assert seen["public_key"] == "rzp_test_abcd1234"
    assert refund.status == "succeeded"
    assert refund.mode == "test"

    # and get_gateway_by_name honours an explicit mode too
    _adapter, creds, _ = get_gateway_by_name(db_session, company_id, "razorpay", mode="test")
    assert creds.secret_key == "rzp_test_secret_value"


# --------------------------------------------------------------------------- #
# provider signature verification
# --------------------------------------------------------------------------- #
def _razorpay_creds() -> GatewayCredentials:
    return GatewayCredentials(
        mode="test", public_key="rzp_test_key", secret_key="razorpay_secret",
        webhook_secret="razorpay_whsec",
    )


def test_razorpay_client_signature_valid_and_invalid():
    adapter = RazorpayAdapter()
    creds = _razorpay_creds()
    order_id, payment_id = "order_abc", "pay_xyz"
    good = hmac.new(
        creds.secret_key.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()

    result = adapter.verify_client_payment(
        creds,
        payload={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": good,
        },
    )
    assert result.succeeded is True and result.provider_ref == payment_id

    bad = adapter.verify_client_payment(
        creds,
        payload={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": "0" * 64,
        },
    )
    assert bad.succeeded is False and bad.error_code == "BAD_SIGNATURE"

    missing = adapter.verify_client_payment(creds, payload={"razorpay_order_id": order_id})
    assert missing.succeeded is False and missing.error_code == "MISSING_FIELDS"


def test_razorpay_webhook_signature_valid_and_invalid():
    from app.core.exceptions import BusinessRuleError

    adapter = RazorpayAdapter()
    creds = _razorpay_creds()
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {"entity": {"id": "pay_1", "order_id": "order_1", "amount": 105000}}
            },
        }
    ).encode()
    good = hmac.new(creds.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    event = adapter.parse_webhook(
        creds, raw_body=body, headers={"X-Razorpay-Signature": good}
    )
    assert event.type == "payment.succeeded"
    assert event.intent_id == "order_1"
    assert event.provider_ref == "pay_1"
    assert event.amount == Decimal("1050.00")
    assert event.event_id

    with pytest.raises(BusinessRuleError) as exc:
        adapter.parse_webhook(creds, raw_body=body, headers={"X-Razorpay-Signature": "bad"})
    assert exc.value.code == "WEBHOOK_BAD_SIGNATURE"

    with pytest.raises(BusinessRuleError) as exc:
        adapter.parse_webhook(creds, raw_body=body, headers={})
    assert exc.value.code == "WEBHOOK_BAD_SIGNATURE"

    # unknown event types are reported as unsupported (acked, not retried forever)
    failed_body = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": {"id": "p", "order_id": "o", "amount": 5}}}}).encode()
    failed_sig = hmac.new(creds.webhook_secret.encode(), failed_body, hashlib.sha256).hexdigest()
    failed = adapter.parse_webhook(creds, raw_body=failed_body, headers={"X-Razorpay-Signature": failed_sig})
    assert failed.type == "payment.failed"


def _stripe_creds() -> GatewayCredentials:
    return GatewayCredentials(
        mode="test", public_key="pk_test_x", secret_key="sk_test_x",
        webhook_secret="stripe_whsec",
    )


def test_stripe_webhook_signature_valid_invalid_and_expired():
    from app.core.exceptions import BusinessRuleError

    adapter = StripeAdapter()
    creds = _stripe_creds()
    body = json.dumps(
        {
            "id": "evt_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123", "amount": 2599}},
        }
    ).encode()

    event = adapter.parse_webhook(
        creds, raw_body=body, headers={"Stripe-Signature": stripe_sig("stripe_whsec", body)}
    )
    assert event.type == "payment.succeeded"
    assert event.intent_id == "pi_123"
    assert event.amount == Decimal("25.99")
    assert event.event_id == "evt_1"

    with pytest.raises(BusinessRuleError) as exc:
        adapter.parse_webhook(
            creds, raw_body=body,
            headers={"Stripe-Signature": stripe_sig("wrong_secret", body)},
        )
    assert exc.value.code == "WEBHOOK_BAD_SIGNATURE"

    stale = stripe_sig("stripe_whsec", body, ts=int(time.time()) - 600)
    with pytest.raises(BusinessRuleError) as exc:
        adapter.parse_webhook(creds, raw_body=body, headers={"Stripe-Signature": stale})
    assert exc.value.code == "WEBHOOK_STALE"

    with pytest.raises(BusinessRuleError) as exc:
        adapter.parse_webhook(creds, raw_body=body, headers={})
    assert exc.value.code == "WEBHOOK_BAD_SIGNATURE"


# --------------------------------------------------------------------------- #
# HTTP adapters (mocked transport — no network)
# --------------------------------------------------------------------------- #
def test_razorpay_create_intent_and_error_mapping():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content.decode()
        captured["idempotency"] = request.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"id": "order_1"})

    adapter = RazorpayAdapter(transport=httpx.MockTransport(handler))
    creds = _razorpay_creds()
    result = adapter.create_intent(
        creds, amount=Decimal("10.50"), currency="INR", receipt="SO-1",
        customer={}, idempotency_key="intent-1",
    )
    assert captured["url"] == "https://api.razorpay.com/v1/orders"
    expected_auth = "Basic " + base64.b64encode(b"rzp_test_key:razorpay_secret").decode()
    assert captured["auth"] == expected_auth
    sent = json.loads(captured["body"])
    assert sent["amount"] == "1050" and sent["currency"] == "INR"  # minor units, never floats
    assert captured["idempotency"] == "intent-1"
    assert result.intent_id == "order_1"
    assert result.client_payload == {
        "provider": "razorpay", "mode": "test", "key": "rzp_test_key",
        "order_id": "order_1", "amount": 1050, "currency": "INR",
    }

    # error mapping: provider 4xx → PAYMENT_PROVIDER_ERROR, body not echoed raw
    failing = RazorpayAdapter(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": {"message": "bad order", "code": "BAD_REQUEST"}})
        )
    )
    from app.core.exceptions import BusinessRuleError

    with pytest.raises(BusinessRuleError) as exc:
        failing.create_intent(
            _razorpay_creds(), amount=Decimal("1"), currency="INR", receipt="SO-2",
            customer={}, idempotency_key="k",
        )
    assert exc.value.code == "PAYMENT_PROVIDER_ERROR"
    assert "bad order" in exc.value.message


def test_stripe_create_intent_and_verify():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["idempotency"] = request.headers.get("Idempotency-Key")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"id": "pi_1", "client_secret": "pi_1_secret"})

    adapter = StripeAdapter(transport=httpx.MockTransport(handler))
    creds = _stripe_creds()
    result = adapter.create_intent(
        creds, amount=Decimal("99.99"), currency="USD", receipt="SO-9",
        customer={"ref": "cust-1"}, idempotency_key="intent-9",
    )
    assert captured["url"] == "https://api.stripe.com/v1/payment_intents"
    assert captured["auth"] == "Bearer sk_test_x"
    assert captured["idempotency"] == "intent-9"
    assert "amount=9999" in captured["body"]
    assert "automatic_payment_methods%5Benabled%5D=true" in captured["body"] or \
        "automatic_payment_methods[enabled]=true" in captured["body"]
    assert result.client_payload["client_secret"] == "pi_1_secret"
    assert result.client_payload["publishable_key"] == "pk_test_x"

    # verify: succeeded vs not
    def verify_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "pi_1", "status": "succeeded", "amount": 9999})

    ok = StripeAdapter(transport=httpx.MockTransport(verify_handler))
    verified = ok.verify_client_payment(creds, payload={"payment_intent_id": "pi_1"})
    assert verified.succeeded is True and verified.amount == Decimal("99.99")

    pending = StripeAdapter(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"id": "pi_1", "status": "requires_payment_method"})
        )
    )
    not_ok = pending.verify_client_payment(creds, payload={"payment_intent_id": "pi_1"})
    assert not_ok.succeeded is False and not_ok.error_code == "NOT_SUCCEEDED"


# --------------------------------------------------------------------------- #
# end-to-end: mock checkout → confirm → paid + invoice (idempotent)
# --------------------------------------------------------------------------- #
def test_mock_checkout_intent_then_confirm_pays_and_posts_invoice(
    client, auth_headers, master_data, company_id
):
    _ensure_fiscal_year(client, auth_headers)
    _allow_guest_checkout(client, auth_headers, company_id)
    _seed_stock(client, auth_headers, master_data)

    order, headers = guest_checkout(client, auth_headers, master_data, company_id)
    assert order["status"] == "pending_payment"
    assert order["payment_state"] != "paid"
    assert order["payment"]["provider"] == "mock"
    assert order["payment"]["mode"] == "test"
    assert order["payment"]["client_payload"]["intent_id"].startswith("mock_order_")
    order_id = order["id"]

    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order_id}/payment/confirm",
        headers=headers, json={"payment_id": "mock_payment"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "paid"
    assert body["payment_state"] == "paid"
    assert body["invoice_id"] is not None
    assert body["payment"]["status"] == "succeeded"

    invoice = client.get(f"/api/v1/invoices/{body['invoice_id']}", headers=auth_headers).json()
    assert invoice["status"] == "posted"

    # second confirm is a replay: no duplicate payment, no duplicate invoice
    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order_id}/payment/confirm",
        headers=headers, json={"payment_id": "mock_payment"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoice_id"] == body["invoice_id"]

    payments = client.get("/api/v1/payments", headers=auth_headers).json()
    succeeded = [p for p in payments if p.get("order_id") == order_id and p["status"] == "succeeded"]
    assert len(succeeded) == 1
    assert succeeded[0]["mode"] == "test"
    invoices = [i for i in client.get("/api/v1/invoices", headers=auth_headers).json()]
    assert len(invoices) == 1


def test_payment_methods_report_provider_and_mode(client, auth_headers, company_id):
    # no gateway configured yet → mock fallback outside production
    resp = client.get("/api/v1/storefront/shop/payment-methods", headers={"X-Company-Id": company_id})
    assert resp.status_code == 200, resp.text
    methods = {m["code"]: m for m in resp.json()}
    assert methods["card"]["available"] is True
    assert methods["card"]["provider"] == "mock"
    assert methods["card"]["mode"] == "test"
    assert methods["cod"]["provider"] == "cash"
    assert methods["cod"]["mode"] is None
    assert "secret" not in resp.text

    # enable razorpay for cards only → card resolves to razorpay/test
    resp = put_gateway(
        client, auth_headers, "razorpay",
        is_enabled=True, supported_methods=["card"], priority=1, **RAZORPAY_TEST_KEYS,
    )
    assert resp.status_code == 200, resp.text
    methods = {
        m["code"]: m
        for m in client.get(
            "/api/v1/storefront/shop/payment-methods", headers={"X-Company-Id": company_id}
        ).json()
    }
    assert methods["card"]["provider"] == "razorpay"
    assert methods["card"]["mode"] == "test"
    assert methods["upi"]["provider"] == "mock"  # razorpay doesn't handle upi here
    assert "testsecretkey123456" not in json.dumps(methods)


# --------------------------------------------------------------------------- #
# webhooks: verify, idempotency, ordering vs the browser callback
# --------------------------------------------------------------------------- #
def _razorpay_body(intent_id: str, event: str = "payment.captured", event_id: str = "evt_1") -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {"payment": {"entity": {"id": "pay_1", "order_id": intent_id, "amount": 1000}}},
        }
    ).encode()


def _razorpay_headers(body: bytes, secret: str = "whsec_test_abc") -> dict:
    return {"X-Razorpay-Signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}


def _prepare_razorpay_checkout(monkeypatch, client, auth_headers, master_data, company_id, key):
    """Enable Razorpay (stubbed HTTP) and place a guest order through it."""
    from app.modules.payments.adapters import RazorpayAdapter

    resp = put_gateway(
        client, auth_headers, "razorpay",
        is_enabled=True, supported_methods=["card", "upi"], priority=1, **RAZORPAY_TEST_KEYS,
    )
    assert resp.status_code == 200, resp.text

    def fake_create(self, creds, *, amount, currency, receipt, customer, idempotency_key):
        # unique per order — like a real gateway (and the shared test DB keeps
        # payment_records across tests, where (provider, provider_ref) is unique)
        intent_id = "order_" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
        return IntentResult(
            provider="razorpay",
            intent_id=intent_id,
            client_payload={
                "provider": "razorpay", "mode": creds.mode, "key": creds.public_key,
                "order_id": intent_id, "amount": 1000, "currency": currency.upper(),
            },
        )

    monkeypatch.setattr(RazorpayAdapter, "create_intent", fake_create)
    order, headers = guest_checkout(
        client, auth_headers, master_data, company_id, key=key, method="card"
    )
    assert order["payment"]["provider"] == "razorpay"
    assert order["payment"]["mode"] == "test"
    intent_id = order["payment"]["client_payload"]["order_id"]
    assert intent_id.startswith("order_")
    return order, headers, intent_id


def test_webhook_before_confirm_finalizes_once(
    monkeypatch, client, auth_headers, master_data, company_id
):
    _ensure_fiscal_year(client, auth_headers)
    _allow_guest_checkout(client, auth_headers, company_id)
    _seed_stock(client, auth_headers, master_data)
    order, headers, intent_id = _prepare_razorpay_checkout(
        monkeypatch, client, auth_headers, master_data, company_id, "wh-early"
    )

    body = _razorpay_body(intent_id)
    resp = client.post(
        f"/api/v1/payments/webhooks/razorpay/{company_id}",
        content=body, headers=_razorpay_headers(body),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["matched"] is True

    detail = client.get("/api/v1/storefront/shop/orders", headers=headers)
    paid = next(o for o in detail.json() if o["id"] == order["id"])
    assert paid["status"] == "paid" and paid["invoice_id"] is not None

    # duplicate delivery of the same event → replay, no second invoice
    resp = client.post(
        f"/api/v1/payments/webhooks/razorpay/{company_id}",
        content=body, headers=_razorpay_headers(body),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["replayed"] is True

    # the browser's late confirm changes nothing
    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/payment/confirm",
        headers=headers, json={"razorpay_order_id": intent_id, "razorpay_payment_id": "pay_1",
                               "razorpay_signature": hmac.new(
                                   b"testsecretkey123456", f"{intent_id}|pay_1".encode(), hashlib.sha256
                               ).hexdigest()},
    )
    assert resp.status_code == 200, resp.text

    payments = client.get("/api/v1/payments", headers=auth_headers).json()
    succeeded = [p for p in payments if p.get("order_id") == order["id"] and p["status"] == "succeeded"]
    assert len(succeeded) == 1
    assert len(client.get("/api/v1/invoices", headers=auth_headers).json()) == 1


def test_confirm_before_webhook_finalizes_once(
    monkeypatch, client, auth_headers, master_data, company_id
):
    _ensure_fiscal_year(client, auth_headers)
    _allow_guest_checkout(client, auth_headers, company_id)
    _seed_stock(client, auth_headers, master_data)
    order, headers, intent_id = _prepare_razorpay_checkout(
        monkeypatch, client, auth_headers, master_data, company_id, "wh-late"
    )

    signature = hmac.new(b"testsecretkey123456", f"{intent_id}|pay_1".encode(), hashlib.sha256).hexdigest()
    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/payment/confirm",
        headers=headers,
        json={"razorpay_order_id": intent_id, "razorpay_payment_id": "pay_1",
              "razorpay_signature": signature},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paid"

    body = _razorpay_body(intent_id, event_id="evt_late")
    resp = client.post(
        f"/api/v1/payments/webhooks/razorpay/{company_id}",
        content=body, headers=_razorpay_headers(body),
    )
    assert resp.status_code == 200, resp.text

    payments = client.get("/api/v1/payments", headers=auth_headers).json()
    succeeded = [p for p in payments if p.get("order_id") == order["id"] and p["status"] == "succeeded"]
    assert len(succeeded) == 1
    assert len(client.get("/api/v1/invoices", headers=auth_headers).json()) == 1


def test_webhook_bad_signature_rejected(monkeypatch, client, auth_headers, master_data, company_id):
    _ensure_fiscal_year(client, auth_headers)
    _allow_guest_checkout(client, auth_headers, company_id)
    _seed_stock(client, auth_headers, master_data)
    order, headers, intent_id = _prepare_razorpay_checkout(
        monkeypatch, client, auth_headers, master_data, company_id, "wh-bad"
    )

    body = _razorpay_body(intent_id)
    resp = client.post(
        f"/api/v1/payments/webhooks/razorpay/{company_id}",
        content=body, headers={"X-Razorpay-Signature": "0" * 64},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "WEBHOOK_BAD_SIGNATURE"

    # order untouched
    detail = client.get("/api/v1/storefront/shop/orders", headers=headers)
    assert next(o for o in detail.json() if o["id"] == order["id"])["status"] == "pending_payment"


def test_webhook_payment_failed_keeps_order_pending(
    monkeypatch, client, auth_headers, master_data, company_id
):
    _ensure_fiscal_year(client, auth_headers)
    _allow_guest_checkout(client, auth_headers, company_id)
    _seed_stock(client, auth_headers, master_data)
    order, headers, intent_id = _prepare_razorpay_checkout(
        monkeypatch, client, auth_headers, master_data, company_id, "wh-fail"
    )

    body = _razorpay_body(intent_id, event="payment.failed", event_id="evt_fail")
    resp = client.post(
        f"/api/v1/payments/webhooks/razorpay/{company_id}",
        content=body, headers=_razorpay_headers(body),
    )
    assert resp.status_code == 200, resp.text

    payments = client.get("/api/v1/payments", headers=auth_headers).json()
    failed = [p for p in payments if p.get("order_id") == order["id"] and p["status"] == "failed"]
    assert len(failed) == 1
    detail = client.get("/api/v1/storefront/shop/orders", headers=headers)
    assert next(o for o in detail.json() if o["id"] == order["id"])["status"] == "pending_payment"

    # shopper can retry: a fresh intent is created for the same pending order
    resp = client.post(
        f"/api/v1/storefront/shop/orders/{order['id']}/pay",
        headers=headers, json={"method": "card"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment"]["provider"] == "razorpay"


def test_gateway_test_connection_endpoint(client, auth_headers, monkeypatch):
    resp = client.post("/api/v1/payments/gateways/mock/test", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # never configured → clear 404, not a crash
    resp = client.post("/api/v1/payments/gateways/razorpay/test", headers=auth_headers)
    assert resp.status_code == 404

    put_gateway(client, auth_headers, "razorpay", is_enabled=True, **RAZORPAY_TEST_KEYS)
    # mock the provider HTTP call — tests must never hit the network
    monkeypatch.setattr(
        RazorpayAdapter, "test_connection",
        lambda self, creds: (True, f"Connected to Razorpay ({creds.mode} mode)"),
    )
    resp = client.post("/api/v1/payments/gateways/razorpay/test", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert resp.json()["mode"] == "test"