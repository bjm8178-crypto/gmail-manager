"""
test_main_health.py — Test main.py health and status endpoints
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def test_health_endpoint_basic():
    """Test /health endpoint returns 200 OK with status"""
    from main import app
    
    with patch('main._get_connection') as mock_conn, \
         patch('main._release_connection'):
        
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"count": 0}
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_connection
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


def test_ml_status_endpoint():
    """Test /ml/status endpoint returns model status"""
    from main import app
    
    client = TestClient(app)
    response = client.get("/ml/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "model_loaded" in data or "model_version" in data


def test_ai_status_endpoint():
    """Test /ai/status endpoint returns cascade status"""
    from main import app
    
    client = TestClient(app)
    response = client.get("/ai/status")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
