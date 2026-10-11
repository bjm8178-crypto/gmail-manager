"""Verify the safety barriers used by the isolated full-suite runner."""
import asyncio
import os
from pathlib import Path
import socket

import dotenv
import psycopg2
import pytest


def test_environment_files_are_never_loaded(tmp_path):
    if os.environ.get("ISOLATED_TESTS") != "1":
        pytest.skip("Only enforced in isolated test environment")
    assert dotenv.load_dotenv(tmp_path / ".env") is False
    assert dotenv.dotenv_values(tmp_path / ".env") == {}
    for filename in (".env", "private.db", "model.pkl"):
        with pytest.raises(PermissionError, match="isolation forbids"):
            (tmp_path / filename).read_bytes()


def test_live_http_and_dns_are_blocked():
    if os.environ.get("ISOLATED_TESTS") != "1":
        pytest.skip("Only enforced in isolated test environment")
    with pytest.raises(PermissionError, match="live socket"):
        socket.getaddrinfo("example.com", 443)
    with socket.socket() as client:
        with pytest.raises(PermissionError, match="live socket"):
            client.connect(("127.0.0.1", 8000))


def test_ambient_postgres_connections_are_rejected():
    if os.environ.get("ISOLATED_TESTS") != "1":
        pytest.skip("Only enforced in isolated test environment")
    with pytest.raises(RuntimeError, match="outside the disposable"):
        psycopg2.connect("dbname=postgres host=127.0.0.1 port=5432")
    assert Path(os.environ["GMAIL_TEST_SANDBOX"]).resolve() == Path(__file__).resolve().parents[2]


def test_asyncio_private_socketpair_remains_available():
    async def value():
        return 42
    assert asyncio.run(value()) == 42
