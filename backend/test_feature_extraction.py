"""Test feature extraction excludes AI-sourced emails (Task 4.2)."""

import pytest
from features import get_sender_history
from database import init_db, _get_connection, _release_connection, _execute


@pytest.fixture
def setup_test_data():
    """Create test emails with different sources."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    try:
        # Ensure test user exists
        _execute(cursor, """
            SELECT user_id FROM users WHERE gmail_address = %s
        """, ("test_features@example.com",))
        row = cursor.fetchone()
        
        if row:
            user_id = row[0] if isinstance(row, tuple) else row['user_id']
        else:
            _execute(cursor, """
                INSERT INTO users (gmail_address, access_token)
                VALUES (%s, %s)
                RETURNING user_id
            """, ("test_features@example.com", "test_token"))
            row = cursor.fetchone()
            user_id = row[0] if isinstance(row, tuple) else row['user_id']
            conn.commit()
        
        # Clean up any existing test emails
        _execute(cursor, """
            DELETE FROM analyzed_emails WHERE email_id LIKE %s
        """, ("email_feature_%",))
        conn.commit()
        
        # Insert emails with different sources
        test_emails = [
            ("email_feature_ai_1", user_id, "sender@example.com", 80, "ai"),
            ("email_feature_ai_2", user_id, "sender@example.com", 90, "ai"),
            ("email_feature_ml_1", user_id, "sender@example.com", 70, "ml"),
            ("email_feature_human_1", user_id, "sender@example.com", 60, "human"),
        ]
        
        for email_id, uid, sender, score, source in test_emails:
            _execute(cursor, """
                INSERT INTO analyzed_emails 
                (email_id, user_id, sender, scam_score, source, status)
                VALUES (%s, %s, %s, %s, %s, 'labeled')
            """, (email_id, uid, sender, score, source))
        
        conn.commit()
        
        yield conn, user_id
        
    finally:
        # Cleanup
        _execute(cursor, """
            DELETE FROM analyzed_emails WHERE email_id LIKE %s
        """, ("email_feature_%",))
        conn.commit()
        _release_connection(conn)


def test_sender_history_excludes_ai_source(setup_test_data):
    """Verify get_sender_history excludes AI-sourced emails."""
    conn, user_id = setup_test_data
    
    # Query specifically for the sender with test data from fixture
    # The fixture creates 4 emails for sender@example.com: 2 AI, 1 ML, 1 human
    history = get_sender_history("sender@example.com", conn)
    
    # Should only count 2 emails: ML (70) and human (60)
    # AI emails (80, 90) should be excluded
    assert history['sent_count'] == 2, f"Expected 2 non-AI emails, got {history['sent_count']}"
    
    # Both ML (70) and human (60) are >= 60 threshold
    assert history['scam_count'] == 2, f"Expected 2 scam emails (ML + human), got {history['scam_count']}"
    
    # Average should be (70 + 60) / 2 = 65
    assert abs(history['avg_score'] - 65.0) < 0.01, f"Expected avg 65.0, got {history['avg_score']}"


def test_sender_history_returns_default_when_only_ai(setup_test_data):
    """Verify get_sender_history returns defaults when sender has only AI emails."""
    conn, user_id = setup_test_data
    
    # Insert sender with only AI-sourced emails
    cursor = conn.cursor()
    _execute(cursor, """
        INSERT INTO analyzed_emails 
        (email_id, user_id, sender, scam_score, source, status)
        VALUES (%s, %s, %s, %s, %s, 'labeled')
    """, ("email_feature_ai_only", user_id, "ai_only@example.com", 95, "ai"))
    conn.commit()
    
    history = get_sender_history("ai_only@example.com", conn)
    
    # Should return defaults since all emails are AI-sourced
    assert history['sent_count'] == 0
    assert history['scam_count'] == 0
    assert history['avg_score'] == 0.5


def test_sender_history_includes_ml_and_human_sources(setup_test_data):
    """Verify get_sender_history includes ML and human sources."""
    conn, user_id = setup_test_data
    
    # Insert sender with ML and human sources only
    cursor = conn.cursor()
    test_emails = [
        ("email_feature_mixed_ml", user_id, "mixed@example.com", 75, "ml"),
        ("email_feature_mixed_human", user_id, "mixed@example.com", 85, "human"),
    ]
    
    for email_id, uid, sender, score, source in test_emails:
        _execute(cursor, """
            INSERT INTO analyzed_emails 
            (email_id, user_id, sender, scam_score, source, status)
            VALUES (%s, %s, %s, %s, %s, 'labeled')
        """, (email_id, uid, sender, score, source))
    conn.commit()
    
    history = get_sender_history("mixed@example.com", conn)
    
    # Should count both ML and human emails
    assert history['sent_count'] == 2
    assert history['scam_count'] == 2  # Both >= 60
    assert abs(history['avg_score'] - 80.0) < 0.01  # (75 + 85) / 2
