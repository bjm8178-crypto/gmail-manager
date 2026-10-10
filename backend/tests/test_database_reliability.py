"""
Database reliability tests exercising real production functions.

Tests actual SQL execution against mocked PostgreSQL connections.
Verifies ownership enforcement, metadata preservation, and transaction behavior.
"""
import pytest
from unittest.mock import MagicMock, patch, call
import psycopg2


@pytest.fixture
def mock_pg_connection():
    """Mock PostgreSQL connection with cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.rowcount = 1
    return mock_conn, mock_cursor


def test_save_analyzed_email_executes_upsert(mock_pg_connection):
    """Test save_analyzed_email executes INSERT with ON CONFLICT DO UPDATE."""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_analyzed_email
        
        save_analyzed_email(
            email_id="test123",
            user_id=1,
            label_id=5,
            scam_score=45,
            scam_indicators='["test"]',
            is_quarantined=0,
            snippet="Test snippet",
            sender="sender@test.com",
            subject="Test Subject",
            status="labeled",
            body="Test body",
            reasoning="Test reasoning",
            v2_score=42
        )
        
        # Verify INSERT was executed
        assert mock_cursor.execute.called
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO analyzed_emails" in sql_call
        assert "ON CONFLICT (email_id) DO UPDATE" in sql_call
        assert "WHERE analyzed_emails.user_id = excluded.user_id" in sql_call
        
        # Verify commit called
        assert mock_conn.commit.called
        
        # Verify connection released
        assert mock_pool.putconn.called


def test_save_analyzed_email_ownership_enforcement(mock_pg_connection):
    """Test save_analyzed_email rejects cross-account overwrites."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.rowcount = 0  # Simulate ownership conflict
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_analyzed_email
        
        with pytest.raises(ValueError, match="different account"):
            save_analyzed_email(
                email_id="hijacked@mail.com",
                user_id=2,
                label_id=1,
                scam_score=90,
                scam_indicators='["danger"]',
                is_quarantined=1,
                snippet="snippet",
                sender="sender",
                subject="Test"
            )
        
        # Verify rollback called
        assert mock_conn.rollback.called


def test_save_analyzed_email_preserves_metadata(mock_pg_connection):
    """Test save_analyzed_email includes optional v2 metadata fields."""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_analyzed_email
        
        save_analyzed_email(
            email_id="meta123",
            user_id=1,
            label_id=2,
            scam_score=30,
            scam_indicators='[]',
            is_quarantined=0,
            snippet="snippet",
            sender="sender@test.com",
            subject="Subject",
            reasoning="AI reasoning",
            routing_decision="Important",
            v2_score=28,
            analysis_status="complete",
            url_scan_status="clean",
            urls_total=3,
            urls_checked=3
        )
        
        # Verify metadata fields in SQL
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "reasoning" in sql_call
        assert "routing_decision" in sql_call
        assert "v2_score" in sql_call
        assert "analysis_status" in sql_call
        assert "url_scan_status" in sql_call
        
        # Verify values passed
        values = mock_cursor.execute.call_args[0][1]
        assert "AI reasoning" in values
        assert "Important" in values
        assert 28 in values
        assert "complete" in values


def test_update_analyzed_email_requires_user_id(mock_pg_connection):
    """Test update_analyzed_email enforces ownership via user_id."""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import update_analyzed_email
        
        update_analyzed_email(
            email_id="update123",
            user_id=1,
            label_id=3,
            scam_score=55,
            scam_indicators='["indicator"]',
            is_quarantined=0,
            status="labeled"
        )
        
        # Verify WHERE clause includes user_id
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "WHERE email_id = %s AND user_id = %s" in sql_call
        
        # Verify user_id in parameters
        values = mock_cursor.execute.call_args[0][1]
        assert 1 in values
        assert "update123" in values


def test_get_analyzed_emails_joins_labels(mock_pg_connection):
    """Test get_analyzed_emails performs LEFT JOIN with custom_labels."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = [
        {
            "email_id": "email1",
            "label_name": "Important",
            "bg_color": "#ff0000",
            "text_color": "#ffffff",
            "scam_score": 10
        },
        {
            "email_id": "email2",
            "label_name": "Spam",
            "bg_color": "#999999",
            "text_color": "#000000",
            "scam_score": 85
        }
    ]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_analyzed_emails
        
        result = get_analyzed_emails(user_id=1)
        
        # Verify query structure
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "LEFT JOIN custom_labels cl ON ae.label_id = cl.label_id" in sql_call
        assert "LEFT JOIN retry_queue rq" in sql_call
        assert "WHERE ae.user_id = %s" in sql_call
        assert "ORDER BY COALESCE(NULLIF(ae.received_at, ''), CAST(ae.analyzed_at AS TEXT)) DESC" in sql_call
        
        # Verify user_id parameter
        params = mock_cursor.execute.call_args[0][1]
        assert params == (1,)
        
        # Verify result structure
        assert len(result) == 2
        assert result[0]["email_id"] == "email1"
        assert result[0]["label_name"] == "Important"
        assert result[1]["scam_score"] == 85


def test_get_analyzed_emails_ordering(mock_pg_connection):
    """Test get_analyzed_emails orders by received_at with analyzed_at fallback."""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_analyzed_emails
        
        get_analyzed_emails(user_id=1)
        
        sql_call = mock_cursor.execute.call_args[0][0]
        # Verify received_at takes priority over analyzed_at
        assert "COALESCE(NULLIF(ae.received_at, ''), CAST(ae.analyzed_at AS TEXT)) DESC" in sql_call


def test_save_url_result_inserts_cache_entry(mock_pg_connection):
    """Test save_url_result stores URL scan results."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None  # No existing entry
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_url_result
        
        save_url_result(
            email_id="url_test123",
            url="https://example.com",
            is_safe=1,
            threat_type="SAFE"
        )
        
        # Verify SELECT check
        assert mock_cursor.execute.call_count >= 1
        select_call = mock_cursor.execute.call_args_list[0][0][0]
        assert "SELECT 1 FROM url_cache WHERE email_id = %s AND url = %s" in select_call
        
        # Verify INSERT
        insert_call = mock_cursor.execute.call_args_list[1][0][0]
        assert "INSERT INTO url_cache" in insert_call


def test_add_to_retry_queue_stores_failure(mock_pg_connection):
    """Test add_to_retry_queue records email processing failures."""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import add_to_retry_queue
        
        add_to_retry_queue(
            email_id="failed123",
            user_id=1,
            error_reason="rate_limit",
            retry_after_minutes=15
        )
        
        # Verify INSERT with ON CONFLICT
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO retry_queue" in sql_call
        assert "ON CONFLICT (email_id)" in sql_call
        
        # Verify parameters
        values = mock_cursor.execute.call_args[0][1]
        assert "failed123" in values
        assert 1 in values
        assert "rate_limit" in values


def test_connection_pool_retry_logic():
    """Test _get_connection retries on PoolError."""
    import database
    
    mock_pool = MagicMock()
    # First 3 calls fail, 4th succeeds
    mock_conn = MagicMock()
    mock_pool.getconn.side_effect = [
        psycopg2.pool.PoolError("pool exhausted"),
        psycopg2.pool.PoolError("pool exhausted"),
        psycopg2.pool.PoolError("pool exhausted"),
        mock_conn
    ]
    
    with patch.object(database, '_pg_pool', mock_pool):
        conn = database._get_connection()
        
        assert conn == mock_conn
        assert mock_pool.getconn.call_count == 4


def test_transaction_rollback_on_exception(mock_pg_connection):
    """Test save_analyzed_email rolls back on database errors."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.execute.side_effect = psycopg2.IntegrityError("constraint violation")
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_analyzed_email
        
        with pytest.raises(psycopg2.IntegrityError):
            save_analyzed_email(
                email_id="err123",
                user_id=1,
                label_id=1,
                scam_score=50,
                scam_indicators='[]',
                is_quarantined=0,
                snippet="snippet",
                sender="sender",
                subject="subject"
            )
        
        # Verify rollback called
        assert mock_conn.rollback.called
        # Verify connection still released
        assert mock_pool.putconn.called


def test_upsert_user_returns_id(mock_pg_connection):
    """Test upsert_user creates or retrieves user."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {"id": 42}
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import upsert_user
        
        user_id = upsert_user(google_id="google123", email_addr="test@example.com")
        
        # Verify INSERT with ON CONFLICT
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO users" in sql_call
        assert "ON CONFLICT (google_id)" in sql_call
        assert "RETURNING id" in sql_call
        
        # Verify returned ID
        assert user_id == 42


def test_get_labels_filters_by_user(mock_pg_connection):
    """Test get_labels returns only user-specific labels."""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = [
        {"label_id": 1, "label_name": "Important", "bg_color": "#ff0000"},
        {"label_id": 2, "label_name": "Work", "bg_color": "#0000ff"}
    ]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_labels
        
        labels = get_labels(user_id=1)
        
        # Verify WHERE clause
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "WHERE user_id = %s" in sql_call
        
        # Verify user_id parameter
        params = mock_cursor.execute.call_args[0][1]
        assert params == (1,)
        
        # Verify result
        assert len(labels) == 2
        assert labels[0]["label_name"] == "Important"
