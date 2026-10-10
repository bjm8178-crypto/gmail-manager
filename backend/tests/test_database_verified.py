"""
test_database_verified.py — Database verified function tests
Tests actual production functions confirmed to exist in database.py
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_pg_connection():
    """Mock PostgreSQL connection"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.rowcount = 1
    return mock_conn, mock_cursor


def test_get_emails_by_ids_returns_email_list(mock_pg_connection):
    """Test get_emails_by_ids retrieves multiple emails by ID"""
    mock_conn, mock_cursor = mock_pg_connection
    # Mock psycopg2.extras.RealDictRow - dict() calls __iter__ which yields (key, value) tuples
    mock_row1 = MagicMock()
    mock_row1.__iter__ = lambda self: iter([
        ("email_id", "email1"), ("sender", "user@test.com"), ("subject", "Subject 1"), 
        ("scam_score", 10), ("is_quarantined", 0), ("snippet", "snippet1")
    ])
    mock_row2 = MagicMock()
    mock_row2.__iter__ = lambda self: iter([
        ("email_id", "email2"), ("sender", "user@test.com"), ("subject", "Subject 2"),
        ("scam_score", 5), ("is_quarantined", 0), ("snippet", "snippet2")
    ])
    mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_emails_by_ids
        result = get_emails_by_ids(user_id=1, email_ids=["email1", "email2"])
        
        assert len(result) == 2
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "WHERE email_id = ANY" in sql or "email_id IN" in sql


def test_get_emails_by_ids_filters_by_user(mock_pg_connection):
    """Test get_emails_by_ids enforces user_id ownership"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = []
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_emails_by_ids
        result = get_emails_by_ids(user_id=123, email_ids=["email1"])
        
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert 123 in params


def test_get_pending_retry_queue_returns_failed_emails(mock_pg_connection):
    """Test get_pending_retry_queue retrieves emails pending retry"""
    mock_conn, mock_cursor = mock_pg_connection
    # Mock psycopg2 Row objects with proper dict conversion
    mock_row1 = MagicMock()
    mock_row1.keys.return_value = ["email_id", "user_id", "error_message", "retry_count", "last_attempt", "status", "sender", "subject", "snippet", "scam_score", "is_quarantined", "created_at"]
    mock_row1.__iter__ = lambda self: iter(["email_retry1", 1, "Error", 2, "2024-01-01 12:00:00", "failed", "sender", "subject", "snippet", 50, 0, "2024-01-01"])
    mock_row2 = MagicMock()
    mock_row2.keys.return_value = ["email_id", "user_id", "error_message", "retry_count", "last_attempt", "status", "sender", "subject", "snippet", "scam_score", "is_quarantined", "created_at"]
    mock_row2.__iter__ = lambda self: iter(["email_retry2", 1, "Error", 3, "2024-01-01 12:05:00", "failed", "sender", "subject", "snippet", 50, 0, "2024-01-01"])
    mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_pending_retry_queue
        result = get_pending_retry_queue(user_id=1, max_retries=5)
        
        assert len(result) == 2
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "retry_count" in sql.lower()


def test_get_pending_retry_queue_respects_max_retries(mock_pg_connection):
    """Test get_pending_retry_queue filters by max_retries limit"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = []
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_pending_retry_queue
        result = get_pending_retry_queue(user_id=1, max_retries=3)
        
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert 3 in params


def test_mark_retry_attempt_increments_count(mock_pg_connection):
    """Test mark_retry_attempt increments retry counter"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 1
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import mark_retry_attempt
        mark_retry_attempt(email_id="email123", user_id=1)
        
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql
        assert "retry_count" in sql.lower()
        assert mock_conn.commit.called


def test_mark_retry_attempt_enforces_user_id(mock_pg_connection):
    """Test mark_retry_attempt validates user ownership"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 1
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import mark_retry_attempt
        mark_retry_attempt(email_id="email123", user_id=999)
        
        params = mock_cursor.execute.call_args[0][1]
        assert 999 in params


def test_get_dead_letter_queue_returns_exhausted_retries(mock_pg_connection):
    """Test get_dead_letter_queue retrieves emails exceeding retry limit"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_row1 = MagicMock()
    mock_row1.keys.return_value = ["email_id", "retry_count", "last_attempt", "error_message", "created_at"]
    mock_row1.__iter__ = lambda self: iter(["dead1", 5, "2024-01-01 12:00:00", "Exhausted", "2024-01-01"])
    mock_row2 = MagicMock()
    mock_row2.keys.return_value = ["email_id", "retry_count", "last_attempt", "error_message", "created_at"]
    mock_row2.__iter__ = lambda self: iter(["dead2", 6, "2024-01-02 12:00:00", "Exhausted", "2024-01-02"])
    mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_dead_letter_queue
        result = get_dead_letter_queue(user_id=1)
        
        assert len(result) == 2
        assert mock_cursor.execute.called


def test_remove_from_retry_queue_deletes_entry(mock_pg_connection):
    """Test remove_from_retry_queue removes email from retry table"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 1
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import remove_from_retry_queue
        remove_from_retry_queue(email_id="email123")
        
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE" in sql
        assert mock_conn.commit.called


def test_bulk_quarantine_emails_marks_multiple_emails(mock_pg_connection):
    """Test bulk_quarantine_emails sets quarantine flag for list of IDs"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 3
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import bulk_quarantine_emails
        result = bulk_quarantine_emails(
            email_ids=["email1", "email2", "email3"],
            user_id=1
        )
        
        assert result == 3
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql
        assert "is_quarantined" in sql or "quarantine" in sql.lower()


def test_bulk_quarantine_emails_enforces_ownership(mock_pg_connection):
    """Test bulk_quarantine_emails validates user_id on all emails"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 0  # No rows updated (ownership mismatch)
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import bulk_quarantine_emails
        result = bulk_quarantine_emails(email_ids=["email1"], user_id=999)
        
        params = mock_cursor.execute.call_args[0][1]
        assert 999 in params


def test_bulk_quarantine_emails_returns_count(mock_pg_connection):
    """Test bulk_quarantine_emails returns number of updated rows"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 5
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import bulk_quarantine_emails
        result = bulk_quarantine_emails(
            email_ids=["e1", "e2", "e3", "e4", "e5"],
            user_id=1
        )
        
        assert result == 5


def test_get_pending_retry_queue_empty_for_no_failures(mock_pg_connection):
    """Test get_pending_retry_queue returns empty when no pending retries"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = []
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_pending_retry_queue
        result = get_pending_retry_queue(user_id=1)
        
        assert result == []


def test_get_dead_letter_queue_empty_for_no_exhausted(mock_pg_connection):
    """Test get_dead_letter_queue returns empty when no exhausted retries"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = []
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_dead_letter_queue
        result = get_dead_letter_queue(user_id=1)
        
        assert result == []
