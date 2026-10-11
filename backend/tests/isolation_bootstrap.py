"""Installed as sitecustomize.py ONLY inside the runner's scratch source copy."""
import os
from pathlib import Path
import sys

if os.environ.get("GMAIL_TEST_SANDBOX"):
    root = Path(os.environ["GMAIL_TEST_SANDBOX"]).resolve()
    if not (root / ".isolated-test-sandbox").is_file():
        raise RuntimeError("Missing isolation marker")

    # python-dotenv 1.0.1 does not support PYTHON_DOTENV_DISABLED. Patch before
    # importing any application module, including in Python subprocess tests.
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    dotenv.dotenv_values = lambda *args, **kwargs: {}

    import socket
    socketpair_code = getattr(socket.socketpair, "__code__", None)

    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            if path.name == ".env" or path.suffix.lower() in {".db", ".pkl"}:
                raise PermissionError("Test isolation forbids environment/database/model file access")
        if event in {"socket.connect", "socket.getaddrinfo"}:
            # Windows asyncio needs the stdlib's private, freshly bound socketpair.
            # Permit exactly that connection, not arbitrary loopback services.
            caller = sys._getframe(1)
            listener = caller.f_locals.get("lsock")
            if (event == "socket.connect" and caller.f_code is socketpair_code
                    and listener is not None
                    and args[1] == listener.getsockname()):
                return
            # Application HTTP must be mocked, not sent even to a local service.
            # PostgreSQL's native libpq is separately constrained below.
            raise PermissionError("Test isolation forbids live socket connections")
        # Coverage uses sqlite3 internally for its own .coverage metadata;
        # application fixtures use PostgreSQL, not SQLite.

    sys.addaudithook(audit)

    import psycopg2
    from psycopg2.extensions import parse_dsn
    original_connect = psycopg2.connect

    def connect(dsn=None, *args, **kwargs):
        params = parse_dsn(dsn or "")
        params.update({k: str(v) for k, v in kwargs.items()
                       if k not in {"connection_factory", "cursor_factory", "async_", "async"}})
        if (params.get("host") != "127.0.0.1"
                or params.get("port") != os.environ["GMAIL_TEST_PG_PORT"]
                or not params.get("dbname", "").startswith("gmail_test_")
                or params.get("user") != "gmail_test_runner"
                or params.get("service") or params.get("hostaddr")):
            raise RuntimeError("Refusing a PostgreSQL connection outside the disposable test cluster")
        return original_connect(dsn, *args, **kwargs)

    psycopg2.connect = connect
    sys._gmail_test_isolation = True
