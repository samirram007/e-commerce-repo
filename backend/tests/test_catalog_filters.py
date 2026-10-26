"""Catalog product list filters: search (name/SKU/barcode), stock_type,
is_active and category_id — all server-side query params."""
import uuid


def _create_product(client, headers, **fields):
    sku = fields.pop("sku", f"FLTR-{uuid.uuid4().hex[:6].upper()}")
    resp = client.post(
        "/api/v1/catalog/products",
        headers=headers,
        json={"sku": sku, "name": "Item", "base_price": "10", **fields},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _list(client, headers, **params):
    resp = client.get("/api/v1/catalog/products", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def test_products_stock_type_filter(client, auth_headers):
    service = _create_product(
        client, auth_headers, name="Support Plan", stock_type="service"
    )
    _create_product(client, auth_headers, name="Another Physical", stock_type="stock")

    items = _list(client, auth_headers, stock_type="service")
    assert [p["id"] for p in items] == [service["id"]]
    assert all(p["stock_type"] == "service" for p in items)


def test_products_is_active_filter(client, auth_headers):
    retired = _create_product(
        client, auth_headers, name="Retired Widget", stock_type="stock", is_active=False
    )

    inactive = _list(client, auth_headers, is_active="false")
    assert [p["id"] for p in inactive] == [retired["id"]]

    active = _list(client, auth_headers, is_active="true")
    assert all(p["is_active"] is True for p in active)
    assert not any(p["id"] == retired["id"] for p in active)


def test_products_category_filter(client, auth_headers):
    category = client.post(
        "/api/v1/catalog/categories",
        headers=auth_headers,
        json={"name": f"Cat {uuid.uuid4().hex[:6]}"},
    )
    assert category.status_code == 201, category.text
    categorized = _create_product(
        client, auth_headers, name="Categorized", category_id=category.json()["id"]
    )

    items = _list(client, auth_headers, category_id=category.json()["id"])
    assert [p["id"] for p in items] == [categorized["id"]]


def test_products_search_matches_name_sku_and_barcode(client, auth_headers):
    _create_product(client, auth_headers, name="Gizmo Pro Drill", sku="DRILL-PRO-9")
    barcoded = _create_product(
        client, auth_headers, name="Plain Box", barcode="9990001112223"
    )

    assert [p["id"] for p in _list(client, auth_headers, search="gizmo")] != []
    assert [p["sku"] for p in _list(client, auth_headers, search="drill-pro")] == ["DRILL-PRO-9"]
    assert [p["id"] for p in _list(client, auth_headers, search="9990001112223")] == [
        barcoded["id"]
    ]


def test_product_hsn_sac_code_is_validated_and_returned(client, auth_headers):
    product = _create_product(client, auth_headers, name="Cable", hsn_sac="85444299")
    assert product["hsn_sac"] == "85444299"

    patched = client.patch(
        f"/api/v1/catalog/products/{product['id']}",
        headers=auth_headers,
        json={"hsn_sac": "8517"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["hsn_sac"] == "8517"

    # HSN is 4-8 digits and SAC is 6; anything else is rejected
    bad = client.post(
        "/api/v1/catalog/products",
        headers=auth_headers,
        json={"sku": "BAD-HSN-1", "name": "Bad", "hsn_sac": "85A1"},
    )
    assert bad.status_code == 400, bad.text
    assert bad.json()["error"]["code"] == "BAD_HSN_SAC"
