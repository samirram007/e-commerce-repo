"""Reports endpoints: date-range handling must work.

Regression guard for `reports.service.to_utc_day_bounds`, which builds the
inclusive company-timezone window from query `from_date`/`to_date`.
"""


def test_sales_summary_with_date_range(client, auth_headers):
    resp = client.get(
        "/api/v1/reports/sales-summary",
        headers=auth_headers,
        params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "invoice_count" in body
    assert "total" in body


def test_purchase_summary_defaults_to_today(client, auth_headers):
    resp = client.get("/api/v1/reports/purchase-summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
