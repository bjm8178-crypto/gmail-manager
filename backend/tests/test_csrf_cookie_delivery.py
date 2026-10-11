"""Regression tests for OAuth cookie attributes and CSRF enforcement.

These tests use the active PostgreSQL-backed application configuration and patch
only the route's imported collaborators. They do not use SQLite or fake DB URLs.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

import main


def _cookie(response, name: str):
    return next((cookie for cookie in response.cookies.jar if cookie.name == name), None)


def _callback_response(production: bool, frontend_url: str):
    with patch.object(main, "IS_PRODUCTION", production), \
         patch.object(main, "consume_oauth_state", return_value="test-verifier"), \
         patch.object(main, "handle_callback", return_value={
             "success": True,
             "user_id": 123,
             "gmail_address": "test@example.com",
         }), \
         patch.object(main, "create_access_token", return_value="test-jwt"), \
         patch.object(main, "generate_csrf_token", return_value="test-csrf"), \
         patch.dict(main.os.environ, {"FRONTEND_URL": frontend_url}, clear=False), \
         patch("audit.log_event"):
        client = TestClient(main.app)
        return client.get(
            "/auth/callback",
            params={"code": "test-code", "state": "test-state"},
            follow_redirects=False,
        )


def test_oauth_callback_cookies_respect_transport_security():
    local_response = _callback_response(False, "")

    assert local_response.status_code == 303
    assert local_response.headers["location"].startswith("http://localhost:5173/inbox")

    local_jwt = _cookie(local_response, "jwt_token")
    local_csrf = _cookie(local_response, "csrf_token")
    assert local_jwt is not None
    assert local_csrf is not None
    assert not local_jwt.secure
    assert not local_csrf.secure
    assert local_jwt.has_nonstandard_attr("HttpOnly")
    assert not local_csrf.has_nonstandard_attr("HttpOnly")

    production_response = _callback_response(
        True,
        "https://gmail-manager-gamma.vercel.app",
    )

    assert production_response.status_code == 303
    assert production_response.headers["location"].startswith(
        "https://gmail-manager-gamma.vercel.app/inbox"
    )

    production_jwt = _cookie(production_response, "jwt_token")
    production_csrf = _cookie(production_response, "csrf_token")
    assert production_jwt is not None
    assert production_csrf is not None
    assert production_jwt.secure
    assert production_csrf.secure


def _set_auth_override():
    original = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": 999,
        "email": "test@example.com",
    }
    return original


def test_csrf_protection_blocks_post_without_token():
    original = _set_auth_override()
    try:
        response = TestClient(main.app).post("/emails/fetch-only?limit=10")
    finally:
        main.app.dependency_overrides = original

    assert response.status_code == 403
    assert "CSRF token missing or invalid" in response.text


async def _fake_fetch_only_pipeline(*, limit, user_id):
    yield {"type": "complete", "fetched": 0, "skipped": 0}


def test_csrf_protection_accepts_post_with_valid_token():
    csrf_value = "test-csrf-token-32-chars-long-12345"
    original = _set_auth_override()
    try:
        with patch("gmail.fetch_only_pipeline", new=_fake_fetch_only_pipeline):
            response = TestClient(main.app).post(
                "/emails/fetch-only?limit=10",
                cookies={"csrf_token": csrf_value},
                headers={"X-CSRF-Token": csrf_value},
            )
    finally:
        main.app.dependency_overrides = original

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    assert response.json()["fetched"] == 0
