"""Initial PostgreSQL schema migration.

Revision ID: 0001_initial_schema
"""
from pathlib import Path

from alembic import op


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).parents[2] / "postgres_schema.sql"
    op.execute(schema_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    for table in (
        "audit_log",
        "ml_disagreements",
        "ml_models",
        "dead_letter_queue",
        "retry_queue",
        "url_cache",
        "analyzed_emails",
        "scan_cursor",
        "custom_labels",
        "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
