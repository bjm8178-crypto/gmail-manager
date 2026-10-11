"""Fail closed before application imports; use isolated_runner.py to run the suite.

The suite includes destructive integration tests. A source-only scratch copy and
an exclusively owned PostgreSQL cluster are required, not an ambient DATABASE_URL.
"""
import importlib
import os
from pathlib import Path
import sys
import uuid

import pytest

BACKEND = Path(__file__).resolve().parents[1]
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


@pytest.fixture(autouse=True)
def restore_encryption_configuration():
    """Reload cached keys after monkeypatch restores each test's environment."""
    yield
    if "encryption" in sys.modules:
        importlib.reload(sys.modules["encryption"])
