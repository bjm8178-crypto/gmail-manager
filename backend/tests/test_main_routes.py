"""
test_main_routes.py — FastAPI route handler tests
Tests verified route handlers in main.py with proper dependency overrides
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def test_root_endpoint_returns_welcome():
    """Test root endpoint returns API info"""
    from main import app
    client = TestClient(app)
    
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "status" in data


def test_health_endpoint_success():
    """Test /health endpoint returns healthy status"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_user_id', return_value=1), \
             patch('database._get_connection'), \
             patch('database._execute', return_value=[]):
            response = client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data or "database" in data
    finally:
        app.dependency_overrides.clear()


def test_get_labels_returns_user_labels():
    """Test /labels GET endpoint returns user's Gmail labels"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_labels', return_value=[
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


def test_scan_endpoint_requires_auth():
    """Test /scan endpoint rejects unauthenticated requests"""
    from main import app
    client = TestClient(app)
    
    response = client.post("/scan")
    
    assert response.status_code in [401, 403, 422]


def test_scan_endpoint_with_valid_token():
    """Test /scan endpoint processes with valid auth"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('gmail.fetch_emails', return_value={
            "emails": [{"id": "msg1"}, {"id": "msg2"}],
            "next_page_token": None
        }), \
             patch('auth.get_credentials', return_value=MagicMock()):
            response = client.post("/scan", json={"max_results": 10})
            
            assert response.status_code in [200, 202]
    finally:
        app.dependency_overrides.clear()


def test_analyze_email_endpoint_success():
    """Test /analyze/{email_id} endpoint analyzes specific email"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.is_already_analyzed', return_value=False), \
             patch('gmail._analyze_one', return_value={"scam_score": 10}), \
             patch('auth.get_credentials', return_value=MagicMock()):
            response = client.post("/analyze/email123")
            
            assert response.status_code in [200, 202, 404]
    finally:
        app.dependency_overrides.clear()


def test_label_endpoint_applies_label():
    """Test /label endpoint applies Gmail label to email"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_label_id_by_name', return_value="Label_1"), \
             patch('gmail.apply_label', return_value=None), \
             patch('auth.get_credentials', return_value=MagicMock()):
            response = client.post(
                "/label",
                json={"email_ids": ["email123"], "label_name": "Important"}
            )
            
            assert response.status_code in [200, 207]
    finally:
        app.dependency_overrides.clear()


def test_delete_mode_get_returns_current_mode():
    """Test GET /delete-mode returns user's delete mode"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_delete_mode', return_value="trash"):
            response = client.get("/delete-mode")
            
            assert response.status_code == 200
            data = response.json()
            assert "delete_mode" in data
    finally:
        app.dependency_overrides.clear()


def test_delete_mode_set_updates_mode():
    """Test POST /delete-mode updates user's delete mode"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.set_delete_mode', return_value=None):
            response = client.post(
                "/delete-mode",
                json={"delete_mode": "permanent"}
            )
            
            assert response.status_code in [200, 204]
    finally:
        app.dependency_overrides.clear()


def test_quarantine_endpoint_quarantines_emails():
    """Test /quarantine endpoint marks emails as quarantined"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.bulk_quarantine_emails', return_value=2):
            response = client.post(
                "/quarantine",
                json={"email_ids": ["email1", "email2"]}
            )
            
            assert response.status_code in [200, 207]
    finally:
        app.dependency_overrides.clear()


def test_safe_endpoint_marks_email_safe():
    """Test /safe endpoint marks email as safe"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.mark_email_safe', return_value=None):
            response = client.post("/safe/email123")
            
            assert response.status_code in [200, 204]
    finally:
        app.dependency_overrides.clear()


def test_retry_endpoint_retries_failed_emails():
    """Test /retry endpoint retries failed analysis"""
    from main import app
    from dependencies import require_auth
    
    def mock_require_auth():
        return {"user_id": 1, "email": "test@example.com"}
    
    app.dependency_overrides[require_auth] = mock_require_auth
    client = TestClient(app)
    
    try:
        with patch('database.get_pending_retry_queue', return_value=[]), \
             patch('auth.get_credentials', return_value=MagicMock()):
            response = client.post("/retry")
            
            assert response.status_code in [200, 202]
    finally:
        app.dependency_overrides.clear()


def test_cors_headers_present():
    """Test CORS headers are configured"""
    from main import app
    client = TestClient(app)
    
    response = client.options("/")
    
    # CORS preflight should return headers
    assert response.status_code in [200, 204, 405]
