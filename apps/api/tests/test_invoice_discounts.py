"""Manual discounts on invoices: line-level and order-level.

An order-level discount is spread across the lines in proportion to their value,
so each line is taxed on its own discounted amount and the stored per-line
discounts add up to the invoice's discount total.
"""
from decimal import Decimal

import pytest

API = "/api/v1"


def _customer(client, auth_headers) -> str:
    resp = client.post(
        f"{API}/partners/customers", headers=auth_headers, json={"code": "DISC-1", "name": "Discount Co"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _tax(client, auth_headers, percentage="18") -> str:
    resp = client.post(
        f"{API}/taxes",
        headers=auth_headers,
        json={
            "code": f"DISCGST{percentage}",
            "name": f"GST {percentage}%",
            "percentage": percentage,
            "is_default_sales": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _products(client, auth_headers) -> tuple[str, str]:
    ids = []
    for index, price in enumerate(("1000", "400")):
        resp = client.post(
            f"{API}/catalog/products",
            headers=auth_headers,
            json={
                "sku": f"DISC-SKU-{index}",
                "name": f"Discounted item {index}",
                "hsn_sac": "8473",
                "base_price": price,
                "base_cost": "0",
                "stock_type": "service",
                "is_sellable": True,
            },
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids[0], ids[1]


def _invoice(client, auth_headers, *, customer_id, lines, discount="0"):
    return client.post(
        f"{API}/invoices",
        headers=auth_headers,
        json={
            "customer_id": customer_id,
            "invoice_date": "2026-04-01",
            "currency": "USD",
            "post": False,
            "discount": discount,
            "lines": lines,
        },
    )


def test_line_discount_is_taxed_on_the_discounted_value(client, auth_headers):
    customer_id = _customer(client, auth_headers)
    tax_rate_id = _tax(client, auth_headers)
    product_id, _ = _products(client, auth_headers)

    resp = _invoice(
        client,
        auth_headers,
        customer_id=customer_id,
        lines=[
            {
                "product_id": product_id,
                "qty": "2",
                "unit_price": "1000",
                "discount": "200",
                "tax_rate_id": tax_rate_id,
            }
        ],
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    assert Decimal(invoice["subtotal"]) == Decimal("2000")
    assert Decimal(invoice["discount_total"]) == Decimal("200")
    # 18% of the discounted 1800, not of 2000
    assert Decimal(invoice["tax_total"]) == pytest.approx(Decimal("324"))
    assert Decimal(invoice["total"]) == Decimal("2124")


def test_order_discount_is_spread_across_lines_by_value(client, auth_headers):
    customer_id = _customer(client, auth_headers)
    tax_rate_id = _tax(client, auth_headers)
    first, second = _products(client, auth_headers)

    resp = _invoice(
        client,
        auth_headers,
        customer_id=customer_id,
        discount="300",
        lines=[
            {"product_id": first, "qty": "1", "unit_price": "1000", "tax_rate_id": tax_rate_id},
            {"product_id": second, "qty": "1", "unit_price": "400", "tax_rate_id": tax_rate_id},
        ],
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    assert Decimal(invoice["subtotal"]) == Decimal("1400")
    assert Decimal(invoice["discount_total"]) == Decimal("300")
    # 18% of 1100 (after the discount), and the shares follow the line values
    assert Decimal(invoice["tax_total"]) == pytest.approx(Decimal("198"))
    assert Decimal(invoice["total"]) == Decimal("1298")

    lines = client.get(f"{API}/invoices/{invoice['id']}/lines", headers=auth_headers).json()
    shares = [Decimal(line["discount"]) for line in lines]
    assert sum(shares) == Decimal("300")
    assert shares[0] == Decimal("214.29") and shares[1] == Decimal("85.71")


def test_order_discount_combines_with_line_discounts(client, auth_headers):
    customer_id = _customer(client, auth_headers)
    tax_rate_id = _tax(client, auth_headers)
    first, second = _products(client, auth_headers)

    resp = _invoice(
        client,
        auth_headers,
        customer_id=customer_id,
        discount="100",
        lines=[
            {
                "product_id": first,
                "qty": "1",
                "unit_price": "1000",
                "discount": "50",
                "tax_rate_id": tax_rate_id,
            },
            {"product_id": second, "qty": "1", "unit_price": "400", "tax_rate_id": tax_rate_id},
        ],
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    # 50 on the first line + 100 spread over the two (71.43 / 28.57)
    assert Decimal(invoice["discount_total"]) == Decimal("150")
    lines = client.get(f"{API}/invoices/{invoice['id']}/lines", headers=auth_headers).json()
    assert [Decimal(line["discount"]) for line in lines] == [
        Decimal("121.43"),
        Decimal("28.57"),
    ]


def test_order_discount_cannot_exceed_the_invoice_value(client, auth_headers):
    customer_id = _customer(client, auth_headers)
    product_id, _ = _products(client, auth_headers)

    resp = _invoice(
        client,
        auth_headers,
        customer_id=customer_id,
        discount="5000",
        lines=[{"product_id": product_id, "qty": "1", "unit_price": "1000"}],
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "DISCOUNT_EXCEEDS"


def test_order_discount_needs_lines_with_a_value(client, auth_headers):
    customer_id = _customer(client, auth_headers)
    product_id, _ = _products(client, auth_headers)

    resp = _invoice(
        client,
        auth_headers,
        customer_id=customer_id,
        discount="10",
        lines=[{"product_id": product_id, "qty": "1", "unit_price": "0"}],
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "BAD_DISCOUNT"
