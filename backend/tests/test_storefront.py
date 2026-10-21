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

    unconfigured = client.get("/api/v1/storefront/shop/pincode/999999", headers=anon).json()
    assert unconfigured["configured"] is False and unconfigured["deliverable"] is False

    from app.modules.storefront import service as sf

    from app.db.session import get_session_factory
    Session = get_session_factory()
    with Session() as s:
        zone = sf.set_delivery_zone(s, cid, pincode="110001", deliverable=True, eta_days=2, cod_allowed=True)
        s.commit()  # direct session bypasses the request-scoped unit of work
    assert zone.id

    delivery = client.get("/api/v1/storefront/shop/pincode/110001", headers=anon).json()
    assert delivery == {"pincode": "110001", "deliverable": True, "eta_days": 2, "cod_allowed": True, "configured": True}


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
    item_id = cart["items"][0]["id"]

    cart = client.patch(
        f"/api/v1/storefront/shop/cart/items/{item_id}", headers=tok, json={"qty": 5}
    ).json()
    assert float(cart["items"][0]["qty"]) == 5.0

    cart = client.delete(f"/api/v1/storefront/shop/cart/items/{item_id}", headers=tok).json()
    assert cart["items"] == []

    # token stability: re-add after clear, then clear whole cart
    client.post("/api/v1/storefront/shop/cart/items", headers=tok, json={"product_id": p["id"], "qty": 1})
    cart = client.delete("/api/v1/storefront/shop/cart", headers=tok).json()
    assert cart["items"] == []


def test_storefront_requires_company_header(client, admin_headers, auth_headers):
    resp = client.get("/api/v1/storefront/shop/products")
    assert resp.status_code == 401  # AuthError envelope: company context required


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
