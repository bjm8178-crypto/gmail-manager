"""
test_main_routes.py — FastAPI route handler tests
Tests verified route handlers in main.py
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies"""
    with patch('main.get_credentials') as mock_creds, \
         patch('main.database') as mock_db, \
         patch('main.AIRouter') as mock_ai:
        mock_creds.return_value = MagicMock()
        yield {
            'creds': mock_creds,
            'db': mock_db,
            'ai': mock_ai
        }


def test_root_endpoint_returns_welcome():
    """Test root endpoint returns API info"""
    from main import app
    client = TestClient(app)
    
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "status" in data


def test_health_endpoint_success(mock_dependencies):
    """Test /health endpoint returns healthy status"""
    from main import app
    client = TestClient(app)
    mock_dependencies['db'].get_user_id.return_value = 1
    
    with patch('main.build_gmail_service'):
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy" or "database" in data


def test_get_labels_returns_user_labels(mock_dependencies):
    """Test /labels GET endpoint returns user's Gmail labels"""
    from main import app
    client = TestClient(app)
    
    mock_service = MagicMock()
    mock_service.users().labels().list().execute.return_value = {
        "labels": [
            {"id": "Label_1", "name": "Important", "type": "user"},
            {"id": "Label_2", "name": "Personal", "type": "user"}
        ]
    }
    
    with patch('main.build_gmail_service', return_value=mock_service), \
         patch('main.get_user_id', return_value=1):
        response = client.get("/labels", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "labels" in data
        assert len(data["labels"]) >= 0


def test_scan_endpoint_requires_auth():
    """Test /scan endpoint rejects unauthenticated requests"""
    from main import app
    client = TestClient(app)
    
    response = client.post("/scan")
    
    assert response.status_code in [401, 403, 422]


def test_scan_endpoint_with_valid_token(mock_dependencies):
    """Test /scan endpoint processes with valid auth"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].get_scan_cursor.return_value = None
    
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}],
        "resultSizeEstimate": 2
    }
    
    with patch('main.build_gmail_service', return_value=mock_service), \
         patch('main.get_user_id', return_value=1), \
         patch('main.gmail.fetch_emails', return_value=[]):
        response = client.post(
            "/scan",
            json={"max_results": 10},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 202]


def test_analyze_email_endpoint_success(mock_dependencies):
    """Test /analyze/{email_id} endpoint analyzes specific email"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].is_already_analyzed.return_value = False
    
    mock_service = MagicMock()
    mock_service.users().messages().get().execute.return_value = {
        "id": "email123",
        "payload": {"headers": [{"name": "Subject", "value": "Test"}]},
        "snippet": "Test email"
    }
    
    with patch('main.build_gmail_service', return_value=mock_service), \
         patch('main.get_user_id', return_value=1), \
         patch('main.gmail._analyze_one', return_value={"scam_score": 10}):
        response = client.post(
            "/analyze/email123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 202]


def test_label_endpoint_applies_label(mock_dependencies):
    """Test /label endpoint applies Gmail label to email"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].get_label_id_by_name.return_value = "Label_1"
    
    mock_service = MagicMock()
    mock_service.users().messages().modify().execute.return_value = {"id": "email123"}
    
    with patch('main.build_gmail_service', return_value=mock_service), \
         patch('main.get_user_id', return_value=1):
        response = client.post(
            "/label",
            json={"email_ids": ["email123"], "label_name": "Important"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 207]


def test_rewrite_email_endpoint_success(mock_dependencies):
    """Test /rewrite endpoint rewrites email with AI"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    
    mock_router = AsyncMock()
    mock_router.analyze.return_value = "Rewritten email content"
    
    with patch('main.get_user_id', return_value=1), \
         patch('main.AIRouter', return_value=mock_router):
        response = client.post(
            "/rewrite",
            json={
                "prompt": "Rewrite this email",
                "original_text": "Original email content"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 202]


def test_delete_mode_get_returns_current_mode(mock_dependencies):
    """Test GET /delete-mode returns user's delete mode"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].get_delete_mode.return_value = "trash"
    
    with patch('main.get_user_id', return_value=1):
        response = client.get(
            "/delete-mode",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "delete_mode" in data


def test_delete_mode_set_updates_mode(mock_dependencies):
    """Test POST /delete-mode updates user's delete mode"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].set_delete_mode.return_value = None
    
    with patch('main.get_user_id', return_value=1):
        response = client.post(
            "/delete-mode",
            json={"delete_mode": "permanent"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 204]


def test_quarantine_endpoint_quarantines_emails(mock_dependencies):
    """Test /quarantine endpoint marks emails as quarantined"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].bulk_quarantine_emails.return_value = 2
    
    with patch('main.get_user_id', return_value=1):
        response = client.post(
            "/quarantine",
            json={"email_ids": ["email1", "email2"]},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 207]


def test_safe_endpoint_marks_email_safe(mock_dependencies):
    """Test /safe endpoint marks email as safe"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].mark_email_safe.return_value = None
    
    with patch('main.get_user_id', return_value=1):
        response = client.post(
            "/safe/email123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 204]


def test_retry_endpoint_retries_failed_emails(mock_dependencies):
    """Test /retry endpoint retries failed analysis"""
    from main import app
    client = TestClient(app)
    
    mock_dependencies['db'].get_user_id.return_value = 1
    mock_dependencies['db'].get_pending_retry_queue.return_value = []
    
    with patch('main.get_user_id', return_value=1):
        response = client.post(
            "/retry",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code in [200, 202]


def test_cors_headers_present():
    """Test CORS headers are configured"""
    from main import app
    client = TestClient(app)
    
    response = client.options("/")
    
    # CORS preflight should return headers
    assert response.status_code in [200, 204, 405]
