"""
test_database_connection.py — Test database connection management, pooling, and error handling
"""
import pytest
from unittest.mock import MagicMock, patch, call
import time

# Test connection acquisition and release
def test_get_connection_from_pool_succeeds():
    """Test successful connection retrieval from pool"""
    from database import _get_connection, _pg_pool
    
    mock_conn = MagicMock()
    with patch.object(_pg_pool, 'getconn', return_value=mock_conn):
        conn = _get_connection()
        assert conn == mock_conn
        _pg_pool.getconn.assert_called_once()


def test_release_connection_returns_to_pool():
    """Test connection is returned to pool after use"""
    from database import _release_connection, _pg_pool
    
    mock_conn = MagicMock()
    with patch.object(_pg_pool, 'putconn') as mock_putconn:
        _release_connection(mock_conn)
        mock_putconn.assert_called_once_with(mock_conn, close=False)


def test_release_connection_with_close_flag():
    """Test connection is closed when close=True"""
    from database import _release_connection, _pg_pool
    
    mock_conn = MagicMock()
    with patch.object(_pg_pool, 'putconn') as mock_putconn:
        _release_connection(mock_conn, close=True)
        mock_putconn.assert_called_once_with(mock_conn, close=True)


def test_get_connection_retries_on_pool_error():
    """Test connection acquisition retries on PoolError"""
    from database import _get_connection, _pg_pool
    import psycopg2
    
    mock_conn = MagicMock()
    with patch.object(_pg_pool, 'getconn', side_effect=[
        psycopg2.pool.PoolError("Pool exhausted"),
        psycopg2.pool.PoolError("Pool exhausted"),
        mock_conn
    ]), patch('time.sleep'):
        conn = _get_connection()
        assert conn == mock_conn
        assert _pg_pool.getconn.call_count == 3


def test_get_connection_fails_after_max_retries():
    """Test connection acquisition fails after 5 retries"""
    from database import _get_connection, _pg_pool
    import psycopg2
    
    with patch.object(_pg_pool, 'getconn', side_effect=psycopg2.pool.PoolError("Pool exhausted")), \
         patch('time.sleep'):
        with pytest.raises(psycopg2.pool.PoolError):
            _get_connection()
        assert _pg_pool.getconn.call_count == 5


def test_execute_replaces_placeholder():
    """Test _execute replaces %s with correct placeholder"""
    from database import _execute
    
    mock_cursor = MagicMock()
    _execute(mock_cursor, "SELECT * FROM users WHERE user_id = %s", (123,))
    
    mock_cursor.execute.assert_called_once()
    executed_query = mock_cursor.execute.call_args[0][0]
    assert "%s" in executed_query
    assert mock_cursor.execute.call_args[0][1] == (123,)


def test_execute_without_params():
    """Test _execute works without parameters"""
    from database import _execute
    
    mock_cursor = MagicMock()
    _execute(mock_cursor, "SELECT COUNT(*) FROM users")
    
    mock_cursor.execute.assert_called_once()
    assert mock_cursor.execute.call_args[0][1] == ()


def test_column_exists_postgres_true():
    """Test _column_exists returns True when column exists (Postgres)"""
    from database import _column_exists, USE_POSTGRES
    
    if not USE_POSTGRES:
        pytest.skip("Postgres-only test")
    
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"column_name": "user_id"}
    
    result = _column_exists(mock_cursor, "users", "user_id")
    assert result is True
    mock_cursor.execute.assert_called_once()


def test_column_exists_postgres_false():
    """Test _column_exists returns False when column missing (Postgres)"""
    from database import _column_exists, USE_POSTGRES
    
    if not USE_POSTGRES:
        pytest.skip("Postgres-only test")
    
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    
    result = _column_exists(mock_cursor, "users", "nonexistent_column")
    assert result is False
