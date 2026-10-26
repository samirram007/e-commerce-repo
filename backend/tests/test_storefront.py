"""Guest storefront tests: public catalog, trending detail counts, favorites/
watchlist, pincode zones, and the anonymous token cart."""
HEADERS = {"X-Company-Id": ""}
ANON = {"X-Company-Id": "", "X-Anon-Id": "anon-test-001"}


_COMPANY_SEQ = [0]


def _company_tgt(client, admin_headers):
    # unique name: the session-scoped test DB rejects duplicate company names
    _COMPANY_SEQ[0] += 1
    cid = client.post(
        "/api/v1/companies",
        headers=admin_headers,
        json={"name": f"Storefront Co {_COMPANY_SEQ[0]}", "base_currency": "USD"},
    ).json()["id"]
    return cid


def _store_headers(client, admin_headers, cid):
    """Product/zone creation headers scoped to the storefront company."""
    return {"Authorization": admin_headers["Authorization"], "X-Company-Id": cid}


def _product(client, auth_headers, *, name, price, category=None):
    resp = client.post(
        "/api/v1/catalog/products",
        headers=auth_headers,
        json={
            "sku": name.replace(" ", ""),
            "name": name,
            "base_price": str(price),
            "base_cost": "1",
            "stock_type": "stock",
            "category_id": category,
            "is_sellable": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_guest_catalog_browse_and_filters(client, admin_headers, auth_headers):
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    anon = {"X-Company-Id": cid, "X-Anon-Id": "anon-1"}
    cat = client.post(
        "/api/v1/catalog/categories",
        headers=store,
        json={"name": "Gadgets", "parent_id": None},
    ).json()
    p1 = _product(client, store, name="Guest Widget", price="10.50", category=cat["id"])
    _product(client, store, name="Enterprise Only", price="500")

    # list without auth (guest) — only sellable+active items, paginated contract
    resp = client.get(f"/api/v1/storefront/shop/products?limit=10", headers=anon)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 2
    assert {"Guest Widget", "Enterprise Only"} <= {i["name"] for i in body["items"]}

    # price filter + sort
    resp = client.get(
        f"/api/v1/storefront/shop/products?max_price=100&sort=price_asc", headers=anon
    ).json()
    assert all(float(i["price"]) <= 100 for i in resp["items"])
    prices = [float(i["price"]) for i in resp["items"]]
    assert prices == sorted(prices)

    # category filter (descendant-safe)
    resp = client.get(f"/api/v1/storefront/shop/products?category={cat['id']}", headers=anon).json()
    assert [i["name"] for i in resp["items"]] == ["Guest Widget"]

    # category cards count what opening them shows (uncategorised never leaks in)
    cats = client.get("/api/v1/storefront/shop/categories", headers=anon).json()
    gadgets = next(c for c in cats if c["name"] == "Gadgets")
    assert gadgets["product_count"] == 1

    # trending requires views; initially empty
    assert client.get(f"/api/v1/storefront/shop/trending", headers=anon).json() == []


def test_guest_product_detail_view_counts_and_related(client, admin_headers, auth_headers):
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    anon = {"X-Company-Id": cid, "X-Anon-Id": "anon-2"}
    a = _product(client, store, name="Viewed Product", price="5")
    b = _product(client, store, name="Related Product", price="6")

    detail = client.get(f"/api/v1/storefront/shop/products/{a['id']}?count_view=true", headers=anon).json()
    assert detail["name"] == "Viewed Product"
    assert detail["view_count"] == 1
    again = client.get(f"/api/v1/storefront/shop/products/{a['id']}?count_view=true", headers=anon).json()
    assert again["view_count"] == 2

    trending = client.get("/api/v1/storefront/shop/trending", headers=anon).json()
    assert [t["id"] for t in trending] == [a["id"]]


def test_guest_favorites_and_watchlist_toggle(client, admin_headers, auth_headers):
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    anon = {"X-Company-Id": cid, "X-Anon-Id": "anon-3"}
    p = _product(client, store, name="Fav Product", price="7")

    def toggle(kind):
        return client.post(
            "/api/v1/storefront/shop/interests/toggle",
            headers=anon,
            json={"kind": kind, "product_id": p["id"]},
        ).json()

    fav_on = toggle("favorite")
    assert fav_on == {"kind": "favorite", "product_id": p["id"], "active": True}
    toggle("watchlist")
    on = toggle("watchlist")
    assert on["active"] is False

    interests = client.get("/api/v1/storefront/shop/interests", headers=anon).json()
    assert [f["id"] for f in interests["favorite"]] == [p["id"]]
    assert interests["watchlist"] == []


def test_pincode_check_and_zone_config(client, admin_headers):
    cid = _company_tgt(client, admin_headers)
    anon = {"X-Company-Id": cid}

    # valid Indian PIN, but no zone configured for this company yet
    unconfigured = client.get("/api/v1/storefront/shop/pincode/591999", headers=anon).json()
    assert unconfigured["configured"] is False and unconfigured["deliverable"] is False
    assert unconfigured["valid"] is True and unconfigured["state"] == "Karnataka"

    from app.modules.storefront import service as sf

    from app.db.session import get_session_factory
    Session = get_session_factory()
    with Session() as s:
        zone = sf.set_delivery_zone(s, cid, pincode="110 001", deliverable=True, eta_days=2, cod_allowed=True)
        s.commit()  # direct session bypasses the request-scoped unit of work
    assert zone.id and zone.pincode == "110001"

    delivery = client.get("/api/v1/storefront/shop/pincode/110001", headers=anon).json()
    assert delivery == {
        "pincode": "110001",
        "valid": True,
        "state": "Delhi",
        "city": "New Delhi",
        "deliverable": True,
        "eta_days": 2,
        "cod_allowed": True,
        "configured": True,
    }

    # India-specific validation: six digits, first digit non-zero
    for bad in ["012345", "11001", "1100012", "ABCDEF"]:
        resp = client.get(f"/api/v1/storefront/shop/pincode/{bad}", headers=anon)
        assert resp.status_code == 400, bad
        assert resp.json()["error"]["code"] == "BAD_PINCODE", bad


def test_delivery_zone_prefixes_cover_a_whole_state(client, admin_headers):
    """One 2-digit prefix row must serve every PIN in that postal circle, and
    an exact PIN rule must still win over it."""
    cid = _company_tgt(client, admin_headers)
    anon = {"X-Company-Id": cid}

    from app.db.session import get_session_factory
    from app.modules.storefront import service as sf

    with get_session_factory()() as s:
        sf.set_delivery_zone(s, cid, pincode="40", deliverable=True, eta_days=3, cod_allowed=True)
        # Pune: explicitly not served, despite the Maharashtra prefix
        sf.set_delivery_zone(s, cid, pincode="411004", deliverable=False, eta_days=5, cod_allowed=False)
        s.commit()

    mumbai = client.get("/api/v1/storefront/shop/pincode/400001", headers=anon).json()
    assert mumbai["deliverable"] is True and mumbai["configured"] is True
    assert mumbai["eta_days"] == 3 and mumbai["state"] == "Maharashtra"

    pune = client.get("/api/v1/storefront/shop/pincode/411004", headers=anon).json()
    assert pune["deliverable"] is False and pune["configured"] is True

    elsewhere = client.get("/api/v1/storefront/shop/pincode/560001", headers=anon).json()
    assert elsewhere["configured"] is False and elsewhere["deliverable"] is False

    import pytest

    from app.core.exceptions import BusinessRuleError

    for bad in ["0", "1", "abc", "1234567"]:
        with pytest.raises(BusinessRuleError):
            sf.normalize_zone_code(bad)


def test_guest_checkout_validates_indian_pin(client, admin_headers, auth_headers):
    """Guest checkout must reject malformed and undeliverable Indian PIN codes."""
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    tok = {"X-Company-Id": cid, "X-Cart-Token": "guest-checkout-token-01"}
    p = _product(client, store, name="Checkout Product", price="25")
    client.post(
        "/api/v1/storefront/shop/cart/items", headers=tok, json={"product_id": p["id"], "qty": 1}
    )

    def payload(pincode: str) -> dict:
        return {
            "name": "Guest Shopper",
            "email": "guest@example.com",
            "address": {"line1": "1 Test Road", "pincode": pincode, "country": "IN"},
            "payment_method": "card",
        }

    from app.db.session import get_session_factory
    from app.modules.companies.models import Company
    from app.modules.storefront import service as sf

    with get_session_factory()() as s:
        # storefront checkout is opt-in per company (the seeded demo turns it on)
        company = s.get(Company, cid)
        company.allow_guest_checkout = True
        sf.set_delivery_zone(s, cid, pincode="560001", deliverable=True, eta_days=2, cod_allowed=True)
        s.commit()

    bad = client.post(
        "/api/v1/storefront/shop/checkout",
        headers={**tok, "Idempotency-Key": "k-bad-pin"},
        json=payload("012345"),
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "BAD_PINCODE"

    missing = client.post(
        "/api/v1/storefront/shop/checkout",
        headers={**tok, "Idempotency-Key": "k-no-pin"},
        json={**payload(""), "address": {"line1": "1 Test Road", "country": "IN"}},
    )
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "PINCODE_REQUIRED"

    elsewhere = client.post(
        "/api/v1/storefront/shop/checkout",
        headers={**tok, "Idempotency-Key": "k-other-pin"},
        json=payload("110001"),
    )
    assert elsewhere.status_code == 400 and elsewhere.json()["error"]["code"] == "NOT_DELIVERABLE"


def test_guest_token_cart_lifecycle(client, admin_headers, auth_headers):
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    tok = {"X-Company-Id": cid, "X-Cart-Token": "guestcart-token-0001"}
    p = _product(client, store, name="Cart Product", price="12.00")

    cart = client.post(
        "/api/v1/storefront/shop/cart/items", headers=tok, json={"product_id": p["id"], "qty": 2}
    ).json()
    assert len(cart["items"]) == 1
    assert float(cart["items"][0]["qty"]) == 2.0
    item = cart["items"][0]
    item_id = item["id"]
    # the cart row is priced server-side (unit price, tax and line total)
    assert item["image_url"] == f"/api/v1/storefront/shop/products/{p['id']}/image"
    assert item["unit_price"] == item["price"]
    assert float(item["line_total"]) >= float(item["unit_price"]) * 2
    assert float(cart["quote"]["total"]) >= float(item["line_total"])

    cart = client.patch(
        f"/api/v1/storefront/shop/cart/items/{item_id}", headers=tok, json={"qty": 5}
    ).json()
    assert float(cart["items"][0]["qty"]) == 5.0

    # setting qty to 0 removes the row
    cart = client.patch(
        f"/api/v1/storefront/shop/cart/items/{item_id}", headers=tok, json={"qty": 0}
    ).json()
    assert cart["items"] == []
    assert float(cart["quote"]["total"]) == 0.0

    # token stability: re-add after clear, then clear whole cart
    client.post("/api/v1/storefront/shop/cart/items", headers=tok, json={"product_id": p["id"], "qty": 1})
    cart = client.delete("/api/v1/storefront/shop/cart", headers=tok).json()
    assert cart["items"] == []


def test_storefront_requires_company_header(client, admin_headers, auth_headers):
    resp = client.get("/api/v1/storefront/shop/products")
    assert resp.status_code == 401  # AuthError envelope: company context required


def test_product_image_is_public_svg(client, admin_headers, auth_headers):
    """`image_url` points here and an <img> cannot send auth/company headers,
    so the route must resolve the product by id alone."""
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    cat = client.post(
        "/api/v1/catalog/categories", headers=store, json={"name": "Phones", "parent_id": None}
    ).json()
    p = _product(client, store, name="Image Product", price="9", category=cat["id"])

    listed = client.get("/api/v1/storefront/shop/products", headers={"X-Company-Id": cid}).json()
    url = next(i["image_url"] for i in listed["items"] if i["id"] == p["id"])

    resp = client.get(url)  # no headers at all, like a browser image request
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.content.startswith(b"<svg") and b"Image Product" in resp.content

    assert client.get("/api/v1/storefront/shop/products/does-not-exist/image").status_code == 404


def test_interest_requires_owner_on_legacy_paths(client, admin_headers, auth_headers):
    # anonymous toggle without X-Anon-Id must fail cleanly
    cid = _company_tgt(client, admin_headers)
    store = _store_headers(client, admin_headers, cid)
    p = _product(client, store, name="NoOwner Product", price="2")
    resp = client.post(
        "/api/v1/storefront/shop/interests/toggle",
        headers={"X-Company-Id": cid},
        json={"kind": "favorite", "product_id": p["id"]},
    )
    assert resp.status_code == 400  # BusinessRuleError: identity required


def test_payment_methods_flag_razorpay_when_unconfigured(client, admin_headers):
    """Checkout must be able to explain why the Razorpay window never opens."""
    cid = _company_tgt(client, admin_headers)
    anon = {"X-Company-Id": cid, "X-Anon-Id": "anon-payment-methods"}
    methods = client.get("/api/v1/storefront/shop/payment-methods", headers=anon).json()
    by_code = {m["code"]: m for m in methods}
    assert {"card", "upi", "cod", "razorpay"} <= set(by_code)
    # without keys the sandbox methods are offered and Razorpay is explicitly off
    assert by_code["razorpay"]["available"] is False
    assert by_code["razorpay"]["reason"] == "not_configured"
