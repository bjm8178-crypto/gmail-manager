"""Alembic migration system verification tests."""

import os
import subprocess
import uuid

import database


def test_alembic_upgrade_creates_all_tables():
    """Verify Alembic upgrade creates the expected schema in an isolated namespace."""
    schema = f"alembic_test_{uuid.uuid4().hex[:12]}"
    conn = database._get_connection()
    cursor = conn.cursor()
    try:
        database._execute(cursor, f"CREATE SCHEMA {schema}")
        conn.commit()
        env = os.environ.copy()
        env["ALEMBIC_SEARCH_PATH"] = schema
        result = subprocess.run(
            ["python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(__file__),
        )
        assert result.returncode == 0, f"Upgrade failed: {result.stderr}"
        database._execute(cursor, "SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = %s", (schema,))
        table_count = cursor.fetchone()["n"]
        assert table_count == 11, f"Expected 11 tables, found {table_count}"
    finally:
        database._execute(cursor, f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conn.commit()
        database._release_connection(conn)


def test_alembic_downgrade_removes_application_tables():
    """Verify Alembic downgrade removes all application tables."""
    schema = f"alembic_test_{uuid.uuid4().hex[:12]}"
    conn = database._get_connection()
    cursor = conn.cursor()
    try:
        database._execute(cursor, f"CREATE SCHEMA {schema}")
        conn.commit()
        env = os.environ.copy()
        env["ALEMBIC_SEARCH_PATH"] = schema
        subprocess.run(
            ["python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            capture_output=True,
            env=env,
            cwd=os.path.dirname(__file__),
            check=True,
        )
        result = subprocess.run(
            ["python", "-m", "alembic", "-c", "alembic.ini", "downgrade", "base"],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(__file__),
        )
        assert result.returncode == 0, f"Downgrade failed: {result.stderr}"
        database._execute(cursor, "SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = %s", (schema,))
        table_count = cursor.fetchone()["n"]
        assert table_count == 1, f"Expected 1 table (alembic_version), found {table_count}"
    finally:
        database._execute(cursor, f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conn.commit()
        database._release_connection(conn)
