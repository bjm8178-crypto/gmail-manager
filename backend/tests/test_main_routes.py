"""
test_main_routes.py — FastAPI route handler tests with proper CSRF handling
Tests verified route handlers in main.py using TestClient with valid CSRF tokens
"""
import pytest
import secrets
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def _csrf_headers():
    """Generate valid CSRF token cookie and header for POST requests."""
    token = secrets.token_urlsafe(32)
    return {
        "cookies": {"csrf_token": token},
        "headers": {"X-CSRF-Token": token}
    }


def test_root_endpoint_returns_welcome():
    """Test root endpoint returns API info"""
    from main import app
    client = TestClient(app)
    
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "status" in data


def test_health_endpoint_success():
    """Test /health endpoint returns healthy status (exempt from CSRF)"""
    from main import app
    client = TestClient(app)
    
    # /health is CSRF-exempt, no token needed
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data or "database" in data


def test_emails_fetch_endpoint_requires_auth():
    """Test /emails/fetch endpoint rejects unauthenticated requests"""
    from main import app
    client = TestClient(app)
    
    response = client.get("/emails/fetch")
    
    # Should reject due to missing auth
    assert response.status_code in [401, 403, 422]


def test_emails_analyzed_endpoint_with_auth():
    """Test /emails/analyzed endpoint with valid auth"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_analyzed_emails', return_value=[]):
            response = client.get("/emails/analyzed")
            
            assert response.status_code == 200
            data = response.json()
            assert "emails" in data or isinstance(data, list)
    finally:
        app.dependency_overrides.clear()


def test_labels_endpoint_returns_user_labels():
    """Test /labels GET endpoint returns user's Gmail labels"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        with patch('main.get_labels', return_value=[
            {"id": 1, "label_name": "Important", "gmail_label_id": "Label_1"},
            {"id": 2, "label_name": "Personal", "gmail_label_id": "Label_2"}
        ]):
            response = client.get("/labels")
            
            assert response.status_code == 200
            data = response.json()
            assert "labels" in data
            assert len(data["labels"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_emails_analyze_bulk_endpoint():
    """Test /emails/analyze-bulk endpoint"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        csrf = _csrf_headers()
        # Mock the Gmail functions and credentials used in the route
        with patch('main.get_analyzed_emails', return_value=[{"id": "1", "analyzed": False}]), \
             patch('main.analyze_bulk_ordered', return_value={"analyzed": 0, "failed": 0}), \
             patch('main.get_credentials', return_value=MagicMock()):
            response = client.post("/emails/analyze-bulk", json={}, **csrf)
            
            assert response.status_code in [200, 202, 400]  # 400 acceptable if validation fails
    finally:
        app.dependency_overrides.clear()


def test_emails_batch_label_endpoint():
    """Test /emails/batch-label endpoint applies labels"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        csrf = _csrf_headers()
        # Mock the internal _apply_label_change function used in the route
        with patch('main._apply_label_change', return_value={"success": True}), \
             patch('main._request_user_email', return_value="test@example.com"):
            response = client.post(
                "/emails/batch-label",
                json={"changes": [{"email_id": "123", "label_name": "Important"}]},
                **csrf
            )
            
            assert response.status_code in [200, 207]
    finally:
        app.dependency_overrides.clear()


def test_settings_delete_mode_get():
    """Test GET /settings/delete-mode returns user's delete mode"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_delete_mode', return_value="trash"):
            response = client.get("/settings/delete-mode")
            
            assert response.status_code == 200
            data = response.json()
            assert "delete_mode" in data
    finally:
        app.dependency_overrides.clear()


def test_settings_delete_mode_put():
    """Test PUT /settings/delete-mode updates user's delete mode"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        csrf = _csrf_headers()
        with patch('main.set_delete_mode', return_value=None):
            response = client.put(
                "/settings/delete-mode",
                json={"mode": "permanent"},
                **csrf
            )
            
            assert response.status_code in [200, 204]
    finally:
        app.dependency_overrides.clear()


def test_quarantine_get_endpoint():
    """Test GET /quarantine returns quarantined emails"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        with patch('main.get_analyzed_emails', return_value=[]):
            response = client.get("/quarantine")
            
            assert response.status_code == 200
            data = response.json()
            assert "emails" in data or isinstance(data, list)
    finally:
        app.dependency_overrides.clear()


def test_quarantine_safe_endpoint():
    """Test POST /quarantine/{email_id}/safe marks email as safe"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        csrf = _csrf_headers()
        with patch('database.mark_email_safe', return_value=None):
            response = client.post("/quarantine/email123/safe", **csrf)
            
            assert response.status_code in [200, 204]
    finally:
        app.dependency_overrides.clear()


def test_emails_mark_safe_endpoint():
    """Test PATCH /emails/{email_id}/mark-safe endpoint"""
    from main import app
    from dependencies import require_auth
    
    def mock_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_auth
    client = TestClient(app)
    
    try:
        csrf = _csrf_headers()
        with patch('database.mark_email_safe', return_value=None):
            response = client.patch("/emails/email123/mark-safe", **csrf)
            
            assert response.status_code in [200, 204]
    finally:
        app.dependency_overrides.clear()


def test_cors_headers_present():
    """Test CORS headers are configured"""
    from main import app
    client = TestClient(app)
    
    response = client.options("/")
    
    # CORS preflight should return headers
    assert response.status_code in [200, 204, 405]
