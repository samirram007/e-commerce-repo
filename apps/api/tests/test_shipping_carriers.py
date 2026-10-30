"""Third-party shipping: the carrier control plane and how checkout prices it.

Covers the credential rules (write-only, required before enabling, planned
carriers refused), the storefront's delivery options with the shop's rule
fallback, and that the charge is recomputed server-side.
"""
import uuid
from decimal import Decimal

from tests.test_storefront_payments import _setup_store

API = "/api/v1"
SHOP = f"{API}/storefront/shop"
CARRIERS = f"{API}/delivery/carriers"


def _cat(client, ctx):
    resp = client.get(CARRIERS, headers=ctx["store"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _one(client, ctx, carrier):
    return next(row for row in _cat(client, ctx)["profiles"] if row["carrier"] == carrier)


def _save(client, ctx, carrier, **payload):
    return client.put(f"{CARRIERS}/{carrier}", headers=ctx["store"], json=payload)


def _options(client, ctx, pincode=None):
    resp = client.get(
        f"{SHOP}/shipping-options",
        headers=ctx["headers"],
        params={"pincode": pincode} if pincode else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _place(client, ctx, *, carrier=None):
    body = {
        "name": "Shipping Shopper",
        "email": f"ship-{uuid.uuid4().hex[:8]}@example.com",
        "address": {"line1": "1 Test Road", "pincode": "560001", "country": "IN"},
        "payment_method": "cod",
    }
    if carrier is not None:
        body["shipping_carrier"] = carrier
    return client.post(
        f"{SHOP}/checkout",
        headers={**ctx["headers"], "Idempotency-Key": f"ship-{uuid.uuid4()}"},
        json=body,
    )


def test_catalog_lists_third_party_carriers(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    data = _cat(client, ctx)
    codes = [carrier["code"] for carrier in data["carriers"]]
    for expected in ("manual", "shiprocket", "delhivery", "bluedart", "dtdc", "fedex", "dhl", "custom"):
        assert expected in codes
    shiprocket = next(carrier for carrier in data["carriers"] if carrier["code"] == "shiprocket")
    assert shiprocket["kind"] == "api" and shiprocket["status"] == "planned"
    assert [field["key"] for field in shiprocket["credential_fields"]] == ["email", "password"]

    manual = _one(client, ctx, "manual")
    # own delivery needs no credentials, so it is "configured" but switched off
    assert manual["is_enabled"] is False and manual["configured"] is True


def test_enabling_a_carrier_requires_credentials(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    refused = _save(client, ctx, "shiprocket", is_enabled=True)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "CARRIER_NOT_AVAILABLE"  # adapter has not shipped

    # credentials can still be stored for the day the adapter lands
    stored = _save(client, ctx, "shiprocket", credentials={"email": "ops@shop.io", "password": "pw"})
    assert stored.status_code == 200, stored.text
    assert stored.json()["credential_keys"] == ["email", "password"]
    assert stored.json()["configured"] is True and stored.json()["is_enabled"] is False
    assert "pw" not in stored.text  # secrets are write-only

    unknown = _save(client, ctx, "shiprocket", credentials={"token": "x"})
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "UNKNOWN_CREDENTIAL"


def test_own_delivery_can_be_enabled_without_credentials(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    saved = _save(client, ctx, "manual", is_enabled=True, priority=5, label="Same-day rider")
    assert saved.status_code == 200, saved.text
    assert saved.json()["is_enabled"] is True and saved.json()["display_label"] == "Same-day rider"


def test_delivery_options_fall_back_to_the_shop_rules(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    # nothing configured: the shop's own standard option keeps checkout usable
    assert [option["code"] for option in _options(client, ctx)] == ["standard"]
    assert _options(client, ctx)[0]["rate_source"] == "rules"

    _save(client, ctx, "manual", is_enabled=True, priority=10, label="Shop rider")
    options = _options(client, ctx)
    assert [option["code"] for option in options] == ["manual"]
    assert options[0]["label"] == "Shop rider"
    assert options[0]["carrier"] == "manual"
    assert options[0]["rate_source"] == "rules"  # priced by the delivery-zone rules


def test_checkout_uses_the_chosen_carrier_and_rejects_unknown_ones(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _save(client, ctx, "manual", is_enabled=True, label="Shop rider")

    option = _options(client, ctx)[0]
    # a carrier the shop does not offer is refused before the order is placed
    refused = _place(client, ctx, carrier="shiprocket")
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "SHIPPING_OPTION_UNAVAILABLE"

    order = _place(client, ctx, carrier="manual")
    assert order.status_code == 200, order.text
    # the carrier's price (here the rule fallback) is what the order is charged
    assert Decimal(order.json()["shipping_total"]) == Decimal(option["price"])


def test_disabling_and_deleting_a_carrier(client, admin_headers):
    ctx = _setup_store(client, admin_headers)
    _save(client, ctx, "manual", is_enabled=True, priority=1)
    assert [option["code"] for option in _options(client, ctx)] == ["manual"]

    off = _save(client, ctx, "manual", is_enabled=False)
    assert off.status_code == 200 and off.json()["is_enabled"] is False
    assert [option["code"] for option in _options(client, ctx)] == ["standard"]

    assert client.delete(f"{CARRIERS}/manual", headers=ctx["store"]).json() == {"deleted": "manual"}
    assert client.delete(f"{CARRIERS}/manual", headers=ctx["store"]).status_code == 404


def test_product_weight_and_size_feed_shipping(client, admin_headers):
    ctx = _setup_store(client, admin_headers, price="1000")
    product_id = ctx["product"]["id"]

    updated = client.patch(
        f"{API}/catalog/products/{product_id}",
        headers=ctx["store"],
        json={"weight_kg": "1.25", "length_cm": "30", "width_cm": "20", "height_cm": "10"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert Decimal(body["weight_kg"]) == Decimal("1.250")
    assert Decimal(body["length_cm"]) == Decimal("30")

    negative = client.patch(
        f"{API}/catalog/products/{product_id}", headers=ctx["store"], json={"weight_kg": "-1"}
    )
    assert negative.status_code == 422  # validation rejects a negative weight

    # the cart weighs its lines, so carriers can rate the parcel
    _save(client, ctx, "manual", is_enabled=True, label="Shop rider")
    options = _options(client, ctx)
    assert [option["code"] for option in options] == ["manual"]
    assert _place(client, ctx, carrier="manual").status_code == 200


def test_carrier_config_is_company_scoped(client, admin_headers):
    first = _setup_store(client, admin_headers)
    second = _setup_store(client, admin_headers)
    _save(client, first, "manual", is_enabled=True)
    assert _one(client, first, "manual")["is_enabled"] is True
    assert _one(client, second, "manual")["is_enabled"] is False
