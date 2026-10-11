"""
test_health_endpoint.py — Phase 4: /health Endpoint Tests
Tests the comprehensive system health monitoring endpoint.
"""

import os
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint_returns_200():
    """Healthy returns 200; degraded returns 503 for monitoring correctness."""
    response = client.get("/health")
    data = response.json()
    assert response.status_code == (200 if data["status"] == "healthy" else 503)


def test_health_endpoint_has_required_fields():
    """Test that /health response includes all required fields."""
    response = client.get("/health")
    data = response.json()
    
    # Required fields
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "commit_sha" in data
    assert "build_timestamp" in data
    assert "environment" in data
    assert "database" in data
    
    # Status should be healthy or degraded
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    # Version should match
    assert data["version"] == "2.0.0"
    
    # Environment should be valid
    assert data["environment"] in ["production", "development"]


def test_health_endpoint_database_status():
    """Test that database health check is present."""
    response = client.get("/health")
    data = response.json()
    
    assert "database" in data
    db_status = data["database"]
    
    # Database status should have either connected or error state
    assert "status" in db_status
    
    if db_status["status"] == "connected":
        # Connected state should have metrics
        assert "pending_queue_count" in db_status
        assert "total_emails" in db_status
        assert isinstance(db_status["pending_queue_count"], int)
        assert isinstance(db_status["total_emails"], int)
    else:
        # Error state should have error message
        assert "error" in db_status


def test_health_endpoint_timestamp_format():
    """Test that timestamp is in ISO 8601 format."""
    response = client.get("/health")
    data = response.json()
    
    timestamp = data["timestamp"]
    # Should be ISO 8601 format (e.g., "2026-10-01T01:57:53.945123+00:00")
    assert "T" in timestamp
    assert isinstance(timestamp, str)


def test_health_endpoint_uptime_optional():
    """Test that uptime field is optional (depends on psutil)."""
    response = client.get("/health")
    data = response.json()
    
    # Uptime is optional (only present if psutil is installed)
    if "uptime_seconds" in data:
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0


def test_health_endpoint_no_auth_required():
    """Test that /health endpoint does not require authentication."""
    # Should work without any auth headers
    response = client.get("/health")
    data = response.json()
    assert response.status_code == (200 if data["status"] == "healthy" else 503)
    # Should NOT return 401 Unauthorized
    assert response.status_code != 401


def test_health_endpoint_commit_sha():
    """Test that commit_sha is present (may be 'unknown' in dev)."""
    response = client.get("/health")
    data = response.json()
    
    assert "commit_sha" in data
    # Should be either a git SHA or "unknown"
    commit_sha = data["commit_sha"]
    assert isinstance(commit_sha, str)
    assert len(commit_sha) > 0


def test_health_endpoint_build_timestamp():
    """Test that build_timestamp is present (may be 'unknown' in dev)."""
    response = client.get("/health")
    data = response.json()
    
    assert "build_timestamp" in data
    build_timestamp = data["build_timestamp"]
    assert isinstance(build_timestamp, str)
    assert len(build_timestamp) > 0


def test_root_endpoint_still_works():
    """Test that the original / endpoint still works."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Gmail Manager API"
    assert data["status"] == "running"


def test_health_vs_root_endpoints():
    """Test that /health provides more info than / endpoint."""
    root_response = client.get("/")
    health_response = client.get("/health")
    
    root_data = root_response.json()
    health_data = health_response.json()
    
    # Health should have more fields than root
    assert len(health_data) > len(root_data)
    
    # Health should have database info (root doesn't)
    assert "database" in health_data
    assert "database" not in root_data


def test_health_endpoint_json_response():
    """Test that /health returns JSON content-type."""
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"


def test_health_query_failure_rolls_back_before_postgres_connection_release():
    """A failed PostgreSQL health query must not poison the connection pool."""
    import main

    class FakeCursor:
        def execute(self, query, params=()):
            pass

        def fetchone(self):
            return (1,)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.rollback_count = 0

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rollback_count += 1

    connection = FakeConnection()
    execute_calls = []
    released = []

    def failing_execute(cursor, query, params=()):
        execute_calls.append((query, params))
        raise RuntimeError("simulated PostgreSQL query failure")

    with patch.object(main, "_get_connection", return_value=connection), \
            patch.object(main, "_execute", side_effect=failing_execute), \
            patch.object(main, "_release_connection", side_effect=lambda conn: released.append(conn)), \
            patch.object(main, "get_scheduler_status", return_value={"running": False}):
        response = asyncio.run(main.health_check())

    assert response.status_code == 503
    assert connection.rollback_count == 1
    assert released == [connection]
    assert len(execute_calls) == 1


# Integration test (requires database)
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION", "0") != "1",
    reason="Requires database connection (use --run-integration flag)"
)
def test_health_endpoint_with_database():
    """Integration test: Verify database health check works with real database."""
    response = client.get("/health")
    data = response.json()
    
    # Should be healthy with working database
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "connected"
    assert data["database"]["pending_queue_count"] >= 0
    assert data["database"]["total_emails"] >= 0
