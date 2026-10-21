"""Batch-tracked products through the full fulfilment path.

The shipment issue follows the rows the reservation was consumed from
(location + batch_ref). An untargeted issue (batch_ref=None) misses the
batch-keyed on-hand row, driving it negative and failing the `packed`
transition with NEGATIVE_STOCK.
"""
import pytest


def _ensure_fiscal_year(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code in (200, 201), resp.text


def _gl_balanced(client, auth_headers) -> bool:
    tb = client.get("/api/v1/accounting/reports/trial-balance", headers=auth_headers).json()
    debit = sum(float(r["debit"]) for r in tb)
    credit = sum(float(r["credit"]) for r in tb)
    return abs(debit - credit) < 0.001


@pytest.fixture()
def batch_product_id(client, auth_headers, master_data):
    """Batch-tracked product with 20 units received under batch ESP-2026-01."""
    _ensure_fiscal_year(client, auth_headers)

    resp = client.post(
        "/api/v1/catalog/products",
        headers=auth_headers,
        json={
            "sku": "BATCH-FUL-1",
            "name": "Batch Espresso Beans 1kg",
            "base_price": "18.99",
            "base_cost": "9.50",
            "stock_type": "stock",
            "track_batches": True,
        },
    )
    assert resp.status_code == 201, resp.text
    product_id = resp.json()["id"]

    # only the purchasing receive flow carries batch_ref
    po = client.post(
        "/api/v1/purchasing/orders",
        headers=auth_headers,
        json={
            "vendor_id": master_data["vendor_id"],
            "order_date": "2026-03-01",
            "currency": "USD",
            "lines": [{"product_id": product_id, "ordered_qty": "20", "unit_cost": "9.50"}],
        },
    ).json()
    client.post(f"/api/v1/purchasing/orders/{po['id']}/submit", headers=auth_headers)
    client.post(f"/api/v1/purchasing/orders/{po['id']}/approve", headers=auth_headers)
    lines = client.get(
        f"/api/v1/purchasing/orders/{po['id']}/lines", headers=auth_headers
    ).json()
    resp = client.post(
        f"/api/v1/purchasing/orders/{po['id']}/receive",
        headers=auth_headers,
        json={
            "lines": [
                {
                    "order_line_id": lines[0]["id"],
                    "qty_received": "20",
                    "location_id": master_data["bin_id"],
                    "batch_ref": "ESP-2026-01",
                    "expiry_date": "2027-06-30",
                }
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    return product_id


def _on_hand_rows(client, auth_headers, product_id) -> dict:
    rows = client.get(
        "/api/v1/inventory/on-hand",
        headers=auth_headers,
        params={"product_id": product_id},
    ).json()
    return {r.get("batch_ref"): r for r in rows}


def test_batch_stock_lands_in_batch_row(client, auth_headers, master_data, batch_product_id):
    rows = _on_hand_rows(client, auth_headers, batch_product_id)
    assert "ESP-2026-01" in rows
    assert float(rows["ESP-2026-01"]["on_hand"]) == 20.0
    # batch-tracked receipts never fall back to the batch_ref=None row
    assert rows.get(None) is None


def test_batch_product_fulfills_through_packed(
    client, auth_headers, master_data, batch_product_id
):
    product_id = batch_product_id
    data = master_data

    resp = client.post(
        "/api/v1/storefront/cart/items",
        headers=auth_headers,
        json={"product_id": product_id, "qty": "3"},
    )
    assert resp.status_code == 200, resp.text
    order = client.post(
        "/api/v1/storefront/checkout",
        headers={**auth_headers, "Idempotency-Key": "batch-ship-1"},
        json={
            "customer_id": data["customer_id"],
            "shipping_address": "123 Demo St",
            "shipping_total": "5.00",
        },
    ).json()

    # reservation sits on the batch row
    rows = _on_hand_rows(client, auth_headers, product_id)
    assert float(rows["ESP-2026-01"]["reserved"]) == 3.0

    resp = client.post(
        f"/api/v1/storefront/orders/{order['order_id']}/pay",
        headers={**auth_headers, "Idempotency-Key": "batch-pay-1"},
        json={"method": "mock_gateway", "provider": "mock"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/v1/shipments", headers=auth_headers, params={"order_id": order["order_id"]}
    )
    assert resp.status_code == 201, resp.text
    shipment_id = resp.json()["id"]

    for to_status in ("picked", "packed"):
        resp = client.post(
            f"/api/v1/shipments/{shipment_id}/transition",
            headers=auth_headers,
            params={"to_status": to_status},
        )
        assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "packed"

    # the issue decremented the batch row (not an unrelated None row)
    rows = _on_hand_rows(client, auth_headers, product_id)
    assert float(rows["ESP-2026-01"]["on_hand"]) == 17.0
    assert float(rows["ESP-2026-01"]["reserved"]) == 0.0
    assert rows.get(None) is None

    # COGS + invoice postings kept the GL balanced
    assert _gl_balanced(client, auth_headers)

    ledger = client.get(
        "/api/v1/inventory/ledger",
        headers=auth_headers,
        params={"product_id": product_id},
    ).json()
    issues = [
        l for l in ledger
        if l["movement_type"] == "issue" and l.get("batch_ref") == "ESP-2026-01"
    ]
    assert issues and float(issues[0]["qty_delta"]) == -3.0
