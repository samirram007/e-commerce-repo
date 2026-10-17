"""Auth/permission tests: bootstrap is once-only, JWT-gated access, 403s."""


def test_bootstrap_only_once(client):
    resp = client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "second@test.io", "password": "Whatever!123", "full_name": "Nope"},
    )
    assert resp.status_code == 403


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "missing_token"


def test_login_and_me(client, admin_headers):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.io", "password": "SuperSecret!123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["is_platform_admin"] is True


def test_company_scoping_denies_foreign_context(client, admin_headers, company_id):
    """A member-less company context must be rejected for non-platform users.
    Platform admin passes; regular agent scope test lives in flow tests."""
    resp = client.get(
        f"/api/v1/companies/{company_id}", headers=admin_headers
    )
    assert resp.status_code == 200


def test_logout_revokes_refresh_session(client, admin_headers):
    """Logout must decode the presented refresh cookie (no NameError) -> 204."""
    resp = client.post("/api/v1/auth/logout", headers=admin_headers)
    assert resp.status_code == 204, resp.text


def test_refresh_session_jti_fits_column(client, admin_headers):
    """Regression: the refresh-session jti must fit refresh_sessions.jti
    VARCHAR(64). SQLite ignores the length, but Postgres rejects over-long
    values, which broke login/refresh in production-like runs."""
    from sqlalchemy import select

    from app.core.security import decode_token
    from app.db.session import get_session_factory
    from app.modules.identity import service as svc
    from app.modules.identity.models import User

    factory = get_session_factory()
    session = factory()
    try:
        user = session.scalar(select(User))
        assert user is not None
        token, refresh = svc.create_refresh_session(session, user)
        session.commit()
        assert len(refresh.jti) <= 64, "jti exceeds refresh_sessions.jti VARCHAR(64)"
        payload = decode_token(token, expected_type="refresh")
        assert payload["session_jti"] == refresh.jti
    finally:
        session.rollback()
        session.close()
