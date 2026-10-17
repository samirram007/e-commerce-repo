"""Accounting invariants: balanced postings only, reopen-period validation,
reversals keep the ledger balanced, trial balance sums to zero."""

import pytest


@pytest.fixture(autouse=True)
def fiscal_ok(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code in (201, 400), resp.text  # 400 = already created


def _journal_payload(entry_date="2026-01-15", debit="100", credit="100"):
    return {
        "entry_date": entry_date,
        "description": "test entry",
        "lines": [
            {"account_code": "1010", "side": "debit", "amount": debit, "description": "bank"},
            {"account_code": "4000", "side": "credit", "amount": credit, "description": "revenue"},
        ],
    }


def test_manual_journal_posts_and_balances(client, auth_headers):
    resp = client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=_journal_payload())
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["status"] == "posted"
    total_debit = sum(float(l["amount"]) for l in entry["lines"] if l["side"] == "debit")
    total_credit = sum(float(l["amount"]) for l in entry["lines"] if l["side"] == "credit")
    assert total_debit == total_credit


def test_unbalanced_journal_rejected(client, auth_headers):
    resp = client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=_journal_payload(debit="123.45", credit="100"))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "JOURNAL_UNBALANCED"


def test_posting_into_empty_fiscal_year_requires_setup(client, auth_headers):
    resp = client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json=_journal_payload(entry_date="2010-01-01"),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NO_FISCAL_YEAR"


def test_reversal_and_trial_balance_zero(client, auth_headers, company_id):
    # fiscal year covering 2026 was already created by the autouse fixture
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code in (201, 400)
    resp = client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=_journal_payload())
    entry = resp.json()
    resp = client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/reverse", headers=auth_headers)
    assert resp.status_code == 201, resp.text

    tb = client.get("/api/v1/accounting/reports/trial-balance", headers=auth_headers)
    assert tb.status_code == 200
    rows = tb.json()
    debit = sum(float(r["debit"]) for r in rows)
    credit = sum(float(r["credit"]) for r in rows)
    assert abs(debit - credit) < 0.001, rows


def test_closed_period_rejects_posting(client, auth_headers, company_id):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2027-01-01", "end_date": "2027-12-31"},
    )
    fy = resp.json()
    periods = client.get(f"/api/v1/fiscal-years/{fy['id']}/periods", headers=auth_headers).json()
    jan = periods[0]
    client.post(f"/api/v1/fiscal-years/{fy['id']}/periods/{jan['id']}/close", headers=auth_headers)
    resp = client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json=_journal_payload(entry_date="2027-02-15", debit="50", credit="50"),
    )
    assert resp.status_code == 201  # February still open
    resp = client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json=_journal_payload(entry_date="2027-01-05", debit="50", credit="50"),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PERIOD_CLOSED"


def test_journal_entry_snapshots_fiscal_year_and_filters(client, auth_headers):
    resp = client.post("/api/v1/accounting/journal-entries", headers=auth_headers, json=_journal_payload())
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["fiscal_year_id"], "posting must snapshot the resolved fiscal year"

    fy_id = entry["fiscal_year_id"]

    # Journal list filters on the stored snapshot.
    listed = client.get(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        params={"fiscal_year_id": fy_id},
    )
    assert listed.status_code == 200
    assert any(e["id"] == entry["id"] for e in listed.json())

    other = client.get(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        params={"fiscal_year_id": "does-not-exist"},
    )
    assert other.status_code == 200
    assert all(e["id"] != entry["id"] for e in other.json())

    # Trial balance/ledger accept the same filter.
    tb = client.get(
        "/api/v1/accounting/reports/trial-balance",
        headers=auth_headers,
        params={"fiscal_year_id": fy_id},
    )
    assert tb.status_code == 200
    assert len(tb.json()) > 0

    tb_empty = client.get(
        "/api/v1/accounting/reports/trial-balance",
        headers=auth_headers,
        params={"fiscal_year_id": "does-not-exist"},
    )
    assert tb_empty.status_code == 200
    assert tb_empty.json() == []
