"""End-to-end flows:
cart -> idempotent checkout -> payment -> invoice + journals
PO -> goods receipt -> vendor bill + journals
Both keep the GL balanced and stock consistent.
"""

import pytest


def _ensure_fiscal_year(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code == 201, resp.text


def _add_to_cart(client, auth_headers, product_id: str, qty="2"):
    resp = client.post(
        "/api/v1/storefront/cart/items",
        headers=auth_headers,
        json={"product_id": product_id, "qty": qty},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _checkout(client, auth_headers, customer_id, key="test-key-1"):
    return client.post(
        "/api/v1/storefront/checkout",
        headers={**auth_headers, "Idempotency-Key": key},
        json={
            "customer_id": customer_id,
            "shipping_address": "123 Demo St",
            "shipping_total": "5.00",
        },
    )


def _pay(client, auth_headers, order_id, key="pay-key-1"):
    return client.post(
        f"/api/v1/storefront/orders/{order_id}/pay",
        headers={**auth_headers, "Idempotency-Key": key},
        json={"method": "mock_gateway", "provider": "mock"},
    )


def _gl_balanced(client, auth_headers) -> bool:
    tb = client.get("/api/v1/accounting/reports/trial-balance", headers=auth_headers).json()
    debit = sum(float(r["debit"]) for r in tb)
    credit = sum(float(r["credit"]) for r in tb)
    return abs(debit - credit) < 0.001


@pytest.fixture(autouse=True)
def fiscal_ok(client, auth_headers, master_data):
    _ensure_fiscal_year(client, auth_headers)
    # seed plenty of stock for checkout flows
    resp = client.post(
        "/api/v1/inventory/adjustments",
        headers=auth_headers,
        json={
            "location_id": master_data["bin_id"],
            "product_id": master_data["product_id"],
            "quantity": "1000",
            "direction": "increase",
            "reason": "opening stock",
        },
    )
    assert resp.status_code in (200, 201), resp.text


def test_checkout_reserves_and_pays_end_to_end(client, auth_headers, master_data):
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "3")

    resp = _checkout(client, auth_headers, data["customer_id"])
    assert resp.status_code == 200, resp.text
    order = resp.json()
    assert order["status"] == "pending_payment"
    # 3 units at 20 = 60; total includes tax and shipping and is server-computed
    assert float(order["total"]) > 0

    # stock reserved, not issued
    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    stock = next(r for r in on_hand if r["product_id"] == data["product_id"])
    assert float(stock["reserved"]) == 3.0
    assert float(stock["on_hand"]) == 1000.0
    assert float(stock["available"]) == 997.0

    resp = _pay(client, auth_headers, order["order_id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "paid"
    assert body["invoice_id"] is not None
    assert body["payment_ref"]

    invoice = client.get(f"/api/v1/invoices/{body['invoice_id']}", headers=auth_headers).json()
    assert invoice["status"] == "posted"
    assert abs(float(invoice["total"]) - float(order["total"])) < 0.011

    assert _gl_balanced(client, auth_headers)


def test_checkout_idempotent_replay(client, auth_headers, master_data):
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "1")
    first = _checkout(client, auth_headers, data["customer_id"], key="same-key")
    second = _checkout(client, auth_headers, data["customer_id"], key="same-key")
    assert first.json()["order_id"] == second.json()["order_id"]
    assert second.json()["replayed"] is True
    orders = client.get("/api/v1/storefront/orders", headers=auth_headers).json()
    assert len([o for o in orders]) == 1


def test_payment_idempotent_no_double_invoice(client, auth_headers, master_data):
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "1")
    order = _checkout(client, auth_headers, data["customer_id"], key="k-pay").json()
    first = _pay(client, auth_headers, order["order_id"], key="same-pay")
    second = _pay(client, auth_headers, order["order_id"], key="same-pay")
    assert first.json()["invoice_id"] == second.json()["invoice_id"]
    invoices = client.get("/api/v1/invoices", headers=auth_headers).json()
    assert len(invoices) == 1


def test_out_of_stock_checkout_rejected(client, auth_headers, master_data):
    data = master_data
    resp = client.post(
        "/api/v1/storefront/cart/items",
        headers=auth_headers,
        json={"product_id": data["product_id"], "qty": "2000"},
    )
    cart = resp.json()
    result = _checkout(client, auth_headers, data["customer_id"], key="oos-key")
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "OUT_OF_STOCK"


def test_purchasing_flow_receives_stock_and_posts_bill(client, auth_headers, master_data):
    data = master_data
    po = client.post(
        "/api/v1/purchasing/orders",
        headers=auth_headers,
        json={
            "vendor_id": data["vendor_id"],
            "order_date": "2026-03-01",
            "currency": "USD",
            "lines": [{"product_id": data["product_id"], "ordered_qty": "10", "unit_cost": "10.00"}],
        },
    ).json()
    client.post(f"/api/v1/purchasing/orders/{po['id']}/submit", headers=auth_headers)
    client.post(f"/api/v1/purchasing/orders/{po['id']}/approve", headers=auth_headers)

    # receipt needs a bin under the purchase flow (po lines have no location; use goods receipt endpoint)
    lines = client.get(f"/api/v1/purchasing/orders/{po['id']}/lines", headers=auth_headers).json()
    resp = client.post(
        f"/api/v1/purchasing/orders/{po['id']}/receive",
        headers=auth_headers,
        json={"lines": [{"order_line_id": lines[0]["id"], "qty_received": "10", "location_id": data["bin_id"]}]},
    )
    assert resp.status_code == 201, resp.text
    receipt = resp.json()

    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    assert any(float(r["on_hand"]) == 1010.0 for r in on_hand)  # 1000 seed + 10 received

    resp = client.post(
        f"/api/v1/purchasing/bills/from-receipt/{receipt['id']}?bill_date=2026-03-02",
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    bill = resp.json()
    assert abs(float(bill["total"]) - 100.0) < 0.011

    # ledger mirrors the receipt; GL balanced after bill posting
    ledger = client.get("/api/v1/inventory/ledger", headers=auth_headers).json()
    assert any(l["movement_type"] == "receipt" for l in ledger)
    assert _gl_balanced(client, auth_headers)


def test_sales_return_refunds_and_posts_credit_note(client, auth_headers, master_data):
    """Return -> approve -> complete: exercises credit-note posting (invoicing)
    and provider refund (payments) end-to-end, keeping the GL balanced."""
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "2")
    order = _checkout(client, auth_headers, data["customer_id"], key="ret-key").json()
    paid = _pay(client, auth_headers, order["order_id"], key="ret-pay").json()
    assert paid["status"] == "paid"
    assert paid["invoice_id"] is not None

    detail = client.get(
        f"/api/v1/storefront/orders/{order['order_id']}", headers=auth_headers
    ).json()
    order_line_id = detail["lines"][0]["id"]

    created = client.post(
        "/api/v1/returns",
        headers=auth_headers,
        json={
            "order_id": order["order_id"],
            "lines": [
                {
                    "order_line_id": order_line_id,
                    "qty": "1",
                    "disposition": "resalable",
                    "restock_location_id": data["bin_id"],
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    ret = created.json()

    approved = client.post(f"/api/v1/returns/{ret['id']}/approve", headers=auth_headers)
    assert approved.status_code == 200, approved.text

    completed = client.post(f"/api/v1/returns/{ret['id']}/complete", headers=auth_headers)
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["status"] == "completed"
    assert body["credit_note_id"] is not None
    assert body["refund_payment_id"] is not None

    assert _gl_balanced(client, auth_headers)


def test_cancel_releases_reservation(client, auth_headers, master_data):
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "2")
    order = _checkout(client, auth_headers, data["customer_id"], key="cancel-key").json()
    resp = client.post(f"/api/v1/storefront/orders/{order['order_id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    stock = next(r for r in on_hand if r["product_id"] == data["product_id"])
    assert float(stock["reserved"]) == 0.0
