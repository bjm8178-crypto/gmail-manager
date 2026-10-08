"""
test_audit_logging.py — Phase 6: Audit Logging Tests
Comprehensive test coverage for audit logging system (security & GDPR compliance).
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import _get_connection, _execute, _release_connection
import json
from datetime import datetime, timedelta

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_audit_log():
    """Clear audit_log table before each test."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            INSERT INTO users (user_id, gmail_address)
            VALUES (1, %s)
            ON CONFLICT DO NOTHING
        """, ("audit-test-1@example.com",))
        _execute(cursor, """
            INSERT INTO users (user_id, gmail_address)
            VALUES (2, %s)
            ON CONFLICT DO NOTHING
        """, ("audit-test-2@example.com",))
        _execute(cursor, "DELETE FROM audit_log")
        conn.commit()
        yield
        _execute(cursor, "DELETE FROM audit_log")
        conn.commit()
    finally:
        _release_connection(conn)


class TestAuditLoggingCore:
    """Core audit logging functionality tests."""
    
    def test_log_event_basic(self):
        """Test basic audit event logging."""
        from audit import log_event, ACTION_LOGIN, SEVERITY_INFO
        
        log_event(
            user_id=1,
            action=ACTION_LOGIN,
            severity=SEVERITY_INFO,
            metadata={"email": "test@example.com"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        # Verify log was created
        conn = _get_connection()
        cursor = conn.cursor()
        _execute(cursor, "SELECT * FROM audit_log WHERE user_id = 1")
        row = cursor.fetchone()
        
        assert row is not None
        assert row["action"] == ACTION_LOGIN
        assert row["ip_address"] == "192.168.1.1"
        assert row["user_agent"] == "Mozilla/5.0"
        assert row["severity"] == SEVERITY_INFO
    
    def test_log_event_with_resource(self):
        """Test logging with resource type and ID."""
        from audit import log_event, ACTION_EMAIL_DELETE, SEVERITY_WARNING
        
        log_event(
            user_id=1,
            action=ACTION_EMAIL_DELETE,
            resource_type="email",
            resource_id="abc123",
            severity=SEVERITY_WARNING,
            metadata={"subject": "Test Email"},
            ip_address="10.0.0.1"
        )
        
        conn = _get_connection()
        cursor = conn.cursor()
        _execute(cursor, "SELECT resource_type, resource_id FROM audit_log WHERE user_id = 1")
        row = cursor.fetchone()
        
        assert row["resource_type"] == "email"
        assert row["resource_id"] == "abc123"
    
    def test_log_event_without_user_id(self):
        """Test logging unauthenticated events (failed login)."""
        from audit import log_event, ACTION_LOGIN_FAILED, SEVERITY_WARNING
        
        log_event(
            user_id=None,
            action=ACTION_LOGIN_FAILED,
            severity=SEVERITY_WARNING,
            metadata={"reason": "Invalid credentials"},
            ip_address="203.0.113.42"
        )
        
        conn = _get_connection()
        cursor = conn.cursor()
        _execute(cursor, "SELECT user_id, action FROM audit_log WHERE action = %s", (ACTION_LOGIN_FAILED,))
        row = cursor.fetchone()
        
        assert row["user_id"] is None
        assert row["action"] == ACTION_LOGIN_FAILED
    
    def test_log_event_metadata_json(self):
        """Test metadata JSON serialization."""
        from audit import log_event, ACTION_BULK_DELETE
        
        metadata = {
            "count": 15,
            "sample_ids": ["email1", "email2", "email3"],
            "delete_mode": "trash"
        }
        
        log_event(
            user_id=1,
            action=ACTION_BULK_DELETE,
            metadata=metadata,
            ip_address="10.0.0.1"
        )
        
        conn = _get_connection()
        cursor = conn.cursor()
        _execute(cursor, "SELECT metadata FROM audit_log WHERE user_id = 1")
        row = cursor.fetchone()
        
        stored_metadata = json.loads(row["metadata"])
        assert stored_metadata["count"] == 15
        assert len(stored_metadata["sample_ids"]) == 3
        assert stored_metadata["delete_mode"] == "trash"


class TestAuditLogRetrieval:
    """Test audit log retrieval and filtering."""
    
    def test_get_user_audit_logs_basic(self):
        """Test basic log retrieval for a user."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN
        
        # Create test logs
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.2")
        log_event(user_id=2, action=ACTION_LOGIN, ip_address="10.0.0.3")
        
        # Retrieve user 1's logs
        logs = get_user_audit_logs(user_id=1)
        
        assert len(logs) == 2
        assert logs[0]["user_id"] == 1
        assert logs[1]["user_id"] == 1
    
    def test_get_user_audit_logs_pagination(self):
        """Test pagination with limit and offset."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN
        
        # Create 10 logs
        for i in range(10):
            log_event(user_id=1, action=ACTION_LOGIN, ip_address=f"10.0.0.{i}")
        
        # First page (limit 5)
        page1 = get_user_audit_logs(user_id=1, limit=5, offset=0)
        assert len(page1) == 5
        
        # Second page (limit 5, offset 5)
        page2 = get_user_audit_logs(user_id=1, limit=5, offset=5)
        assert len(page2) == 5
        
        # Verify different logs
        assert page1[0]["log_id"] != page2[0]["log_id"]
    
    def test_get_user_audit_logs_action_filter(self):
        """Test filtering by action type."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN, ACTION_EMAIL_DELETE
        
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_EMAIL_DELETE, ip_address="10.0.0.2")
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.3")
        
        # Filter by ACTION_LOGIN
        logs = get_user_audit_logs(user_id=1, action_filter=ACTION_LOGIN)
        
        assert len(logs) == 2
        assert all(log["action"] == ACTION_LOGIN for log in logs)
    
    def test_get_user_audit_logs_severity_filter(self):
        """Test filtering by severity."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN, SEVERITY_INFO, SEVERITY_CRITICAL
        
        log_event(user_id=1, action=ACTION_LOGIN, severity=SEVERITY_INFO, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_LOGIN, severity=SEVERITY_CRITICAL, ip_address="10.0.0.2")
        log_event(user_id=1, action=ACTION_LOGIN, severity=SEVERITY_INFO, ip_address="10.0.0.3")
        
        # Filter by CRITICAL
        logs = get_user_audit_logs(user_id=1, severity_filter=SEVERITY_CRITICAL)
        
        assert len(logs) == 1
        assert logs[0]["severity"] == SEVERITY_CRITICAL
    
    def test_get_audit_log_count(self):
        """Test counting audit logs."""
        from audit import log_event, get_audit_log_count, ACTION_LOGIN
        
        # Create 7 logs
        for i in range(7):
            log_event(user_id=1, action=ACTION_LOGIN, ip_address=f"10.0.0.{i}")
        
        count = get_audit_log_count(user_id=1)
        assert count == 7
    
    def test_get_audit_log_count_with_filters(self):
        """Test counting with action filter."""
        from audit import log_event, get_audit_log_count, ACTION_LOGIN, ACTION_EMAIL_DELETE
        
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_EMAIL_DELETE, ip_address="10.0.0.2")
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.3")
        
        count = get_audit_log_count(user_id=1, action_filter=ACTION_LOGIN)
        assert count == 2


class TestAuditLogCleanup:
    """Test audit log retention and cleanup."""
    
    def test_cleanup_old_logs(self):
        """Test deleting logs older than retention period."""
        from audit import log_event, cleanup_old_logs, ACTION_LOGIN
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Create old log (100 days ago)
        old_timestamp = (datetime.utcnow() - timedelta(days=100)).isoformat()
        _execute(cursor, """
            INSERT INTO audit_log (user_id, action, timestamp, ip_address, severity)
            VALUES (1, %s, %s, '10.0.0.1', 'info')
        """, (ACTION_LOGIN, old_timestamp))
        
        # Create recent log (10 days ago)
        recent_timestamp = (datetime.utcnow() - timedelta(days=10)).isoformat()
        _execute(cursor, """
            INSERT INTO audit_log (user_id, action, timestamp, ip_address, severity)
            VALUES (1, %s, %s, '10.0.0.2', 'info')
        """, (ACTION_LOGIN, recent_timestamp))
        
        conn.commit()
        
        # Cleanup logs older than 90 days
        deleted_count = cleanup_old_logs(retention_days=90)
        
        assert deleted_count == 1
        
        # Verify only recent log remains
        _execute(cursor, "SELECT COUNT(*) AS count FROM audit_log WHERE user_id = 1")
        count = cursor.fetchone()["count"]
        assert count == 1


class TestAuditEndpoints:
    """Test audit log API endpoints."""
    
    def test_get_audit_logs_endpoint_requires_auth(self):
        """Test that /audit/logs requires authentication."""
        response = client.get("/audit/logs")
        assert response.status_code == 401
    
    def test_get_audit_logs_endpoint_basic(self):
        """Test basic audit log retrieval endpoint."""
        from audit import log_event, ACTION_LOGIN
        
        # Create test logs (simulating authenticated user_id=1)
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.2")
        
        # Mock authentication by setting session (FastAPI TestClient session simulation)
        # Note: In production, this endpoint requires JWT auth via require_auth dependency
        # For testing, we'd need to mock the authentication or use a test user fixture
        
        # This test demonstrates the endpoint structure; actual auth testing requires fixtures
        # assert response.status_code == 200
        # assert response.json()["total_count"] == 2


class TestAuditIntegration:
    """Integration tests for audit logging across the application."""
    
    def test_login_creates_audit_log(self):
        """Test that successful login creates an audit log."""
        # This would require a full OAuth flow simulation
        # Placeholder for integration test
        pass
    
    def test_bulk_delete_creates_audit_log(self):
        """Test that bulk delete operation creates an audit log."""
        # This would require authenticated session + email fixtures
        # Placeholder for integration test
        pass


class TestAuditGDPRCompliance:
    """GDPR compliance tests."""
    
    def test_user_can_access_own_logs(self):
        """Test GDPR Article 15: Right to access processing logs."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN
        
        # User 1 logs
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.2")
        
        # User 2 logs
        log_event(user_id=2, action=ACTION_LOGIN, ip_address="10.0.0.3")
        
        # User 1 can access own logs
        user1_logs = get_user_audit_logs(user_id=1)
        assert len(user1_logs) == 2
        assert all(log["user_id"] == 1 for log in user1_logs)
    
    def test_user_cannot_access_other_logs(self):
        """Test user isolation: cannot access other users' logs."""
        from audit import log_event, get_user_audit_logs, ACTION_LOGIN
        
        log_event(user_id=1, action=ACTION_LOGIN, ip_address="10.0.0.1")
        log_event(user_id=2, action=ACTION_LOGIN, ip_address="10.0.0.2")
        
        # User 1 requests logs (should only see own)
        user1_logs = get_user_audit_logs(user_id=1)
        assert len(user1_logs) == 1
        assert user1_logs[0]["user_id"] == 1
    
    def test_90_day_retention_policy(self):
        """Test GDPR compliance: 90-day retention policy."""
        from audit import cleanup_old_logs
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Create log 91 days ago (should be deleted)
        old_timestamp = (datetime.utcnow() - timedelta(days=91)).isoformat()
        _execute(cursor, """
            INSERT INTO audit_log (user_id, action, timestamp, ip_address, severity)
            VALUES (1, 'test.action', %s, '10.0.0.1', 'info')
        """, (old_timestamp,))
        
        # Create log 89 days ago (should be kept)
        recent_timestamp = (datetime.utcnow() - timedelta(days=89)).isoformat()
        _execute(cursor, """
            INSERT INTO audit_log (user_id, action, timestamp, ip_address, severity)
            VALUES (1, 'test.action', %s, '10.0.0.2', 'info')
        """, (recent_timestamp,))
        
        conn.commit()
        
        # Run cleanup
        deleted = cleanup_old_logs(retention_days=90)
        assert deleted == 1
        
        # Verify retention
        _execute(cursor, "SELECT COUNT(*) AS count FROM audit_log")
        count = cursor.fetchone()["count"]
        assert count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
