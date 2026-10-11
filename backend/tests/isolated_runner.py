"""Run the unfiltered suite in a source-only copy and disposable PostgreSQL.

Usage: python backend/tests/isolated_runner.py --pg-bin <PostgreSQL/bin>
Requires the application requirements plus pytest, pytest-asyncio, pytest-cov,
and trio in this interpreter. Never loads .env or copies databases/models/logs.
The actual pytest exit status is returned; coverage options are left untouched.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        parser.error("Use the dedicated Python 3.11 test virtual environment")
    repo = Path(__file__).resolve().parents[2]
    args.scratch.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="gmail-isolated-", dir=args.scratch))
    source = run / "source"
    backend = source / "backend"
    backend.mkdir(parents=True)
    names = subprocess.check_output(["git", "ls-files", "backend"], cwd=repo, text=True).splitlines()
    names += [str(p.relative_to(repo)).replace("\\", "/") for p in (repo / "backend/tests").glob("*.py")]
    names += [".env.example", ".coveragerc"]
    copied = []
    for name in sorted(set(names)):
        path = repo / name
        # Allow source/config only; never touch serialized models or live data.
        if (not path.is_file() or path.is_symlink()
                or any(part in {"logs", "models", "tokens", "venv", ".venv", "__pycache__"} for part in path.parts)
                or not (path.suffix in {".py", ".sql", ".ini", ".txt"}
                        or path.name in {".env.example", ".coveragerc"})):
            continue
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append(name)
    (source / ".isolated-test-sandbox").touch()
    shutil.copyfile(repo / "backend/tests/isolation_bootstrap.py", backend / "sitecustomize.py")
    (run / "source-manifest.json").write_text(json.dumps(copied, indent=2))

    # OS plumbing only: no ambient provider, PostgreSQL, OAuth, proxy, or Python settings.
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update({
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), str(args.pg_bin),
                                  str(Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32")]),
        "TEMP": str(run), "TMP": str(run), "TMPDIR": str(run),
        "HOME": str(run), "USERPROFILE": str(run),
        "APPDATA": str(run / "appdata"), "LOCALAPPDATA": str(run / "localappdata"),
        "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
    })
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    suffix = ".exe" if os.name == "nt" else ""
    def pg(name, *argv):
        return subprocess.run([str(args.pg_bin / (name + suffix)), *map(str, argv)],
                              env=env, cwd=run, check=True, timeout=120)

    started = False
    result = {"pytest_exit": None, "sandbox": str(source), "postgres_stopped": False}
    try:
        pg("initdb", "-D", run / "pgdata", "-U", "gmail_hygiene_admin",
           "--auth=trust", "--encoding=UTF8", "--locale=C")
        pg("pg_ctl", "-D", run / "pgdata", "-l", run / "postgres.log",
           "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
        started = True
        pg("psql", "-h", "127.0.0.1", "-p", port, "-U", "gmail_hygiene_admin",
           "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
           "CREATE ROLE gmail_test_runner LOGIN CREATEDB NOSUPERUSER;")
        pg("createdb", "-h", "127.0.0.1", "-p", port, "-U", "gmail_hygiene_admin",
           "-O", "gmail_test_runner", "gmail_test_suite")
        env.update({
            "ISOLATED_TESTS": "1",
            "GMAIL_TEST_SANDBOX": str(source), "GMAIL_TEST_PG_PORT": str(port),
            "PYTHONPATH": str(backend), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "DATABASE_URL": f"postgresql://gmail_test_runner@127.0.0.1:{port}/gmail_test_suite",
            "FORCE_SQLITE": "false", "RUN_INTEGRATION": "1",
            "DB_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            "SESSION_SECRET_KEY": secrets.token_hex(32), "JWT_SECRET_KEY": secrets.token_hex(32),
            "GOOGLE_CLIENT_ID": "isolated-test.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "isolated-test-not-a-real-secret",
            "FRONTEND_URL": "http://localhost:5173",
        })
        # Safety checks are real failures, not skips or synthetic test results.
        probe = subprocess.run([sys.executable, "-c",
            "import sys; assert getattr(sys, '_gmail_test_isolation', False); "
            "import database; database.init_db(); database._pg_pool.closeall()"],
            cwd=backend, env=env, timeout=120)
        if probe.returncode:
            raise RuntimeError("Isolated database initialization failed before pytest")
        command = [sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin",
                   "-p", "pytest_cov.plugin", "-p", "anyio.pytest_plugin"]
        print("UNFILTERED PYTEST:", command, flush=True)
        with (run / "pytest.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=backend, env=env,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=600)
        result["pytest_exit"] = completed.returncode
        print("PYTEST_EXIT:", completed.returncode, flush=True)
        print("PYTEST_LOG:", run / "pytest.log", flush=True)
        # Print last 40 lines of pytest output for verification
        log_path = run / "pytest.log"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            print("\n=== LAST 40 LINES OF PYTEST OUTPUT ===", flush=True)
            for line in lines[-40:]:
                print(line, flush=True)
        return completed.returncode
    finally:
        if started:
            pg("pg_ctl", "-D", run / "pgdata", "-m", "immediate", "-w", "stop")
            result["postgres_stopped"] = True
        (run / "result.json").write_text(json.dumps(result, indent=2))
        print("RESULT:", run / "result.json", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
