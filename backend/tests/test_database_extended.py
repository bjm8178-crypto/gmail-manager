"""
test_database_extended.py — Additional database.py function tests for coverage
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


@pytest.fixture
def mock_pg_connection():
    """Mock PostgreSQL connection with cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    return mock_conn, mock_cursor


def test_get_user_id_returns_valid_id(mock_pg_connection):
    """Test get_user_id returns user_id for existing email"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {"user_id": 999}
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_id
        result = get_user_id("user@example.com")
        
        assert result == 999
        mock_cursor.execute.assert_called_once()


def test_get_user_id_raises_for_missing_user(mock_pg_connection):
    """Test get_user_id raises ValueError when user not found"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_id
        with pytest.raises(ValueError, match="User not found"):
            get_user_id("nonexistent@example.com")


def test_get_user_email_by_id_returns_email(mock_pg_connection):
    """Test get_user_email_by_id returns gmail_address"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {"gmail_address": "user@gmail.com"}
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_email_by_id
        result = get_user_email_by_id(123)
        
        assert result == "user@gmail.com"


def test_get_user_email_by_id_returns_none_for_invalid_id(mock_pg_connection):
    """Test get_user_email_by_id returns None when user_id not found"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_email_by_id
        result = get_user_email_by_id(99999)
        
        assert result is None


def test_save_user_ai_key_stores_encrypted_key(mock_pg_connection):
    """Test save_user_ai_key stores encrypted key"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_user_ai_key
        save_user_ai_key(123, "groq", "encrypted_key_data")
        
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


def test_get_user_ai_keys_returns_all_keys(mock_pg_connection):
    """Test get_user_ai_keys returns dict of all provider keys"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {
        "groq_api_key": "key1",
        "gemini_api_key": None,
        "cohere_api_key": "key3",
        "nvidia_api_key": None
    }
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_ai_keys
        result = get_user_ai_keys(123)
        
        assert result["groq"] == "key1"
        assert result["gemini"] is None
        assert result["cohere"] == "key3"
        assert result["nvidia"] is None


def test_get_user_ai_keys_returns_none_for_missing_user(mock_pg_connection):
    """Test get_user_ai_keys returns None dict for missing user"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_user_ai_keys
        result = get_user_ai_keys(99999)
        
        assert all(v is None for v in result.values())


def test_delete_user_ai_key_removes_key(mock_pg_connection):
    """Test delete_user_ai_key sets key to NULL"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import delete_user_ai_key
        delete_user_ai_key(123, "groq")
        
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "NULL" in sql.upper()
        mock_conn.commit.assert_called_once()


def test_get_label_id_by_name_returns_id(mock_pg_connection):
    """Test get_label_id_by_name returns label_id"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {"label_id": 555}
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_label_id_by_name
        result = get_label_id_by_name(123, "Urgent")
        
        assert result == 555


def test_add_label_inserts_new_label(mock_pg_connection):
    """Test add_label creates new label with colors"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.lastrowid = 777
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import add_label
        result = add_label(123, "Priority", "#FF0000", "#FFFFFF")
        
        mock_cursor.execute.assert_called_once()
        assert "INSERT" in mock_cursor.execute.call_args[0][0].upper()
        mock_conn.commit.assert_called_once()
        assert result == 777


def test_get_labels_returns_user_labels(mock_pg_connection):
    """Test get_labels returns list of user's labels"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchall.return_value = [
        {"label_id": 1, "label_name": "Work", "bg_color": "#FF0000", "text_color": "#FFFFFF"},
        {"label_id": 2, "label_name": "Personal", "bg_color": "#00FF00", "text_color": "#000000"}
    ]
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_labels
        result = get_labels(123)
        
        assert len(result) == 2
        assert result[0]["label_name"] == "Work"


def test_delete_label_removes_label(mock_pg_connection):
    """Test delete_label removes label from database"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import delete_label
        delete_label(555, 123)
        
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE" in sql.upper()
        mock_conn.commit.assert_called_once()


def test_get_delete_mode_returns_user_preference(mock_pg_connection):
    """Test get_delete_mode returns user's delete mode"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = {"delete_mode": "trash"}
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_delete_mode
        result = get_delete_mode(123)
        
        assert result == "trash"


def test_get_delete_mode_defaults_to_trash(mock_pg_connection):
    """Test get_delete_mode returns 'trash' when not set"""
    mock_conn, mock_cursor = mock_pg_connection
    mock_cursor.fetchone.return_value = None
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import get_delete_mode
        result = get_delete_mode(123)
        
        assert result == "trash"


def test_set_delete_mode_updates_preference(mock_pg_connection):
    """Test set_delete_mode updates user's delete mode"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import set_delete_mode
        set_delete_mode(123, "trash")
        
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        mock_conn.commit.assert_called_once()


def test_set_delete_mode_rejects_invalid_mode(mock_pg_connection):
    """Test set_delete_mode raises ValueError for invalid mode"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import set_delete_mode
        with pytest.raises(ValueError, match="Invalid delete_mode"):
            set_delete_mode(123, "invalid_mode")


def test_mark_email_safe_clears_quarantine(mock_pg_connection):
    """Test mark_email_safe sets scam_score to 0"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool:
        mock_pool.getconn.return_value = mock_conn
        
        from database import mark_email_safe
        mark_email_safe("email123", 123)
        
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "scam_score" in sql.lower()
        mock_conn.commit.assert_called_once()


def test_save_user_token_encrypts_token(mock_pg_connection):
    """Test save_user_token encrypts and stores OAuth token"""
    mock_conn, mock_cursor = mock_pg_connection
    
    with patch('database._pg_pool') as mock_pool, \
         patch('encryption.encrypt_key', return_value="encrypted_token"), \
         patch('encryption.get_current_version', return_value=1):
        mock_pool.getconn.return_value = mock_conn
        
        from database import save_user_token
        save_user_token("user@gmail.com", '{"token": "data"}')
        
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "token" in sql.lower()
        mock_conn.commit.assert_called_once()
