"""Regression tests for honest PostgreSQL initialization failure handling."""

from unittest.mock import Mock

import pytest

import database


class FailingConnection:
    def __init__(self):
        self.rollback_calls = 0
        self.commit_calls = 0

    def cursor(self):
        raise RuntimeError("schema setup failed")

    def rollback(self):
        self.rollback_calls += 1

    def commit(self):
        self.commit_calls += 1


def test_init_db_rolls_back_and_discards_connection_after_initialization_failure(monkeypatch):
    """A failed schema setup must not return a possibly-poisoned connection to the pool."""
    connection = FailingConnection()
    released = Mock()
    monkeypatch.setattr(database, "_get_connection", lambda: connection)
    monkeypatch.setattr(database, "_release_connection", released)

    with pytest.raises(RuntimeError, match="schema setup failed"):
        database.init_db()

    assert connection.rollback_calls == 1
    released.assert_called_once_with(connection, close=True)


def test_init_db_does_not_log_success_when_initialization_fails(monkeypatch, caplog):
    """Failure must propagate before the success message can be emitted."""
    connection = FailingConnection()
    monkeypatch.setattr(database, "_get_connection", lambda: connection)
    monkeypatch.setattr(database, "_release_connection", lambda conn, close=False: None)

    with caplog.at_level("INFO", logger=database.logger.name):
        with pytest.raises(RuntimeError, match="schema setup failed"):
            database.init_db()

    assert "Database initialized" not in caplog.text


def test_init_db_preserves_initialization_error_if_cleanup_also_fails(monkeypatch):
    """Cleanup errors must not hide the database error that caused startup to fail."""
    connection = FailingConnection()

    def release_with_error(conn, close=False):
        raise OSError("pool cleanup failed")

    monkeypatch.setattr(database, "_get_connection", lambda: connection)
    monkeypatch.setattr(database, "_release_connection", release_with_error)

    with pytest.raises(RuntimeError, match="schema setup failed"):
        database.init_db()
