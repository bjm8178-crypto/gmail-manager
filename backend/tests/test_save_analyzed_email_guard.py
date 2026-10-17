"""Tests for save_analyzed_email no-downgrade guard and ownership enforcement."""
import pytest


USER_1 = 99801
USER_2 = 99802
LABEL_1 = 99801
LABEL_2 = 99802


@pytest.fixture(autouse=True)
def cleanup_guard_test_data(isolated_postgres_db):
    db = isolated_postgres_db
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        db._execute(cur, """
            INSERT INTO users (user_id, gmail_address)
            VALUES (%s, 'guard_user1@test.com'), (%s, 'guard_user2@test.com')
            ON CONFLICT (user_id) DO NOTHING
        """, (USER_1, USER_2))
        db._execute(cur, """
            INSERT INTO custom_labels (label_id, user_id, label_name)
            VALUES (%s, %s, 'Inbox'), (%s, %s, 'Inbox')
            ON CONFLICT (label_id) DO NOTHING
        """, (LABEL_1, USER_1, LABEL_2, USER_2))
        conn.commit()
    finally:
        db._release_connection(conn)

    yield

    conn = db._get_connection()
    try:
        cur = conn.cursor()
        db._execute(cur, "DELETE FROM analyzed_emails WHERE user_id IN (%s, %s)", (USER_1, USER_2))
        db._execute(cur, "DELETE FROM custom_labels WHERE user_id IN (%s, %s)", (USER_1, USER_2))
        db._execute(cur, "DELETE FROM users WHERE user_id IN (%s, %s)", (USER_1, USER_2))
        conn.commit()
    finally:
        db._release_connection(conn)


def test_labeled_row_not_downgraded_by_failed(isolated_postgres_db):
    db = isolated_postgres_db

    email_id = "test_guard_failed_1"
    # Initial save: labeled with scam_score=40
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=LABEL_1,
        scam_score=40,
        scam_indicators='["suspicious"]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="labeled",
    )

    # Attempt to overwrite with status='failed'
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=None,
        scam_score=None,
        scam_indicators='[]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="failed",
    )

    # Verify row remains labeled with scam_score=40
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        db._execute(cur, "SELECT status, scam_score FROM analyzed_emails WHERE email_id = %s", (email_id,))
        row = cur.fetchone()
        assert row["status"] == "labeled"
        assert row["scam_score"] == 40
    finally:
        db._release_connection(conn)


def test_labeled_row_not_downgraded_by_fetched(isolated_postgres_db):
    db = isolated_postgres_db

    email_id = "test_guard_fetched_1"
    # Initial save: labeled with scam_score=40
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=LABEL_1,
        scam_score=40,
        scam_indicators='["suspicious"]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="labeled",
    )

    # Attempt to overwrite with status='fetched'
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=None,
        scam_score=None,
        scam_indicators='[]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="fetched",
    )

    # Verify row remains labeled with scam_score=40
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        db._execute(cur, "SELECT status, scam_score FROM analyzed_emails WHERE email_id = %s", (email_id,))
        row = cur.fetchone()
        assert row["status"] == "labeled"
        assert row["scam_score"] == 40
    finally:
        db._release_connection(conn)


def test_failed_row_upgraded_by_labeled(isolated_postgres_db):
    db = isolated_postgres_db

    email_id = "test_upgrade_1"
    # Initial save: failed
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=None,
        scam_score=None,
        scam_indicators='[]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="failed",
    )

    # Overwrite with status='labeled'
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=LABEL_1,
        scam_score=25,
        scam_indicators='["clean"]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="labeled",
    )

    # Verify row is upgraded
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        db._execute(cur, "SELECT status, scam_score FROM analyzed_emails WHERE email_id = %s", (email_id,))
        row = cur.fetchone()
        assert row["status"] == "labeled"
        assert row["scam_score"] == 25
    finally:
        db._release_connection(conn)


def test_different_user_same_email_id_raises_value_error(isolated_postgres_db):
    db = isolated_postgres_db

    email_id = "test_cross_user_1"
    # User 1 saves email
    db.save_analyzed_email(
        email_id=email_id,
        user_id=USER_1,
        label_id=LABEL_1,
        scam_score=20,
        scam_indicators='[]',
        is_quarantined=0,
        snippet="snippet",
        sender="sender@test.com",
        subject="Subject",
        status="labeled",
    )

    # User 2 tries to save same email_id -> must raise ValueError
    with pytest.raises(ValueError, match="different account"):
        db.save_analyzed_email(
            email_id=email_id,
            user_id=USER_2,
            label_id=LABEL_2,
            scam_score=80,
            scam_indicators='[]',
            is_quarantined=1,
            snippet="snippet",
            sender="sender@test.com",
            subject="Subject",
            status="labeled",
        )
