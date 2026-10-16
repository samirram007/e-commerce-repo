"""User tiers (Developer / Admin / Other User) and the assignable role guard.

Covers: system-tier seeding + labels, single-step user creation with a role,
`/auth/me` role exposure, unknown-role rejection, and the privilege-escalation
guard on member role assignment.
"""
import uuid

PASSWORD = "SuperSecret!123"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _login(client, email: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_user(client, admin_headers, *, company_id=None, role_names=None, is_company_admin=False):
    email = _email("tier")
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Tier User",
            "company_id": company_id,
            "role_names": role_names or [],
            "is_company_admin": is_company_admin,
        },
    )
    assert resp.status_code == 201, resp.text
    return email, resp.json()


def test_tier_roles_seeded_and_labelled(client, admin_headers):
    resp = client.get("/api/v1/roles", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    by_name = {r["name"]: r for r in resp.json()}
    for name, label in (("developer", "Developer"), ("admin", "Admin"), ("other_user", "Other User")):
        assert name in by_name, resp.text
        assert by_name[name]["label"] == label
        assert by_name[name]["is_system"] is True
    # Admin tier is a strict superset of the read-only Other User tier.
    admin_perms = set(by_name["admin"]["permissions"])
    other_perms = set(by_name["other_user"]["permissions"])
    assert other_perms and other_perms < admin_perms


def test_roles_list_requires_auth(client):
    assert client.get("/api/v1/roles").status_code == 401


def test_create_user_with_role_grants_membership(client, admin_headers, company_id):
    email, user = _create_user(
        client, admin_headers, company_id=company_id, role_names=["other_user"]
    )
    assert user["roles"] == ["other_user"]

    members = client.get(f"/api/v1/companies/{company_id}/members", headers=admin_headers)
    assert members.status_code == 200, members.text
    row = next(m for m in members.json() if m["user_id"] == user["id"])
    assert row["email"] == email
    assert row["role_names"] == ["other_user"]


def test_me_exposes_roles_and_scoped_permissions(client, admin_headers, company_id):
    email, _user = _create_user(
        client, admin_headers, company_id=company_id, role_names=["other_user"]
    )
    headers = {**_login(client, email), "X-Company-Id": company_id}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["roles"] == ["other_user"]
    assert body["is_company_admin"] is False
    assert "catalog.view" in body["permissions"]
    assert "company.members.manage" not in body["permissions"]


def test_unknown_role_is_rejected(client, admin_headers, company_id):
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": _email("bad"),
            "password": PASSWORD,
            "full_name": "Bad",
            "company_id": company_id,
            "role_names": ["not_a_real_role"],
        },
    )
    assert resp.status_code == 404, resp.text


def test_elevated_role_assignment_requires_privilege(client, admin_headers, company_id):
    """A member-manager role may grant ordinary roles but not Admin/Developer."""
    role_name = f"hr-{uuid.uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={"name": role_name, "permissions": ["company.members.manage"]},
    )
    assert created.status_code == 201, created.text

    mgr_email, _mgr = _create_user(client, admin_headers, company_id=company_id, role_names=[role_name])
    mgr_headers = {**_login(client, mgr_email), "X-Company-Id": company_id}

    _target_email, target = _create_user(client, admin_headers)

    # Ordinary role: allowed.
    ok = client.post(
        f"/api/v1/companies/{company_id}/members",
        headers=mgr_headers,
        json={"user_id": target["id"], "role_names": ["other_user"]},
    )
    assert ok.status_code == 201, ok.text

    # Elevated role: denied for the non-privileged manager.
    denied = client.patch(
        f"/api/v1/companies/{company_id}/members/{target['id']}",
        headers=mgr_headers,
        json={"role_names": ["admin"]},
    )
    assert denied.status_code == 403, denied.text

    # An existing Admin-tier holder may escalate.
    admin_email, _admin = _create_user(
        client, admin_headers, company_id=company_id, role_names=["admin"]
    )
    admin_headers2 = {**_login(client, admin_email), "X-Company-Id": company_id}
    allowed = client.patch(
        f"/api/v1/companies/{company_id}/members/{target['id']}",
        headers=admin_headers2,
        json={"role_names": ["admin"]},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["role_names"] == ["admin"]
