"""Test fixtures.

Uses a throwaway SQLite database per test session (financial invariants are
dialect-agnostic; Postgres-specific behavior is exercised via docker when
available). Provides an authenticated admin client + company context helper.
"""
import os
import tempfile

# Configure a fresh DB before app imports pick up settings
_TMPDIR = tempfile.mkdtemp(prefix="erp-test-")
os.environ["DATABASE_URL"] = f"sqlite:/// {_TMPDIR}/test.db".replace(" ", "")
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["MEDIA_DIR"] = _TMPDIR

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import base_all  # noqa: E402,F401  imports every module's models
from app.db.base import Base  # noqa: E402
from app.db.session import build_engine, get_session_factory  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    engine = build_engine()
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(engine):
    from app.main import app

    with TestClient(app) as tc:
        yield tc


@pytest.fixture()
def admin_token(client) -> str:
    creds = {"email": "admin@test.io", "password": "SuperSecret!123"}
    resp = client.post(
        "/api/v1/auth/bootstrap",
        json={**creds, "full_name": "Admin"},
    )
    if resp.status_code != 201:
        # already bootstrapped in this session DB — log in instead
        resp = client.post("/api/v1/auth/login", json=creds)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


def next_name(prefix: str, seed=[0]) -> str:
    seed[0] += 1
    return f"{prefix}-{seed[0]}"


@pytest.fixture()
def company_id(admin_headers, client) -> str:
    name = next_name("Company")
    resp = client.post(
        "/api/v1/companies",
        headers=admin_headers,
        json={"name": name, "base_currency": "USD"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture()
def auth_headers(admin_headers, company_id) -> dict:
    return {"Authorization": admin_headers["Authorization"], "X-Company-Id": company_id}


def create_company_counterparties(client, auth_headers) -> dict:
    """customer + vendor + product + warehouse + bin id set."""
    resp = client.post("/api/v1/partners/customers", headers=auth_headers, json={"code": "C-1", "name": "Cust"})
    customer_id = resp.json()["id"]
    resp = client.post("/api/v1/partners/vendors", headers=auth_headers, json={"code": "V-1", "name": "Vend"})
    vendor_id = resp.json()["id"]
    resp = client.post("/api/v1/catalog/products", headers=auth_headers, json={"sku": "SKU-1", "name": "Widget", "base_price": "20", "base_cost": "10", "stock_type": "stock"})
    product_id = resp.json()["id"]
    resp = client.post("/api/v1/storage/locations", headers=auth_headers, json={"code": "WH", "name": "Warehouse", "location_type": "warehouse"})
    wh_id = resp.json()["id"]
    resp = client.post("/api/v1/storage/locations", headers=auth_headers, json={"code": "BIN-1", "name": "Bin", "location_type": "bin", "parent_id": wh_id})
    bin_id = resp.json()["id"]
    return {"customer_id": customer_id, "vendor_id": vendor_id, "product_id": product_id, "wh_id": wh_id, "bin_id": bin_id}


@pytest.fixture()
def master_data(client, auth_headers) -> dict:
    return create_company_counterparties(client, auth_headers)
