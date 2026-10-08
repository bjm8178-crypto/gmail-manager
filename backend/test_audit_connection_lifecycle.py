"""Repeated audit operations must not exhaust or retain database connections."""

import audit
import database


def test_repeated_audit_logging_releases_connections():
    for _ in range(1000):
        audit.log_event(user_id=None, action="test.connection_lifecycle")

    if database.USE_POSTGRES:
        assert not database._pg_pool._used
