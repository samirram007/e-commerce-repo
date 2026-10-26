"""Payroll tests: employee CRUD, payslip math, run lifecycle, balanced GL post."""

import uuid
from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def fiscal_ok(client, auth_headers):
    resp = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert resp.status_code in (201, 400), resp.text  # 400 = already created


def _employee_payload(code="E-001", salary="4500.00", allowances="200.00", deduction_rate="10"):
    return {
        "employee_code": code,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "base_salary": salary,
        "allowances": allowances,
        "deduction_rate": deduction_rate,
    }


def _dec(value) -> Decimal:
    """Decimal comparison helper tolerant of str/float JSON encodings."""
    return Decimal(str(value))


def test_payroll_requires_auth(client):
    resp = client.get("/api/v1/payroll/employees")
    assert resp.status_code == 401


def test_employee_crud_and_duplicate_code(client, auth_headers):
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text
    emp = resp.json()
    assert emp["employee_code"] == "E-001"

    # duplicate employee code within the company → 409
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PAYROLL_DUPLICATE_CODE"

    # list contains the employee
    resp = client.get("/api/v1/payroll/employees", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1 and body["page"] == 1
    assert any(e["id"] == emp["id"] for e in body["items"])

    # patch salary + deactivate
    resp = client.patch(
        f"/api/v1/payroll/employees/{emp['id']}",
        headers=auth_headers,
        json={"base_salary": "5000", "employment_status": "inactive"},
    )
    assert resp.status_code == 200, resp.text
    assert _dec(resp.json()["base_salary"]) == Decimal("5000.00")
    assert resp.json()["employment_status"] == "inactive"

    # unknown id → 404
    resp = client.get("/api/v1/payroll/employees/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


def test_run_payroll_payslip_math(client, auth_headers):
    # gross = 4500 + 200 = 4700; deductions = 10% = 470; net = 4230
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text

    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 1},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "draft"
    assert run["employee_count"] == 1
    assert _dec(run["total_gross"]) == Decimal("4700.00")
    assert _dec(run["total_deductions"]) == Decimal("470.00")
    assert _dec(run["total_net"]) == Decimal("4230.00")
    assert len(run["payslips"]) == 1
    slip = run["payslips"][0]
    assert _dec(slip["gross"]) == Decimal("4700.00")
    assert _dec(slip["deductions"]) == Decimal("470.00")
    assert _dec(slip["net_pay"]) == Decimal("4230.00")

    # duplicate period for the same company → 409
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 1},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PAYROLL_RUN_EXISTS"


def test_run_without_employees_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 2},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PAYROLL_NO_EMPLOYEES"


def test_invalid_period_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 13},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inactive_employee_excluded_from_run(client, auth_headers):
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        json=_employee_payload(code="E-002", salary="1000", allowances="0", deduction_rate="0"),
    )
    assert resp.status_code == 201, resp.text
    inactive_id = resp.json()["id"]
    resp = client.patch(
        f"/api/v1/payroll/employees/{inactive_id}",
        headers=auth_headers,
        json={"employment_status": "inactive"},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 4},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["employee_count"] == 1
    assert run["payslips"][0]["employee_code"] == "E-001"


def test_post_run_creates_balanced_journal(client, auth_headers):
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 1},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()

    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/post", headers=auth_headers)
    assert resp.status_code == 201, resp.text
    posted = resp.json()
    assert posted["status"] == "posted"
    assert posted["journal_entry_id"]

    # the journal entry exists, balances, links back, and uses payroll accounts
    entry_resp = client.get(
        f"/api/v1/accounting/journal-entries/{posted['journal_entry_id']}",
        headers=auth_headers,
    )
    assert entry_resp.status_code == 200, entry_resp.text
    entry = entry_resp.json()
    assert entry["status"] == "posted"
    assert entry["source_type"] == "payroll_run"
    assert entry["source_id"] == run["id"]

    lines = entry["lines"]
    total_debit = sum(float(l["amount"]) for l in lines if l["side"] == "debit")
    total_credit = sum(float(l["amount"]) for l in lines if l["side"] == "credit")
    assert total_debit == total_credit == 4700.0, lines
    codes = {l["account_code"] for l in lines}
    assert "6100" in codes  # salaries & wages expense
    assert "2400" in codes  # payroll payable (net)
    assert "2410" in codes  # withholdings payable

    # payslips moved to posted
    detail = client.get(f"/api/v1/payroll/runs/{run['id']}", headers=auth_headers).json()
    assert detail["status"] == "posted"
    assert all(p["status"] == "posted" for p in detail["payslips"])

    # double-post → 409
    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/post", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PAYROLL_RUN_NOT_DRAFT"


def test_cancel_draft_run_frees_period(client, auth_headers):
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 3},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()

    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    # cancelled run frees the period for a new run
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 3},
    )
    assert resp.status_code == 201, resp.text

    # cancelling again → 409
    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PAYROLL_RUN_CANCELLED"


def test_posted_run_cannot_be_cancelled(client, auth_headers):
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text
    resp = client.post(
        "/api/v1/payroll/runs",
        headers=auth_headers,
        json={"period_year": 2026, "period_month": 5},
    )
    run = resp.json()
    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/post", headers=auth_headers)
    assert resp.status_code == 201, resp.text

    resp = client.post(f"/api/v1/payroll/runs/{run['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PAYROLL_RUN_POSTED"


def test_company_scoping_isolates_payroll(client, auth_headers, company_id):
    """Employees/runs of one company are invisible to another company context."""
    resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=_employee_payload())
    assert resp.status_code == 201, resp.text

    # second company for the same admin (unique name: shared session DB across tests)
    resp = client.post(
        "/api/v1/companies",
        headers={"Authorization": auth_headers["Authorization"]},
        json={"name": f"Other Co {uuid.uuid4().hex[:8]}", "base_currency": "USD"},
    )
    assert resp.status_code == 201, resp.text
    other_headers = {
        "Authorization": auth_headers["Authorization"],
        "X-Company-Id": resp.json()["id"],
    }

    resp = client.get("/api/v1/payroll/employees", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []

    # cross-company access to the employee id → 404
    emp_id = client.get("/api/v1/payroll/employees", headers=auth_headers).json()["items"][0]["id"]
    resp = client.get(f"/api/v1/payroll/employees/{emp_id}", headers=other_headers)
    assert resp.status_code == 404


def _seed_employees(client, auth_headers):
    payloads = [
        _employee_payload(code="E-100", salary="3000.00", allowances="0", deduction_rate="0"),
        _employee_payload(code="E-200", salary="1500.00", allowances="0", deduction_rate="0"),
        _employee_payload(code="E-300", salary="9000.00", allowances="0", deduction_rate="0"),
    ]
    # different surnames so surname search/sort are meaningful
    payloads[0]["last_name"] = "Alpha"
    payloads[1]["last_name"] = "Beta"
    payloads[2]["last_name"] = "Gamma"
    for payload in payloads:
        resp = client.post("/api/v1/payroll/employees", headers=auth_headers, json=payload)
        assert resp.status_code == 201, resp.text


def test_employees_server_side_search(client, auth_headers):
    _seed_employees(client, auth_headers)
    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"search": "Beta"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["last_name"] == "Beta"

    # search also matches employee code
    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"search": "E-300"},
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["employee_code"] == "E-300"


def test_employees_server_side_sort(client, auth_headers):
    _seed_employees(client, auth_headers)
    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"sort": "base_salary", "order": "desc"},
    )
    assert resp.status_code == 200
    salaries = [float(e["base_salary"]) for e in resp.json()["items"]]
    assert salaries == sorted(salaries, reverse=True)
    assert salaries[0] == 9000.0


def test_employees_sort_field_allowlist(client, auth_headers):
    """Sorting by a non-allowlisted column must be rejected (AGENT.md §8)."""
    _seed_employees(client, auth_headers)
    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"sort": "created_by"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SORT_FIELD"


def test_employees_pagination(client, auth_headers):
    _seed_employees(client, auth_headers)
    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"sort": "employee_code", "order": "asc", "page": 1, "page_size": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert [e["employee_code"] for e in body["items"]] == ["E-100", "E-200"]

    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"sort": "employee_code", "order": "asc", "page": 2, "page_size": 2},
    )
    body = resp.json()
    assert body["page"] == 2
    assert [e["employee_code"] for e in body["items"]] == ["E-300"]


def test_employees_status_filter(client, auth_headers):
    _seed_employees(client, auth_headers)
    inactive_id = client.get(
        "/api/v1/payroll/employees", headers=auth_headers, params={"search": "E-200"}
    ).json()["items"][0]["id"]
    resp = client.patch(
        f"/api/v1/payroll/employees/{inactive_id}",
        headers=auth_headers,
        json={"employment_status": "inactive"},
    )
    assert resp.status_code == 200

    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"employment_status": "active"},
    )
    body = resp.json()
    assert body["total"] == 2
    assert all(e["employment_status"] == "active" for e in body["items"])

    resp = client.get(
        "/api/v1/payroll/employees",
        headers=auth_headers,
        params={"employment_status": "inactive"},
    )
    assert resp.json()["total"] == 1
