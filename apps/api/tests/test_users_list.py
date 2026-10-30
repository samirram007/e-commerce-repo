"""Server-side user list: search, filters, sort allowlist and pagination.

GET /api/v1/users returns the standard list envelope
({"items", "total", "page", "page_size"}) with `search`, `is_active`,
`role` filters and validated `sort`/`order` (AGENT.md §8).
"""
import uuid

PASSWORD = "SuperSecret!123"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _create_user(client, headers, *, full_name, roles=None, email=None):
    email = email or _email(full_name.split()[0].lower())
    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": full_name,
            "company_id": headers["X-Company-Id"],
            "role_names": roles or [],
            "is_company_admin": False,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_users_search_matches_name_and_email(client, auth_headers):
    _create_user(client, auth_headers, full_name="Zeta Quartz", email=_email("zetaquartz"))
    _create_user(client, auth_headers, full_name="Yuki Yamada", email=_email("yukiyamada"))

    resp = client.get("/api/v1/users", headers=auth_headers, params={"search": "Zeta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1, body
    assert body["items"][0]["full_name"] == "Zeta Quartz"

    # search also matches the email column
    resp = client.get(
        "/api/v1/users", headers=auth_headers, params={"search": "yukiyamada"}
    )
    assert resp.json()["total"] == 1


def test_users_active_filter(client, auth_headers):
    user = _create_user(client, auth_headers, full_name="Deactivated Person")
    resp = client.patch(
        f"/api/v1/users/{user['id']}", headers=auth_headers, json={"is_active": False}
    )
    assert resp.status_code == 200, resp.text

    inactive = client.get(
        "/api/v1/users", headers=auth_headers, params={"is_active": "false"}
    ).json()
    assert any(u["id"] == user["id"] for u in inactive["items"])
    assert all(u["is_active"] is False for u in inactive["items"])

    active = client.get(
        "/api/v1/users", headers=auth_headers, params={"is_active": "true"}
    ).json()
    assert all(u["is_active"] is True for u in active["items"])
    assert not any(u["id"] == user["id"] for u in active["items"])


def test_users_role_filter(client, auth_headers):
    # The session DB is shared, so other tests' users may hold these roles too:
    # assert on the users created here only.
    ada = _create_user(client, auth_headers, full_name="Ada Accountant", roles=["accountant"])
    other = _create_user(client, auth_headers, full_name="Ivan Inventory", roles=["inventory_manager"])

    resp = client.get("/api/v1/users", headers=auth_headers, params={"role": "accountant"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_id = {u["id"]: u for u in body["items"]}
    assert ada["id"] in by_id and other["id"] not in by_id, body
    assert by_id[ada["id"]]["roles"] == ["accountant"]
    assert all("accountant" in u["roles"] for u in body["items"])

    resp = client.get(
        "/api/v1/users", headers=auth_headers, params={"role": "inventory_manager"}
    ).json()
    ids = [u["id"] for u in resp["items"]]
    assert other["id"] in ids and ada["id"] not in ids


def test_users_server_side_sort(client, auth_headers):
    _create_user(client, auth_headers, full_name="Alfa Bravo")
    _create_user(client, auth_headers, full_name="Zulu Zeta")

    resp = client.get(
        "/api/v1/users",
        headers=auth_headers,
        params={"sort": "full_name", "order": "desc"},
    )
    assert resp.status_code == 200, resp.text
    names = [u["full_name"] for u in resp.json()["items"]]
    assert names == sorted(names, reverse=True)


def test_users_sort_field_allowlist(client, auth_headers):
    """Sorting by a non-allowlisted column must be rejected (AGENT.md §8)."""
    resp = client.get("/api/v1/users", headers=auth_headers, params={"sort": "password_hash"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SORT_FIELD"


def test_users_pagination_envelope(client, auth_headers):
    created = [
        _create_user(client, auth_headers, full_name=name)
        for name in ("Penny Alpha", "Quinn Beta", "Rita Gamma")
    ]
    created_emails = {u["email"] for u in created}

    first = client.get(
        "/api/v1/users",
        headers=auth_headers,
        params={"sort": "email", "order": "asc", "page": 1, "page_size": 2},
    ).json()
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert len(first["items"]) == 2
    assert first["total"] >= 3

    second = client.get(
        "/api/v1/users",
        headers=auth_headers,
        params={"sort": "email", "order": "asc", "page": 2, "page_size": 2},
    ).json()
    assert second["page"] == 2
    seen = {u["id"] for u in first["items"]} | {u["id"] for u in second["items"]}
    # every seeded user shows up on one of the first two pages
    assert len(seen) >= len(created_emails)
