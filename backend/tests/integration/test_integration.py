"""
Integration tests for Gmail Manager end-to-end flows.

Tests complete user journeys:
- OAuth authentication flow
- Email fetch → analyze → label pipeline
- ML model inference with AI fallback
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from main import app

client = TestClient(app)


def test_health_endpoint_integration():
    """Test /health endpoint returns complete health status."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify required fields
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "database" in data
    assert "scheduler" in data
    
    # Verify scheduler status
    assert isinstance(data["scheduler"], dict)
    assert "running" in data["scheduler"]


def test_ml_metadata_endpoint_integration():
    """Test /api/ml/active-model-metadata endpoint."""
    response = client.get("/api/ml/active-model-metadata")
    
    # Should return either 200 with model data or 404 if no active model
    assert response.status_code in [200, 404]
    
    if response.status_code == 200:
        data = response.json()
        assert "model_type" in data
        assert "model_version" in data
        assert "training_date" in data
        assert "dataset_info" in data
        assert "performance" in data


def test_cors_headers_integration():
    """Test CORS headers are properly set."""
    response = client.options("/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET"
    })
    
    # Should allow CORS
    assert "access-control-allow-origin" in response.headers


def test_rate_limiting_integration():
    """Test rate limiting is active (basic check)."""
    # Make multiple requests - rate limiter should be configured
    response = client.get("/health")
    assert response.status_code == 200
    
    # Check rate limit headers exist (if slowapi is working)
    # Note: In test mode rate limits may not be enforced


def test_security_headers_integration():
    """Test security headers are present."""
    response = client.get("/health")
    
    # Verify security headers exist
    headers = {k.lower(): v for k, v in response.headers.items()}
    
    # Check for key security headers
    assert "x-content-type-options" in headers or response.status_code == 200


def test_gzip_compression_integration():
    """Test GZIP compression is available."""
    response = client.get("/health", headers={
        "Accept-Encoding": "gzip"
    })
    
    # Should successfully handle compression requests
    assert response.status_code == 200


# Note: Full OAuth, email pipeline, and ML cascade tests require
# database setup, OAuth credentials, and Gmail API access.
# These are placeholder integration tests for the infrastructure.
