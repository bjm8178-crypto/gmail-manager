"""
test_explicit_state_model.py — Regression tests for P0-3 explicit state model
Tests that Gmail sync state fields exist and function correctly.
"""
import pytest
from database import init_db, _get_connection, _release_connection, _execute, _column_exists


def test_gmail_sync_state_columns_exist():
    """Verify all Gmail sync state columns are present in analyzed_emails table."""
    init_db()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        required_columns = [
            'gmail_sync_state',
            'gmail_sync_error',
            'gmail_sync_attempts',
            'last_synced_at'
        ]
        
        for column in required_columns:
            assert _column_exists(cursor, 'analyzed_emails', column), \
                f"Missing required column: {column}"
    finally:
        _release_connection(conn)


def test_gmail_sync_state_default_values():
    """Verify Gmail sync state fields have correct default values."""
    init_db()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Insert a test email with minimal fields
        _execute(cursor, """
            INSERT INTO users (gmail_address, access_token) 
            VALUES (%s, %s)
            ON CONFLICT(gmail_address) DO UPDATE SET access_token = excluded.access_token
        """, ('test_sync_state@example.com', 'test_token'))
        
        _execute(cursor, "SELECT user_id FROM users WHERE gmail_address = %s", 
                ('test_sync_state@example.com',))
        user_id = cursor.fetchone()['user_id']
        
        _execute(cursor, """
            INSERT INTO analyzed_emails (email_id, user_id, status)
            VALUES (%s, %s, %s)
        """, ('test_sync_email_1', user_id, 'pending'))
        
        conn.commit()
        
        # Check default values
        _execute(cursor, """
            SELECT gmail_sync_state, gmail_sync_error, gmail_sync_attempts, last_synced_at
            FROM analyzed_emails WHERE email_id = %s
        """, ('test_sync_email_1',))
        
        row = cursor.fetchone()
        assert row['gmail_sync_state'] == 'not_required', \
            f"Expected default gmail_sync_state='not_required', got {row['gmail_sync_state']}"
        assert row['gmail_sync_error'] is None
        assert row['gmail_sync_attempts'] == 0
        assert row['last_synced_at'] is None
        
        # Cleanup
        _execute(cursor, "DELETE FROM analyzed_emails WHERE email_id = %s", ('test_sync_email_1',))
        _execute(cursor, "DELETE FROM users WHERE gmail_address = %s", ('test_sync_state@example.com',))
        conn.commit()
    finally:
        _release_connection(conn)


def test_gmail_sync_state_transitions():
    """Test that sync state can transition through expected values."""
    init_db()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Create test user and email
        _execute(cursor, """
            INSERT INTO users (gmail_address, access_token) 
            VALUES (%s, %s)
            ON CONFLICT(gmail_address) DO UPDATE SET access_token = excluded.access_token
        """, ('test_sync_transitions@example.com', 'test_token'))
        
        _execute(cursor, "SELECT user_id FROM users WHERE gmail_address = %s", 
                ('test_sync_transitions@example.com',))
        user_id = cursor.fetchone()['user_id']
        
        _execute(cursor, """
            INSERT INTO analyzed_emails (email_id, user_id, status, gmail_sync_state)
            VALUES (%s, %s, %s, %s)
        """, ('test_sync_email_2', user_id, 'labeled', 'pending'))
        conn.commit()
        
        # Test transition: pending -> applying
        _execute(cursor, """
            UPDATE analyzed_emails 
            SET gmail_sync_state = %s, gmail_sync_attempts = gmail_sync_attempts + 1
            WHERE email_id = %s
        """, ('applying', 'test_sync_email_2'))
        conn.commit()
        
        _execute(cursor, "SELECT gmail_sync_state, gmail_sync_attempts FROM analyzed_emails WHERE email_id = %s",
                ('test_sync_email_2',))
        row = cursor.fetchone()
        assert row['gmail_sync_state'] == 'applying'
        assert row['gmail_sync_attempts'] == 1
        
        # Test transition: applying -> applied (success)
        _execute(cursor, """
            UPDATE analyzed_emails 
            SET gmail_sync_state = %s, last_synced_at = CURRENT_TIMESTAMP
            WHERE email_id = %s
        """, ('applied', 'test_sync_email_2'))
        conn.commit()
        
        _execute(cursor, "SELECT gmail_sync_state, last_synced_at FROM analyzed_emails WHERE email_id = %s",
                ('test_sync_email_2',))
        row = cursor.fetchone()
        assert row['gmail_sync_state'] == 'applied'
        assert row['last_synced_at'] is not None
        
        # Cleanup
        _execute(cursor, "DELETE FROM analyzed_emails WHERE email_id = %s", ('test_sync_email_2',))
        _execute(cursor, "DELETE FROM users WHERE gmail_address = %s", ('test_sync_transitions@example.com',))
        conn.commit()
    finally:
        _release_connection(conn)


def test_gmail_sync_error_capture():
    """Test that sync errors are properly recorded."""
    init_db()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Create test user and email
        _execute(cursor, """
            INSERT INTO users (gmail_address, access_token) 
            VALUES (%s, %s)
            ON CONFLICT(gmail_address) DO UPDATE SET access_token = excluded.access_token
        """, ('test_sync_error@example.com', 'test_token'))
        
        _execute(cursor, "SELECT user_id FROM users WHERE gmail_address = %s", 
                ('test_sync_error@example.com',))
        user_id = cursor.fetchone()['user_id']
        
        _execute(cursor, """
            INSERT INTO analyzed_emails (email_id, user_id, status, gmail_sync_state)
            VALUES (%s, %s, %s, %s)
        """, ('test_sync_email_3', user_id, 'labeled', 'pending'))
        conn.commit()
        
        # Simulate a sync failure
        error_message = "Gmail API rate limit exceeded"
        _execute(cursor, """
            UPDATE analyzed_emails 
            SET gmail_sync_state = %s,
                gmail_sync_error = %s,
                gmail_sync_attempts = gmail_sync_attempts + 1
            WHERE email_id = %s
        """, ('failed', error_message, 'test_sync_email_3'))
        conn.commit()
        
        _execute(cursor, """
            SELECT gmail_sync_state, gmail_sync_error, gmail_sync_attempts 
            FROM analyzed_emails WHERE email_id = %s
        """, ('test_sync_email_3',))
        row = cursor.fetchone()
        
        assert row['gmail_sync_state'] == 'failed'
        assert row['gmail_sync_error'] == error_message
        assert row['gmail_sync_attempts'] == 1
        
        # Cleanup
        _execute(cursor, "DELETE FROM analyzed_emails WHERE email_id = %s", ('test_sync_email_3',))
        _execute(cursor, "DELETE FROM users WHERE gmail_address = %s", ('test_sync_error@example.com',))
        conn.commit()
    finally:
        _release_connection(conn)
