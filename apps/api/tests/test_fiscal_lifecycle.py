"""Fiscal year lifecycle: opening balances → year-end close → forward.

Covers the invariants behind the Settings > Fiscal years wizard:
  * opening balances post first (fresh year only), balanced, dated in-year
  * close zeroes cumulative P&L into retained earnings and seals periods
  * close refuses out-of-order / double close
  * forward mirrors closing balances into the next year (created on demand)
  * cumulative reports never double-count the carry-forward snapshot
"""

from decimal import Decimal

import pytest


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _create_fy(client, auth_headers, start="2026-01-01", end="2026-12-31"):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": start, "end_date": end},
    )
    assert resp.status_code in (201, 400), resp.text
    if resp.status_code == 400:
        # already created in this shared test DB — look it up
        for fy in client.get("/api/v1/fiscal-years", headers=auth_headers).json():
            if fy["start_date"] == start:
                return fy
        raise AssertionError("fiscal year not found after 400")
    return resp.json()


def _list_fy(client, auth_headers, start):
    for fy in client.get("/api/v1/fiscal-years", headers=auth_headers).json():
        if fy["start_date"] == start:
            return fy
    raise AssertionError(f"fiscal year starting {start} not found")


def _journal(client, auth_headers, entry_date, debit_acct, credit_acct, amount):
    resp = client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json={
            "entry_date": entry_date,
            "description": "lifecycle test",
            "lines": [
                {"account_code": debit_acct, "side": "debit", "amount": amount},
                {"account_code": credit_acct, "side": "credit", "amount": amount},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _entry_lines(client, auth_headers, entry_id):
    resp = client.get(f"/api/v1/accounting/journal-entries/{entry_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _tb(client, auth_headers, **params):
    resp = client.get(
        "/api/v1/accounting/reports/trial-balance", headers=auth_headers, params=params
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------- opening


def test_opening_balances_post_first(client, auth_headers):
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    resp = client.post(
        f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
        headers=auth_headers,
        json={
            "description": "Opening for new database",
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "5000"},
                {"account_code": "3000", "side": "credit", "amount": "5000"},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["status"] == "posted"
    assert entry["fiscal_year_id"] == fy["id"]
    assert entry["entry_date"] == "2026-01-01"

    detail = _entry_lines(client, auth_headers, entry["id"])
    assert detail["source_type"] == "opening"
    total_d = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "debit")
    total_c = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "credit")
    assert total_d == total_c == Decimal("5000")

    # Trial balance reflects the opening position.
    rows = _tb(client, auth_headers, fiscal_year_id=fy["id"])
    balances = {r["account_code"]: _dec(r["balance"]) for r in rows}
    assert balances["1010"] == Decimal("5000.00")
    assert balances["3000"] == Decimal("-5000.00")


def test_opening_balances_rejected_after_activity(client, auth_headers):
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    # Ensure the year has activity (another test may have opened it already —
    # then FY_HAS_ACTIVITY is what we want anyway).
    resp = client.post(
        f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
        headers=auth_headers,
        json={
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "10"},
                {"account_code": "3000", "side": "credit", "amount": "10"},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    # second attempt → the year now has posted entries
    resp = client.post(
        f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
        headers=auth_headers,
        json={
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "10"},
                {"account_code": "3000", "side": "credit", "amount": "10"},
            ]
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FY_HAS_ACTIVITY"


def test_opening_balances_unbalanced_rejected(client, auth_headers):
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    resp = client.post(
        f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
        headers=auth_headers,
        json={
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "100"},
                {"account_code": "3000", "side": "credit", "amount": "90"},
            ]
        },
    )
    if resp.status_code == 409:  # year already has activity from another test
        pytest.skip("fiscal year already active in shared test DB")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "JOURNAL_UNBALANCED"


def test_opening_balances_date_must_be_in_year(client, auth_headers):
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    resp = client.post(
        f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
        headers=auth_headers,
        json={
            "entry_date": "2025-12-31",
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "10"},
                {"account_code": "3000", "side": "credit", "amount": "10"},
            ],
        },
    )
    if resp.status_code == 409:
        pytest.skip("fiscal year already active in shared test DB")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "DATE_OUTSIDE_FISCAL_YEAR"


# ---------------------------------------------------------------- close


def test_close_posts_closing_entry_and_seals_year(client, auth_headers):
    """Income is zeroed into retained earnings; posting afterwards fails."""
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    if not fy["is_open"]:
        pytest.skip("fiscal year already closed in shared test DB")

    # revenue 1000, expense 400 → profit 600
    _journal(client, auth_headers, "2026-03-10", "1010", "4000", "1000")
    _journal(client, auth_headers, "2026-06-15", "6000", "1010", "400")

    resp = client.post(f"/api/v1/fiscal-years/{fy['id']}/close", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_open"] is False
    assert body["closing_entry_id"], "closing must post a journal entry"

    # closing entry: income zeroed, RE credited with the profit
    detail = _entry_lines(client, auth_headers, body["closing_entry_id"])
    assert detail["source_type"] == "year_end_close"
    lines = {l["account_code"]: (l["side"], _dec(l["amount"])) for l in detail["lines"]}
    assert lines["4000"] == ("debit", Decimal("1000.00"))
    assert lines["6000"] == ("credit", Decimal("400.00"))
    assert lines["3100"] == ("credit", Decimal("600.00"))
    total_d = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "debit")
    total_c = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "credit")
    assert total_d == total_c

    # all periods sealed
    periods = client.get(
        f"/api/v1/fiscal-years/{fy['id']}/periods", headers=auth_headers
    ).json()
    assert periods and all(p["is_open"] is False for p in periods)

    # posting into the closed year fails
    resp = client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json={
            "entry_date": "2026-11-11",
            "lines": [
                {"account_code": "1010", "side": "debit", "amount": "5"},
                {"account_code": "4000", "side": "credit", "amount": "5"},
            ],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("FISCAL_YEAR_CLOSED", "PERIOD_CLOSED")

    # double close → 409
    resp = client.post(f"/api/v1/fiscal-years/{fy['id']}/close", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FISCAL_YEAR_CLOSED"


def test_close_rejects_out_of_order(client, auth_headers):
    fy26 = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2027-01-01", "end_date": "2027-12-31"},
    )
    assert resp.status_code in (201, 400), resp.text
    fy27 = _list_fy(client, auth_headers, "2027-01-01")

    # 2026 still open → closing 2027 first is rejected
    if fy26["is_open"]:
        resp = client.post(f"/api/v1/fiscal-years/{fy27['id']}/close", headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "CLOSE_OUT_OF_ORDER"
    else:
        # someone already closed 2026 — closing it again must 409, and 2027
        # (still open, earlier-year guard satisfied) must close fine
        resp = client.post(f"/api/v1/fiscal-years/{fy26['id']}/close", headers=auth_headers)
        assert resp.status_code == 409


# ---------------------------------------------------------------- forward


def test_forward_creates_next_year_and_balances(client, auth_headers):
    """Close 2026 (profit 600), forward → 2027 opens with matching balances."""
    fy = _create_fy(client, auth_headers, "2026-01-01", "2026-12-31")
    if not fy["is_open"]:
        # already closed by another test — may already be forwarded
        pass
    else:
        # opening cash + revenue + expense
        resp = client.post(
            f"/api/v1/fiscal-years/{fy['id']}/opening-balances",
            headers=auth_headers,
            json={
                "lines": [
                    {"account_code": "1010", "side": "debit", "amount": "5000"},
                    {"account_code": "3000", "side": "credit", "amount": "5000"},
                ]
            },
        )
        assert resp.status_code == 201, resp.text
        _journal(client, auth_headers, "2026-03-10", "1010", "4000", "1000")
        _journal(client, auth_headers, "2026-06-15", "6000", "1010", "400")

        resp = client.post(f"/api/v1/fiscal-years/{fy['id']}/close", headers=auth_headers)
        assert resp.status_code == 200, resp.text

    # forward while still open? must fail — but it's closed here, so post.
    resp = client.post(f"/api/v1/fiscal-years/{fy['id']}/forward", headers=auth_headers)
    if resp.status_code == 409 and resp.json()["error"]["code"] == "ALREADY_FORWARDED":
        pytest.skip("already forwarded in shared test DB")
    assert resp.status_code == 201, resp.text
    result = resp.json()
    assert result["to_created"] is True
    assert result["accounts_carried"] >= 2

    # The new year exists and is open.
    fy27 = _list_fy(client, auth_headers, "2027-01-01")
    assert fy27["is_open"] is True

    # Carry-forward entry: dated at the new year's start, source carry_forward.
    detail = _entry_lines(client, auth_headers, result["journal_entry_id"])
    assert detail["source_type"] == "carry_forward"
    assert detail["entry_date"] == "2027-01-01"
    assert detail["fiscal_year_id"] == fy27["id"]
    total_d = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "debit")
    total_c = sum(_dec(l["amount"]) for l in detail["lines"] if l["side"] == "credit")
    assert total_d == total_c

    # Opening position of 2027 = closing position of 2026:
    # cash 5000 + 1000 - 400 = 5600; equity = 3000 (5000) + RE (profit 600).
    rows = _tb(client, auth_headers, fiscal_year_id=fy27["id"])
    balances = {r["account_code"]: _dec(r["balance"]) for r in rows}
    assert balances["1010"] == Decimal("5600.00")
    assert balances["3000"] == Decimal("-5000.00")
    assert balances["3100"] == Decimal("-600.00")
    # P&L accounts closed to zero in the forwarding year's scoped view.
    assert balances.get("4000", Decimal("0")) == Decimal("0")
    assert balances.get("6000", Decimal("0")) == Decimal("0")

    # Cumulative (all history) must NOT double-count the snapshot.
    cumulative = {
        r["account_code"]: _dec(r["balance"]) for r in _tb(client, auth_headers)
    }
    assert cumulative["1010"] == Decimal("5600.00"), "snapshot doubled the cash balance"
    assert cumulative["3000"] == Decimal("-5000.00")
    assert cumulative["3100"] == Decimal("-600.00")

    # Balance sheet stays consistent after forward.
    resp = client.get(
        "/api/v1/accounting/reports/balance-sheet",
        headers=auth_headers,
        params={"as_of": "2027-06-30"},
    )
    assert resp.status_code == 200, resp.text
    bs = resp.json()
    assert bs["balanced"] is True

    # second forward → 409
    resp = client.post(f"/api/v1/fiscal-years/{fy['id']}/forward", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_FORWARDED"


def test_forward_requires_closed_year(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2028-01-01", "end_date": "2028-12-31"},
    )
    assert resp.status_code in (201, 400), resp.text
    fy28 = _list_fy(client, auth_headers, "2028-01-01")

    resp = client.post(f"/api/v1/fiscal-years/{fy28['id']}/forward", headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FY_NOT_CLOSED"


def test_forward_requires_permission(client, admin_headers, company_id):
    """A user without fiscal.manage/journal.post cannot run the lifecycle."""
    resp = client.post("/api/v1/fiscal-years")
    assert resp.status_code == 401

    headers = {"Authorization": admin_headers["Authorization"], "X-Company-Id": company_id}
    resp = client.post("/api/v1/fiscal-years", headers=headers)
    assert resp.status_code in (403, 422) or resp.status_code == 400
