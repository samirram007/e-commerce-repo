"""One-off E2E smoke: full fiscal lifecycle over real HTTP (run against the
disposable smoke server, then delete this file)."""

import sys

import httpx

BASE = "http://127.0.0.1:8124/api/v1"
c = httpx.Client(base_url=BASE, timeout=20.0)


def check(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {label} {detail}")
    if not cond:
        sys.exit(1)


# 1. bootstrap admin + company
r = c.post("/auth/bootstrap", json={"email": "smoke@e2e.io", "password": "SmokePass!123", "full_name": "Smoke"})
check("bootstrap admin", r.status_code in (200, 201), r.text[:120])
tok = r.json().get("access_token") or c.post("/auth/login", json={"email": "smoke@e2e.io", "password": "SmokePass!123"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

r = c.post("/companies", headers=h, json={"name": "E2E Co", "base_currency": "USD"})
check("create company", r.status_code == 201, r.text[:120])
cid = r.json()["id"]
h["X-Company-Id"] = cid

# 2. seed default chart (new endpoint)
r = c.post("/accounting/accounts/seed-defaults", headers=h)
check("seed default chart", r.status_code == 201 and len(r.json()) >= 30, f"{len(r.json()) if r.status_code==201 else r.text[:120]} accounts")
r2 = c.post("/accounting/accounts/seed-defaults", headers=h)
check("seed is idempotent", r2.status_code == 201 and len(r2.json()) == len(r.json()))

# 3. fiscal year 2026
r = c.post("/fiscal-years", headers=h, json={"start_date": "2026-01-01", "end_date": "2026-12-31"})
check("create FY2026", r.status_code == 201, r.text[:120])
fy = r.json()

# 4. opening balances (fresh year)
r = c.post(f"/fiscal-years/{fy['id']}/opening-balances", headers=h, json={
    "description": "Opening for new database",
    "lines": [
        {"account_code": "1010", "side": "debit", "amount": "10000"},
        {"account_code": "3000", "side": "credit", "amount": "10000"},
    ],
})
check("post opening balances", r.status_code == 201, r.text[:150])
opening_id = r.json()["id"]

# opening must be first: a second attempt now fails
r = c.post(f"/fiscal-years/{fy['id']}/opening-balances", headers=h, json={
    "lines": [
        {"account_code": "1010", "side": "debit", "amount": "5"},
        {"account_code": "3000", "side": "credit", "amount": "5"},
    ],
})
check("opening blocked after activity", r.status_code == 409 and r.json()["error"]["code"] == "FY_HAS_ACTIVITY", r.text[:100])

# 5. some 2026 activity: revenue 2000, expense 800
for d, dr, cr, amt in (("2026-03-15", "1010", "4000", "2000"), ("2026-07-01", "6000", "1010", "800")):
    r = c.post("/accounting/journal-entries", headers=h, json={
        "entry_date": d,
        "lines": [
            {"account_code": dr, "side": "debit", "amount": amt},
            {"account_code": cr, "side": "credit", "amount": amt},
        ],
    })
    check(f"journal {amt} on {d}", r.status_code == 201, r.text[:120])

# 6. P&L before close shows the real result
r = c.get("/accounting/reports/profit-and-loss", headers=h, params={"from_date": "2026-01-01", "to_date": "2026-12-31"})
check("P&L before close", r.status_code == 200 and float(r.json()["profit"]) == 1200.0, r.text[:150])

# 7. close FY2026
r = c.post(f"/fiscal-years/{fy['id']}/close", headers=h)
check("close FY2026", r.status_code == 200, r.text[:200])
body = r.json()
check("close posted closing entry", bool(body.get("closing_entry_id")))

# periods sealed
r = c.get(f"/fiscal-years/{fy['id']}/periods", headers=h)
check("all periods sealed", all(not p["is_open"] for p in r.json()))

# posting into closed year fails
r = c.post("/accounting/journal-entries", headers=h, json={
    "entry_date": "2026-11-11",
    "lines": [
        {"account_code": "1010", "side": "debit", "amount": "5"},
        {"account_code": "4000", "side": "credit", "amount": "5"},
    ],
})
check("posting into closed year rejected", r.status_code == 400, r.text[:120])

# double close → 409
r = c.post(f"/fiscal-years/{fy['id']}/close", headers=h)
check("double close rejected", r.status_code == 409 and r.json()["error"]["code"] == "FISCAL_YEAR_CLOSED")

# P&L for the closed year still reports the real result (closing excluded)
r = c.get("/accounting/reports/profit-and-loss", headers=h, params={"from_date": "2026-01-01", "to_date": "2026-12-31"})
check("P&L after close unchanged", r.status_code == 200 and float(r.json()["profit"]) == 1200.0, r.text[:150])

# 8. forward to next year
r = c.post(f"/fiscal-years/{fy['id']}/forward", headers=h)
check("forward FY2026", r.status_code == 201, r.text[:200])
fwd = r.json()
check("next year created", fwd["to_created"] is True)

# second forward → 409
r = c.post(f"/fiscal-years/{fy['id']}/forward", headers=h)
check("double forward rejected", r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_FORWARDED")

# 9. FY2027-scoped TB = opening position (cash 10000+2000-800=11200, equity 10000 + RE 1200)
r = c.get("/accounting/reports/trial-balance", headers=h, params={"fiscal_year_id": fwd["to_fiscal_year_id"]})
check("TB for FY2027 scoped", r.status_code == 200)
bal = {row["account_code"]: float(row["balance"]) for row in r.json()}
check("FY2027 opening cash", abs(bal.get("1010", 0) - 11200.0) < 0.01, str(bal.get("1010")))
check("FY2027 opening RE", abs(bal.get("3100", 0) - (-1200.0)) < 0.01, str(bal.get("3100")))

# 10. cumulative TB must NOT double-count the snapshot
r = c.get("/accounting/reports/trial-balance", headers=h)
cum = {row["account_code"]: float(row["balance"]) for row in r.json()}
check("cumulative cash not doubled", abs(cum.get("1010", 0) - 11200.0) < 0.01, str(cum.get("1010")))
check("cumulative P&L zero after close", abs(cum.get("4000", 0)) < 0.01 and abs(cum.get("6000", 0)) < 0.01)

# 11. balance sheet balanced after forward
r = c.get("/accounting/reports/balance-sheet", headers=h, params={"as_of": "2027-06-30"})
check("balance sheet balanced after forward", r.status_code == 200 and r.json()["balanced"] is True, r.text[:150])

# 12. out-of-order guard: create FY2025 (earlier, open) while 2026 closed → closing 2025 later is fine,
# but closing 2027 while 2025 open must fail. Create 2025 then try closing 2027.
r = c.post("/fiscal-years", headers=h, json={"start_date": "2025-01-01", "end_date": "2025-12-31"})
check("create FY2025", r.status_code == 201, r.text[:120])
fy25 = r.json()
r = c.get("/fiscal-years", headers=h)
fy27 = next(f for f in r.json() if f["start_date"] == "2027-01-01")
r = c.post(f"/fiscal-years/{fy27['id']}/close", headers=h)
check("out-of-order close rejected", r.status_code == 400 and r.json()["error"]["code"] == "CLOSE_OUT_OF_ORDER", r.text[:150])

# 13. forward requires a closed year
r = c.post(f"/fiscal-years/{fy25['id']}/forward", headers=h)
check("forward open year rejected", r.status_code == 400 and r.json()["error"]["code"] == "FY_NOT_CLOSED")

# 14. payroll runs still work alongside (create employee + draft run)
r = c.post("/payroll/employees", headers=h, json={
    "employee_code": "E-901", "first_name": "Eve", "last_name": "E2E",
    "base_salary": "3000", "allowances": "0", "deduction_rate": "10",
})
check("create employee", r.status_code == 201, r.text[:120])
r = c.post("/payroll/runs", headers=h, json={"period_year": 2026, "period_month": 2})
check("create payroll run", r.status_code == 201, r.text[:150])
run = r.json()
check("run payslip math", abs(float(run["total_net"]) - 2700.0) < 0.01, str(run["total_net"]))
# posting the run must fail: Feb 2026 period is inside the closed FY2026
r = c.post(f"/payroll/runs/{run['id']}/post", headers=h)
check("run post into closed year rejected", r.status_code == 400, r.text[:150])
# cancel the draft instead
r = c.post(f"/payroll/runs/{run['id']}/cancel", headers=h)
check("cancel draft run", r.status_code == 200, r.text[:120])

# 15. unauthenticated access to new endpoints
noauth = httpx.Client(base_url=BASE, timeout=10.0)
r = noauth.post(f"/fiscal-years/{fy['id']}/forward")
check("forward requires auth", r.status_code == 401)

print("\nALL E2E CHECKS PASSED")
