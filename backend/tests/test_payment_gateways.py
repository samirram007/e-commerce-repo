"""Payment gateways: the admin control plane and how it drives the storefront.

Covers credential handling (write-only, env fallback), the enable-time rules
(required credentials, planned providers), the admin's checkout customisation
(label, instruments, display order, extra key/values) and the effect on the
shop's payment methods and checkout validation.
"""
import uuid

from tests.test_storefront_payments import _setup_store

API = "/api/v1"
SHOP = f"{API}/storefront/shop"
GATEWAYS = f"{API}/payments/gateways"


def _gateways(client, ctx):
    resp = client.get(GATEWAYS, headers=ctx["store"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _one(client, ctx, provider):
    return next(g for g in _gateways(client, ctx)["gateways"] if g["provider"] == provider)


def _save(client, ctx, provider, **payload):
    return client.put(f"{GATEWAYS}/{provider}", headers=ctx["store"], json=payload)


def _methods(client, ctx, pincode=None):
    resp = client.get(
        f"{SHOP}/payment-methods", headers=ctx["headers"], params={"pincode": pincode} if pincode else {}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _place(client, ctx, method):
    """Guest checkout with one payment method, for validation checks."""
    return client.post(
        f"{SHOP}/checkout",
        headers={**ctx["headers"], "Idempotency-Key": f"gw-{uuid.uuid4()}"},
        json={
            "name": "Gateway Shopper",
            "email": f"gw-{uuid.uuid4().hex[:8]}@example.com",
            "address": {"line1": "1 Test Road", "pincode": "560001", "country": "IN"},
            "payment_method": method,
        },
    )


def test_catalog_lists_every_provider_unconfigured(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    data = _gateways(client, ctx)
    codes = [provider["code"] for provider in data["providers"]]
    for expected in ("razorpay", "stripe", "paypal", "phonepe", "paytm", "cod"):
        assert expected in codes
    razorpay = next(provider for provider in data["providers"] if provider["code"] == "razorpay")
    assert razorpay["status"] == "ready" and razorpay["kind"] == "hosted_modal"
    # the panel is generated from the registry: fields and options come with it
    assert [field["key"] for field in razorpay["credential_fields"]][:2] == ["key_id", "key_secret"]
    assert any(field["key"] == "methods" for field in razorpay["settings_fields"])

    gateway = _one(client, ctx, "razorpay")
    assert gateway["is_enabled"] is False and gateway["configured"] is False
    assert gateway["source"] == "unset" and gateway["credential_keys"] == []


def test_enabling_requires_credentials_and_secrets_are_write_only(client, admin_headers):
    ctx = _setup_store(client, admin_headers)

    refused = _save(client, ctx, "razorpay", is_enabled=True)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "GATEWAY_NOT_CONFIGURED"

    saved = _save(
        client,
        ctx,
        "razorpay",
        is_enabled=True,
        mode="live",
        label="Pay online",
        priority=1,
        credentials={"key_id": "rzp_live_abc", "key_secret": "shhh-secret", "webhook_secret": "whsec"},
        settings={"methods": ["upi"], "min_order": "100", "max_order": "50000", "instructions": "UPI only"},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["is_enabled"] is True and body["mode"] == "live" and body["source"] == "company"
    assert body["credential_keys"] == ["key_id", "key_secret", "webhook_secret"]
    assert body["display_label"] == "Pay online"
    # the secret never comes back over the API
    assert "shhh-secret" not in saved.text and "whsec" not in saved.text


def test_blank_secret_keeps_the_stored_value(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _save(client, ctx, "razorpay", credentials={"key_id": "rzp_test_a", "key_secret": "keep-me"})

    # the panel round-trips blank secrets; they must not wipe the stored one
    again = _save(client, ctx, "razorpay", credentials={"key_id": "rzp_test_b", "key_secret": ""})
    assert again.status_code == 200, again.text
    assert again.json()["credential_keys"] == ["key_id", "key_secret"]
    assert again.json()["configured"] is True


def test_unknown_credential_key_is_rejected(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    resp = _save(client, ctx, "razorpay", credentials={"nonsense": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_CREDENTIAL"


def test_planned_provider_can_be_configured_but_not_enabled(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    stored = _save(
        client, ctx, "stripe", credentials={"secret_key": "sk_test_1", "publishable_key": "pk_test_1"}
    )
    assert stored.status_code == 200, stored.text
    assert stored.json()["configured"] is True and stored.json()["is_enabled"] is False

    refused = _save(client, ctx, "stripe", is_enabled=True)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "GATEWAY_NOT_AVAILABLE"


def test_enabled_gateway_drives_storefront_methods_in_display_order(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    # Nothing configured: the sandbox keeps a fresh shop checkout usable.
    codes = [method["code"] for method in _methods(client, ctx)]
    assert codes == ["card", "upi", "razorpay", "cod"]

    _save(
        client,
        ctx,
        "razorpay",
        is_enabled=True,
        label="Pay online",
        priority=20,
        credentials={"key_id": "rzp_test_1", "key_secret": "s3cret"},
        settings={"methods": ["upi", "card"], "instructions": "Cards and UPI via Razorpay"},
    )
    _save(client, ctx, "cod", is_enabled=True, priority=10, label="Pay at the door")
    _save(client, ctx, "stripe", is_enabled=True)  # refused: not enabled

    methods = _methods(client, ctx)
    # admin order first (cod 10 before razorpay 20), sandbox gone, planned absent
    assert [method["code"] for method in methods] == ["cod", "razorpay"]
    online = methods[1]
    assert online["label"] == "Pay online" and online["kind"] == "hosted_modal"
    assert online["methods"] == ["upi", "card"]
    assert online["instructions"] == "Cards and UPI via Razorpay"
    assert methods[0]["label"] == "Pay at the door"

    # an instrument the admin switched off is no longer accepted at checkout
    refused = _place(client, ctx, "card")
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "PAYMENT_METHOD_UNAVAILABLE"
    assert _place(client, ctx, "razorpay").status_code == 200


def test_gateway_settings_reject_instruments_the_provider_lacks(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    resp = _save(
        client,
        ctx,
        "razorpay",
        credentials={"key_id": "rzp_test_1", "key_secret": "s"},
        settings={"methods": ["upi", "paypal_button"]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BAD_GATEWAY_SETTINGS"


def test_arbitrary_settings_are_stored_and_returned(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    saved = _save(
        client,
        ctx,
        "cod",
        is_enabled=True,
        settings={"max_order": "5000", "pincode_only": "560001,560002", "delivery_partner": "BlueDart"},
    )
    assert saved.status_code == 200, saved.text
    settings = saved.json()["settings"]
    assert settings["max_order"] == "5000.00"  # money fields are normalised
    assert settings["pincode_only"] == "560001,560002"
    assert settings["delivery_partner"] == "BlueDart"  # custom key kept as sent


def test_disabling_and_deleting_a_gateway(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _save(
        client,
        ctx,
        "razorpay",
        is_enabled=True,
        credentials={"key_id": "rzp_test_1", "key_secret": "s3cret"},
    )
    assert [method["code"] for method in _methods(client, ctx)] == ["razorpay", "cod"]

    off = _save(client, ctx, "razorpay", is_enabled=False)
    assert off.status_code == 200 and off.json()["is_enabled"] is False
    assert [method["code"] for method in _methods(client, ctx)] == ["card", "upi", "razorpay", "cod"]

    removed = client.delete(f"{GATEWAYS}/razorpay", headers=ctx["store"])
    assert removed.status_code == 200 and removed.json() == {"deleted": "razorpay"}
    assert _one(client, ctx, "razorpay")["source"] == "unset"
    assert client.delete(f"{GATEWAYS}/razorpay", headers=ctx["store"]).status_code == 404


def test_cod_still_follows_the_delivery_zone(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _save(client, ctx, "cod", is_enabled=True)
    methods = {method["code"]: method for method in _methods(client, ctx)}
    assert methods["cod"]["kind"] == "offline"


def test_company_credentials_scope_the_razorpay_client():
    """Stored keys take over from the env: real keys are never treated as demo."""
    from app.modules.payments import razorpay

    assert razorpay.is_configured() is False  # tests run with no env keys
    with razorpay.use_credentials({"key_id": "rzp_live_x", "key_secret": "s3cret"}):
        assert razorpay.is_configured() is True
        assert razorpay.is_demo() is False
        assert razorpay.key_id() == "rzp_live_x"
    assert razorpay.is_configured() is False and razorpay.is_demo() is False


def test_gateway_config_is_company_scoped(client, admin_headers):
    first = _setup_store(client, admin_headers)
    second = _setup_store(client, admin_headers)
    _save(
        client,
        first,
        "razorpay",
        is_enabled=True,
        credentials={"key_id": "rzp_first", "key_secret": "s1"},
    )
    assert _one(client, first, "razorpay")["is_enabled"] is True
    assert _one(client, second, "razorpay")["is_enabled"] is False
    assert [method["code"] for method in _methods(client, second)] == ["card", "upi", "razorpay", "cod"]
