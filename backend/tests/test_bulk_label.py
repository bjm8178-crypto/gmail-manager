"""Security and schema tests for bulk label updates."""

import uuid

import database


def _execute(cursor, query, params=()):
    database._execute(cursor, query, params)


def test_bulk_label_updates_label_id_and_respects_user_isolation():
    suffix = uuid.uuid4().hex[:10]
    conn = database._get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, "SELECT COALESCE(MAX(user_id), 0) + 1 AS next_id FROM users")
        user_a = cursor.fetchone()["next_id"]
        user_b = user_a + 1
        _execute(cursor, "INSERT INTO users (user_id, gmail_address) VALUES (%s, %s)", (user_a, f"bulk-a-{suffix}@example.com"))
        _execute(cursor, "INSERT INTO users (user_id, gmail_address) VALUES (%s, %s)", (user_b, f"bulk-b-{suffix}@example.com"))
        _execute(cursor, "SELECT COALESCE(MAX(label_id), 0) + 1 AS next_id FROM custom_labels")
        label_id = cursor.fetchone()["next_id"]
        _execute(cursor, "INSERT INTO custom_labels (label_id, user_id, label_name) VALUES (%s, %s, %s)", (label_id, user_a, "Important"))
        for email_id, user_id in ((f"a-{suffix}", user_a), (f"b-{suffix}", user_b)):
            _execute(cursor, "INSERT INTO analyzed_emails (email_id, user_id, status) VALUES (%s, %s, %s)", (email_id, user_id, "labeled"))
        conn.commit()

        count = database.bulk_update_email_labels([f"a-{suffix}", f"b-{suffix}"], label_id, user_a)
        assert count == 1

        _execute(cursor, "SELECT label_id FROM analyzed_emails WHERE email_id = %s", (f"a-{suffix}",))
        assert cursor.fetchone()["label_id"] == label_id
        _execute(cursor, "SELECT label_id FROM analyzed_emails WHERE email_id = %s", (f"b-{suffix}",))
        assert cursor.fetchone()["label_id"] is None
    finally:
        try:
            _execute(cursor, "DELETE FROM users WHERE user_id IN (%s, %s)", (user_a, user_b))
            conn.commit()
        except Exception:
            conn.rollback()
        database._release_connection(conn)
