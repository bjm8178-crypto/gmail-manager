"""PostgreSQL-only configuration contract tests; no database import."""
from pathlib import Path


ROOT = Path(__file__).parents[1]
DATABASE_SOURCE = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")
ROOT_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")


def test_database_module_refuses_sqlite_fallback():
    assert "SQLite is disabled" in DATABASE_SOURCE
    assert "DATABASE_URL is required" in DATABASE_SOURCE
    assert "import sqlite3" not in DATABASE_SOURCE


def test_root_example_does_not_enable_sqlite():
    assert "FORCE_SQLITE=false" in ROOT_EXAMPLE
    assert "FORCE_SQLITE=true" not in ROOT_EXAMPLE
