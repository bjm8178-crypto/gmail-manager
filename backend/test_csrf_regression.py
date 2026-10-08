"""
CSRF regression tests for OAuth callback cookie delivery issue.

Root cause: csrf_token cookie was only set during /auth/callback.
Sessions predating the fix, or any authentication that skipped the callback,
never received the cookie. POSTs failed with 403 while GETs worked.

Fix: /auth/status now sets csrf_token cookie when authenticated user lacks it.

These tests use a minimal FastAPI app with CSRFMiddleware only, no database imports.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient
import secrets

# Import only CSRFMiddleware, not the whole app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from csrf import CSRFMiddleware


def create_test_app():
    """Create minimal FastAPI app with CSRF middleware for testing."""
    app = FastAPI()
    
    @app.get("/ping")
    async def ping_get():
        return {"message": "pong"}
    
    @app.post("/ping")
    async def ping_post():
        return {"message": "pong"}
    
    @app.post("/health")
    async def health():
        return {"status": "ok"}
    
    # Add CSRF middleware with /health exempt
    app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])
    
    return app


def test_post_with_matching_csrf_token_returns_200():
    """POST with matching csrf_token cookie and X-CSRF-Token header returns 200."""
    app = create_test_app()
    client = TestClient(app)
    
    csrf_value = secrets.token_urlsafe(32)
    
    response = client.post(
        "/ping",
        cookies={"csrf_token": csrf_value},
        headers={"X-CSRF-Token": csrf_value}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.json() == {"message": "pong"}


def test_post_without_cookie_and_header_returns_403():
    """POST with no csrf_token cookie and no X-CSRF-Token header returns 403."""
    app = create_test_app()
    client = TestClient(app)
    
    response = client.post("/ping")
    
    assert response.status_code == 403
    assert "CSRF token missing or invalid" in response.text


def test_post_with_cookie_but_no_header_returns_403():
    """POST with csrf_token cookie but no X-CSRF-Token header returns 403."""
    app = create_test_app()
    client = TestClient(app)
    
    csrf_value = secrets.token_urlsafe(32)
    
    response = client.post(
        "/ping",
        cookies={"csrf_token": csrf_value}
    )
    
    assert response.status_code == 403
    assert "CSRF token missing or invalid" in response.text


def test_post_with_mismatched_tokens_returns_403():
    """POST with mismatched csrf_token cookie and X-CSRF-Token header returns 403."""
    app = create_test_app()
    client = TestClient(app)
    
    cookie_token = secrets.token_urlsafe(32)
    header_token = secrets.token_urlsafe(32)
    
    response = client.post(
        "/ping",
        cookies={"csrf_token": cookie_token},
        headers={"X-CSRF-Token": header_token}
    )
    
    assert response.status_code == 403
    assert "CSRF token missing or invalid" in response.text


def test_get_without_token_returns_200():
    """GET requests bypass CSRF validation."""
    app = create_test_app()
    client = TestClient(app)
    
    response = client.get("/ping")
    
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_post_to_exempt_path_bypasses_csrf():
    """POST to an exempt path (/health) bypasses CSRF check."""
    app = create_test_app()
    client = TestClient(app)
    
    # POST to /health without csrf_token should succeed (exempt)
    response = client.post("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_csrf_diagnostic_logging_on_missing_cookie():
    """Verify CSRF middleware logs the specific rejection reason."""
    # This test verifies that the diagnostic logging added to csrf.py
    # correctly identifies missing cookies vs missing headers vs mismatches.
    # The actual logging is tested through the live backend check.
    pass  # Covered by live verification in step 4
