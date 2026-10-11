"""Regression tests for bounded retries and dead-letter handling."""

import uuid

import database


def _execute(cursor, query, params=()):
    database._execute(cursor, query, params)


def _seed_email():
    suffix = uuid.uuid4().hex[:10]
    conn = database._get_connection()
    cursor = conn.cursor()
    _execute(cursor, "SELECT COALESCE(MAX(user_id), 0) + 1 AS next_id FROM users")
    user_id = cursor.fetchone()["next_id"]
    _execute(cursor, "INSERT INTO users (user_id, gmail_address) VALUES (%s, %s)", (user_id, f"retry-{suffix}@example.com"))
    email_id = f"retry-{suffix}"
    _execute(cursor, "INSERT INTO analyzed_emails (email_id, user_id, status) VALUES (%s, %s, %s)", (email_id, user_id, "labeled"))
    conn.commit()
    return conn, cursor, user_id, email_id


def test_retry_limit_moves_failed_email_to_dead_letter_queue():
    conn, cursor, user_id, email_id = _seed_email()
    try:
        for attempt in range(database.MAX_RETRIES + 1):
            database.add_to_retry_queue(email_id, user_id, f"failure-{attempt}")
        _execute(cursor, "SELECT retry_count FROM retry_queue WHERE email_id = %s", (email_id,))
        assert cursor.fetchone()["retry_count"] == database.MAX_RETRIES

        database.add_to_retry_queue(email_id, user_id, "permanent failure")
        _execute(cursor, "SELECT email_id, user_id, final_retry_count FROM dead_letter_queue WHERE email_id = %s", (email_id,))
        dlq_row = cursor.fetchone()
        assert dlq_row["user_id"] == user_id
        assert dlq_row["final_retry_count"] == database.MAX_RETRIES
        _execute(cursor, "SELECT 1 FROM retry_queue WHERE email_id = %s", (email_id,))
        assert cursor.fetchone() is None
    finally:
        _execute(cursor, "DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        database._release_connection(conn)


def test_retry_below_limit_remains_retryable():
    conn, cursor, user_id, email_id = _seed_email()
    try:
        for attempt in range(3):
            database.add_to_retry_queue(email_id, user_id, f"failure-{attempt}")
        _execute(cursor, "SELECT retry_count FROM retry_queue WHERE email_id = %s", (email_id,))
        assert cursor.fetchone()["retry_count"] == 2
        _execute(cursor, "SELECT 1 FROM dead_letter_queue WHERE email_id = %s", (email_id,))
        assert cursor.fetchone() is None
    finally:
        _execute(cursor, "DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        database._release_connection(conn)


def test_dead_letter_queue_endpoint_is_registered():
    import main

    routes = {route.path for route in main.app.routes}
    assert "/api/admin/dead-letter-queue" in routes
