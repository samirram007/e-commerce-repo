"""Auth/permission tests: bootstrap is once-only, JWT-gated access, 403s."""


def test_bootstrap_only_once(client, admin_token):  # admin_token ensures an admin exists first, standalone or full-suite
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


def test_logout_clears_cookie_and_blocks_refresh(client, admin_headers):
    """Regression: the Set-Cookie deletion used to be dropped — the handler
    set delete_cookie on the injected Response but returned a fresh
    Response(204), and FastAPI does not merge sub-response headers into a
    directly-returned Response. The browser kept a working refresh cookie,
    so ensureSession() silently restored the session after sign-out and the
    user was bounced straight back into the app."""
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.io", "password": "SuperSecret!123"},
    )
    assert login.status_code == 200
    assert client.cookies.get("refresh_token"), "login must set the cookie"

    out = client.post("/api/v1/auth/logout", headers=admin_headers)
    assert out.status_code == 204, out.text
    assert not client.cookies.get("refresh_token"), "logout must clear the cookie"
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_works_without_authorization_header(client, admin_headers):
    """Sign-out must not require a valid access token (expired-token case):
    presenting the refresh cookie alone revokes the session and clears state."""
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.io", "password": "SuperSecret!123"},
    )
    assert login.status_code == 200

    out = client.post("/api/v1/auth/logout")  # refresh cookie only, no Bearer
    assert out.status_code == 204, out.text
    assert not client.cookies.get("refresh_token")


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
