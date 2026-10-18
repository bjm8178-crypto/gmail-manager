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
    # RealDictRow is dict-like: dict(row) works because row already behaves as a dict
    mock_row1 = {
        "email_id": "email1", "sender": "user@test.com", "subject": "Subject 1",
        "scam_score": 10, "is_quarantined": 0, "snippet": "snippet1",
        "body": "", "received_at": "2024-01-01", "analyzed_at": "2024-01-01"
    }
    mock_row2 = {
        "email_id": "email2", "sender": "user@test.com", "subject": "Subject 2",
        "scam_score": 5, "is_quarantined": 0, "snippet": "snippet2",
        "body": "", "received_at": "2024-01-01", "analyzed_at": "2024-01-01"
    }
    mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_emails_by_ids
        result = get_emails_by_ids(user_id=1, email_ids=["email1", "email2"])
        
        assert len(result) == 2
        assert result[0]["email_id"] == "email1"
        assert result[0]["id"] == "email1"  # Line 936 sets row["id"] = row["email_id"]
        assert mock_cursor.execute.called


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


def test_get_analyzed_emails_include_body_false(mock_pg_connection):
    """Test get_analyzed_emails with include_body=False excludes raw body column in SQL query"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = [
        {"email_id": "e1", "user_id": 1, "subject": "Hello", "snippet": "snippet"}
    ]

    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        from database import get_analyzed_emails

        emails = get_analyzed_emails(user_id=1, include_body=False)
        assert len(emails) == 1
        assert "body" not in emails[0]
        sql_executed = mock_cursor.execute.call_args[0][0]
        assert "ae.*" not in sql_executed
        assert "ae.snippet" in sql_executed


def test_get_analyzed_emails_include_body_true(mock_pg_connection):
    """Test get_analyzed_emails with include_body=True selects ae.*"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = [
        {"email_id": "e1", "user_id": 1, "subject": "Hello", "body": "full body"}
    ]

    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        from database import get_analyzed_emails

        emails = get_analyzed_emails(user_id=1, include_body=True)
        assert len(emails) == 1
        sql_executed = mock_cursor.execute.call_args[0][0]
        assert "ae.*" in sql_executed


def test_get_email_body_returns_body_for_owner(mock_pg_connection):
    """Test get_email_body returns body and snippet scoped to user_id"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {
        "email_id": "e123",
        "body": "Secret content",
        "snippet": "Secret...",
    }

    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        from database import get_email_body

        res = get_email_body(user_id=42, email_id="e123")
        assert res is not None
        assert res["body"] == "Secret content"
        assert res["snippet"] == "Secret..."
        params = mock_cursor.execute.call_args[0][1]
        assert params == ("e123", 42)


def test_get_email_body_returns_none_if_not_found(mock_pg_connection):
    """Test get_email_body returns None when email does not exist or user does not own it"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None

    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        from database import get_email_body

        res = get_email_body(user_id=42, email_id="nonexistent")
        assert res is None

