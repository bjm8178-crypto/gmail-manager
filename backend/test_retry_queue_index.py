"""Retry queue index coverage for the actual database schema and query shape."""

from pathlib import Path

import database


INDEX_NAME = "idx_retry_queue_retry_count_last_attempted_email_id"


def test_retry_queue_migration_targets_existing_columns():
    migration = Path(__file__).with_name("migrations") / "003_add_retry_queue_composite_index.sql"
    sql = migration.read_text(encoding="utf-8")
    index_sql = " ".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert INDEX_NAME in index_sql
    assert "retry_count" in index_sql
    assert "last_attempted" in index_sql
    assert "email_id" in index_sql
    assert "user_id" not in index_sql
    assert "next_retry_at" not in index_sql


def test_retry_queue_composite_index_exists():
    conn = database._get_connection()
    try:
        cursor = conn.cursor()
        if database.USE_POSTGRES:
            cursor.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = %s",
                (INDEX_NAME,),
            )
            names = {row["indexname"] for row in cursor.fetchall()}
        else:
            cursor.execute("PRAGMA index_list(retry_queue)")
            names = {row[1] for row in cursor.fetchall()}
        assert INDEX_NAME in names
    finally:
        database._release_connection(conn)
