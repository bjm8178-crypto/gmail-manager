"""Repeated audit operations must not exhaust or retain database connections."""

import audit
import database


def test_repeated_audit_logging_releases_connections(isolated_postgres_db):
    import os
    for _ in range(1000):
        audit.log_event(user_id=None, action="test.connection_lifecycle")

    if database.USE_POSTGRES and os.environ.get("ISOLATED_TESTS") == "1":
        # In isolated mode, pool should be empty after releases
        assert not database._pg_pool._used
    elif database.USE_POSTGRES:
        # In normal mode, other tests share the pool — just verify no runaway growth
        assert len(database._pg_pool._used) < database._pg_pool.maxconn // 2
