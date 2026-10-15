"""Fail closed before application imports; use isolated_runner.py to run the suite.

The suite includes destructive integration tests. A source-only scratch copy and
an exclusively owned PostgreSQL cluster are required, not an ambient DATABASE_URL.
"""
import importlib
import os
from pathlib import Path
import sys
import uuid

os.environ.setdefault("DB_POOL_MAX", "50")

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if os.environ.get("ISOLATED_TESTS") == "1":
    SANDBOX = os.environ.get("GMAIL_TEST_SANDBOX")
    if (not SANDBOX or BACKEND.parent != Path(SANDBOX).resolve()
            or not (BACKEND.parent / ".isolated-test-sandbox").is_file()
            or not getattr(sys, "_gmail_test_isolation", False)):
        raise pytest.UsageError(
            "Unsafe test environment: run backend/tests/isolated_runner.py with "
            "a local PostgreSQL bin directory. Ambient database credentials are forbidden."
        )
sys.path.insert(0, str(BACKEND))


@pytest.fixture
def isolated_postgres_db(monkeypatch):
    """Give destructive/rotation fixtures a new real database, then drop it.

    A database rather than a schema is needed because production column-existence
    queries inspect information_schema across schemas.
    """
    import database
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import make_dsn
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool

    if os.environ.get("ISOLATED_TESTS") == "1":
        # Isolated mode: create disposable database
        name = "gmail_test_" + uuid.uuid4().hex
        admin = psycopg2.connect(os.environ["DATABASE_URL"])
        admin.autocommit = True
        pool = None
        try:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            dsn = make_dsn(os.environ["DATABASE_URL"], dbname=name)
            pool = ThreadedConnectionPool(2, 50, dsn=dsn, cursor_factory=RealDictCursor)
            with monkeypatch.context() as context:
                context.setattr(database, "_pg_pool", pool)
                context.setattr(database, "DATABASE_URL", dsn)
                context.setenv("DATABASE_URL", dsn)
                database.init_db()
                yield database
        finally:
            if pool is not None:
                pool.closeall()
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
            admin.close()
    else:
        # Normal mode: use existing local database, don't create/drop
        database.init_db()
        yield database


@pytest.fixture(autouse=True)
def restore_encryption_configuration():
    """Reload cached keys after monkeypatch restores each test's environment."""
    yield
    if "encryption" in sys.modules:
        importlib.reload(sys.modules["encryption"])


@pytest.fixture(autouse=True)
def sync_db_sequences():
    """Ensure PostgreSQL sequences stay ahead of manually inserted IDs."""
    yield
    import database
    if getattr(database, "_pg_pool", None) is not None:
        try:
            conn = database._get_connection()
            try:
                cur = conn.cursor()
                database._execute(cur, "SELECT setval('users_user_id_seq', COALESCE((SELECT MAX(user_id) FROM users), 0) + 1, false)")
                conn.commit()
            finally:
                database._release_connection(conn)
        except Exception:
            pass
