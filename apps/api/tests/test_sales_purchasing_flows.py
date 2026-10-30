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


def test_checkout_applies_company_default_tax(client, auth_headers, master_data):
    """Regression: quote_cart looked up the default rate via `taxes.TaxRate`,
    a function-local import, so checkout 500'd once a default sales tax existed."""
    data = master_data
    resp = client.post(
        "/api/v1/taxes",
        headers=auth_headers,
        json={
            "code": "VAT10",
            "name": "Sales VAT 10%",
            "percentage": "10",
            "is_default_sales": True,
            "is_default_purchase": True,
        },
    )
    assert resp.status_code == 201, resp.text

    _add_to_cart(client, auth_headers, data["product_id"], "3")
    # the quote labels the tax with its GST slab instead of a bare "Tax" line
    quote = client.get("/api/v1/storefront/cart", headers=auth_headers).json()["quote"]
    breakup = quote["tax_breakup"]
    assert len(breakup) == 1
    assert float(breakup[0]["rate"]) == pytest.approx(10.0)
    assert breakup[0]["amount"] == quote["tax_total"]

    resp = _checkout(client, auth_headers, data["customer_id"])
    assert resp.status_code == 200, resp.text
    order = resp.json()
    # 3 x 20 = 60 goods + 5 shipping; 10% VAT must be baked into the total
    assert float(order["total"]) > 65.0

    # the persisted order carries the tax breakdown
    detail = client.get(
        f"/api/v1/storefront/orders/{order['order_id']}", headers=auth_headers
    ).json()
    assert float(detail["tax_total"]) > 0

    resp = _pay(client, auth_headers, order["order_id"])
    assert resp.status_code == 200, resp.text
    assert _gl_balanced(client, auth_headers)

    # the posted invoice reports the same tax, split by GST rate
    detail = client.get(
        f"/api/v1/storefront/orders/{order['order_id']}", headers=auth_headers
    ).json()
    invoice = client.get(
        f"/api/v1/invoices/{detail['invoice_id']}", headers=auth_headers
    ).json()
    assert float(invoice["tax_breakup"][0]["rate"]) == pytest.approx(10.0)
    assert sum(float(row["amount"]) for row in invoice["tax_breakup"]) == pytest.approx(
        float(invoice["tax_total"])
    )
    # the printable invoice needs the taxable value, buyer GSTIN and address
    assert float(invoice["tax_breakup"][0]["taxable"]) == pytest.approx(
        float(invoice["subtotal"]) - float(invoice["discount_total"])
    )
    assert "customer_tax_identifier" in invoice
    assert invoice["customer_address"] == "123 Demo St"
    # the printable invoice carries the product's HSN/SAC code per line
    line_rows = client.get(
        f"/api/v1/invoices/{invoice['id']}/lines", headers=auth_headers
    ).json()
    assert line_rows[0]["hsn_sac"] == "8473"

    # tax posts as CGST (2110) + SGST (2120), not one lump tax account
    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.accounting.models import Account, JournalLine
    from app.modules.invoicing.models import CustomerInvoice

    with get_session_factory()() as session:
        row = session.get(CustomerInvoice, detail["invoice_id"])
        entry_lines = session.execute(
            select(Account.code, JournalLine.side, JournalLine.amount)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalLine.entry_id == row.journal_entry_id)
        ).all()
    by_code = {code: (side, amount) for code, side, amount in entry_lines}
    assert by_code["2110"][0] == "credit" and by_code["2120"][0] == "credit"
    assert float(by_code["2110"][1] + by_code["2120"][1]) == pytest.approx(
        float(invoice["tax_total"])
    )
    assert "2100" not in by_code
    listed = client.get("/api/v1/invoices", headers=auth_headers).json()
    assert next(i for i in listed if i["id"] == invoice["id"])["tax_breakup"]


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


def test_vendor_bill_splits_input_gst(client, auth_headers, master_data):
    """Vendor-bill tax is an input credit: it debits CGST (1160) + SGST (1170)
    instead of netting the lump-sum tax payable account."""
    data = master_data
    tax = client.post(
        "/api/v1/taxes",
        headers=auth_headers,
        json={
            "code": "GST18",
            "name": "GST 18%",
            "percentage": "18",
            "is_default_purchase": True,
        },
    )
    assert tax.status_code == 201, tax.text
    tax_rate_id = tax.json()["id"]

    po = client.post(
        "/api/v1/purchasing/orders",
        headers=auth_headers,
        json={
            "vendor_id": data["vendor_id"],
            "order_date": "2026-03-01",
            "currency": "USD",
            "lines": [
                {
                    "product_id": data["product_id"],
                    "ordered_qty": "10",
                    "unit_cost": "10.00",
                    "tax_rate_id": tax_rate_id,
                }
            ],
        },
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    client.post(f"/api/v1/purchasing/orders/{po_id}/submit", headers=auth_headers)
    client.post(f"/api/v1/purchasing/orders/{po_id}/approve", headers=auth_headers)
    lines = client.get(
        f"/api/v1/purchasing/orders/{po_id}/lines", headers=auth_headers
    ).json()
    receipt = client.post(
        f"/api/v1/purchasing/orders/{po_id}/receive",
        headers=auth_headers,
        json={
            "lines": [
                {
                    "order_line_id": lines[0]["id"],
                    "qty_received": "10",
                    "location_id": data["bin_id"],
                }
            ]
        },
    )
    assert receipt.status_code == 201, receipt.text
    bill = client.post(
        f"/api/v1/purchasing/bills/from-receipt/{receipt.json()['id']}?bill_date=2026-03-02",
        headers=auth_headers,
    )
    assert bill.status_code == 201, bill.text
    body = bill.json()
    assert float(body["total"]) == pytest.approx(118.0)

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.accounting.models import Account, JournalLine
    from app.modules.purchasing.models import VendorBill

    with get_session_factory()() as session:
        row = session.get(VendorBill, body["id"])
        rows = session.execute(
            select(Account.code, JournalLine.side, JournalLine.amount)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalLine.entry_id == row.journal_entry_id)
        ).all()
    debits = {code: amount for code, side, amount in rows if side == "debit"}
    assert debits["1160"] == pytest.approx(9.0)
    assert debits["1170"] == pytest.approx(9.0)
    assert "2100" not in debits
    assert debits["1200"] == pytest.approx(100.0)
    credits = {code: amount for code, side, amount in rows if side == "credit"}
    assert credits["2000"] == pytest.approx(118.0)

    # ad-hoc vendor bills split the same way
    adhoc = client.post(
        "/api/v1/purchasing/bills",
        headers=auth_headers,
        json={
            "vendor_id": data["vendor_id"],
            "bill_date": "2026-03-03",
            "currency": "USD",
            "lines": [
                {
                    "description": "Freight",
                    "qty": "1",
                    "unit_cost": "50.00",
                    "tax_percentage": "18",
                }
            ],
        },
    )
    assert adhoc.status_code == 201, adhoc.text
    with get_session_factory()() as session:
        row = session.get(VendorBill, adhoc.json()["id"])
        rows = session.execute(
            select(Account.code, JournalLine.side, JournalLine.amount)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalLine.entry_id == row.journal_entry_id)
        ).all()
    adhoc_debits = {code: amount for code, side, amount in rows if side == "debit"}
    assert adhoc_debits["1160"] == pytest.approx(4.5)
    assert adhoc_debits["1170"] == pytest.approx(4.5)
    assert "2100" not in adhoc_debits

    assert _gl_balanced(client, auth_headers)


def test_sales_return_refunds_and_posts_credit_note(client, auth_headers, master_data):
    """Return -> approve -> complete: exercises credit-note posting (invoicing)
    and provider refund (payments) end-to-end, keeping the GL balanced."""
    data = master_data
    resp = client.post(
        "/api/v1/taxes",
        headers=auth_headers,
        json={
            "code": "GST10",
            "name": "GST 10%",
            "percentage": "10",
            "is_default_sales": True,
            "is_default_purchase": True,
        },
    )
    assert resp.status_code == 201, resp.text
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

    # the credit note reverses the GST in the same two components
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.modules.accounting.models import Account, JournalLine
    from app.modules.invoicing.models import CreditNote, CreditNoteLine

    with get_session_factory()() as session:
        credit = session.get(CreditNote, body["credit_note_id"])
        rows = session.execute(
            select(Account.code, JournalLine.side, JournalLine.amount)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalLine.entry_id == credit.journal_entry_id)
        ).all()
        credit_lines = list(
            session.execute(
                select(CreditNoteLine).where(CreditNoteLine.credit_note_id == credit.id)
            ).scalars()
        )
    debits = {code: amount for code, side, amount in rows if side == "debit"}
    expected_tax = sum((Decimal(str(line.tax_amount)) for line in credit_lines), Decimal("0"))
    assert expected_tax > 0
    assert debits["2110"] + debits["2120"] == pytest.approx(float(expected_tax))
    assert "2100" not in debits

    assert _gl_balanced(client, auth_headers)


def test_cancel_releases_reservation(client, auth_headers, master_data):
    data = master_data
    _add_to_cart(client, auth_headers, data["product_id"], "2")
    order = _checkout(client, auth_headers, data["customer_id"], key="cancel-key").json()
    resp = client.post(f"/api/v1/storefront/orders/{order['order_id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    detail = client.get(
        f"/api/v1/storefront/orders/{order['order_id']}", headers=auth_headers
    ).json()
    assert detail["cancel_reason"] == "cancelled_by_staff"
    on_hand = client.get("/api/v1/inventory/on-hand", headers=auth_headers).json()
    stock = next(r for r in on_hand if r["product_id"] == data["product_id"])
    assert float(stock["reserved"]) == 0.0
