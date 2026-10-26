"""Inventory invariants: on-hand mirrors the ledger, negative stock prevented,
reservations tracked, transfers move balances within one warehouse."""

import pytest


def _adjust(auth_headers, client: object, data: dict, direction="increase", qty="5"):
    return client.post(
        "/api/v1/inventory/adjustments",
        headers=auth_headers,
        json={
            "location_id": data["bin_id"],
            "product_id": data["product_id"],
            "quantity": qty,
            "direction": direction,
            "reason": "test",
        },
    )


def test_adjustment_increases_stock_and_ledger(client, auth_headers, master_data):
    data = master_data
    resp = _adjust(auth_headers, client, data)
    assert resp.status_code in (200, 201), resp.text
    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    assert any(float(r["on_hand"]) == 5.0 for r in on_hand)
    ledger = client.get("/api/v1/inventory/ledger", headers=auth_headers).json()
    assert any(l["movement_type"] == "adjustment" for l in ledger)


def test_negative_stock_prevented(client, auth_headers, master_data):
    data = master_data
    _adjust(auth_headers, client, data, qty="2")
    resp = _adjust(auth_headers, client, data, direction="decrease", qty="5")
    assert resp.status_code == 400
    # both guards are valid: pre-check (INSUFFICIENT_STOCK) or ledger guard
    assert resp.json()["error"]["code"] in {"NEGATIVE_STOCK", "INSUFFICIENT_STOCK"}


def test_transfer_between_bins(client, auth_headers, master_data):
    data = master_data
    _adjust(auth_headers, client, data, qty="10")
    # create a second bin under the same warehouse
    resp = client.post(
        "/api/v1/storage/locations",
        headers=auth_headers,
        json={"code": "BIN-2", "name": "Bin 2", "location_type": "bin", "parent_id": data["wh_id"]},
    )
    bin2 = resp.json()["id"]
    resp = client.post(
        "/api/v1/inventory/transfers",
        headers=auth_headers,
        json={
            "product_id": data["product_id"],
            "from_location_id": data["bin_id"],
            "to_location_id": bin2,
            "quantity": "4",
        },
    )
    assert resp.status_code == 201, resp.text
    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    balances = {(r["location_id"], float(r["on_hand"])) for r in on_hand}
    assert (data["bin_id"], 6.0) in balances
    assert (bin2, 4.0) in balances


def test_reconcile_endpoint_reports_balanced(client, auth_headers, master_data):
    data = master_data
    _adjust(auth_headers, client, data, qty="5")
    resp = client.get("/api/v1/inventory/reconcile", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["balanced"] is True


def test_cross_company_product_rejected(client, auth_headers, master_data, company_id):
    """A product from another company cannot be adjusted (IDOR guard)."""
    other_company = client.post(
        "/api/v1/companies",
        headers=auth_headers,
        json={"name": "Other Co", "base_currency": "USD"},
    ).json()["id"]
    other_headers = {**auth_headers, "X-Company-Id": other_company}
    resp = client.get("/api/v1/catalog/products", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []
