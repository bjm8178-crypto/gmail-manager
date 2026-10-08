"""Schema parity tests for the PostgreSQL deployment schema."""

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "postgres_schema.sql"

EXPECTED_TABLES = {
    "users": {"user_id", "gmail_address", "token", "token_key_version", "token_encrypted_at"},
    "custom_labels": {"label_id", "user_id", "label_name"},
    "scan_cursor": {"cursor_id", "user_id", "last_page_token"},
    "analyzed_emails": {
        "email_id", "user_id", "label_id", "scam_score", "status",
        "applied_to_gmail", "last_applied_label_id", "source", "ml_confidence",
        "provider_used", "reasoning", "routing_decision", "v2_score",
        "analysis_status", "category_status", "url_scan_status", "urls_total",
        "urls_checked", "received_at", "user_decision", "gmail_sync_state",
        "gmail_sync_error", "gmail_sync_attempts", "last_synced_at",
        "attachment_risk", "attachment_details",
    },
    "url_cache": {"url_id", "email_id", "url", "is_safe"},
    "retry_queue": {"retry_id", "email_id", "retry_count", "last_attempted", "error_reason"},
    "dead_letter_queue": {"id", "email_id", "user_id", "error_message", "final_retry_count", "moved_at"},
    "ml_models": {"model_id", "version", "trained_at", "training_row_count", "model_blob"},
    "ml_disagreements": {"disagreement_id", "email_id", "ml_prediction", "logged_at"},
    "audit_log": {"log_id", "user_id", "timestamp", "action", "metadata", "severity"},
}


def _schema_table_columns(schema_text: str, table: str) -> set[str]:
    marker = f"CREATE TABLE IF NOT EXISTS {table} ("
    start = schema_text.find(marker)
    assert start >= 0, f"missing table definition: {table}"
    body_start = start + len(marker)
    body_end = schema_text.find("\n);", body_start)
    assert body_end >= 0, f"unterminated table definition: {table}"
    columns = set()
    for line in schema_text[body_start:body_end].splitlines():
        line = line.strip().rstrip(",")
        if not line or line.startswith("--") or line.startswith("FOREIGN KEY"):
            continue
        name = line.split()[0]
        if name.upper() not in {"PRIMARY", "UNIQUE", "CONSTRAINT"}:
            columns.add(name)
    return columns


def test_postgres_schema_declares_application_tables_and_columns():
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    for table, expected_columns in EXPECTED_TABLES.items():
        actual_columns = _schema_table_columns(schema_text, table)
        missing = expected_columns - actual_columns
        assert not missing, f"{table} missing columns: {sorted(missing)}"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="PostgreSQL test database is not configured")
def test_live_postgres_schema_matches_expected_tables():
    import database

    if not database.USE_POSTGRES:
        pytest.skip("SQLite backend is active")

    conn = database._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        actual_tables = {row["table_name"] for row in cursor.fetchall()}
        assert set(EXPECTED_TABLES) <= actual_tables
        for table, expected_columns in EXPECTED_TABLES.items():
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                (table,),
            )
            actual_columns = {row["column_name"] for row in cursor.fetchall()}
            assert expected_columns <= actual_columns, (table, sorted(expected_columns - actual_columns))
    finally:
        database._release_connection(conn)
