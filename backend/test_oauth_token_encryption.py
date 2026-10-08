import importlib
import json

from cryptography.fernet import Fernet


def setup_database(monkeypatch, tmp_path):
    monkeypatch.setenv("FORCE_SQLITE", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("DB_ENCRYPTION_KEY_V2", Fernet.generate_key().decode())
    import encryption
    importlib.reload(encryption)
    import database
    database = importlib.reload(database)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "oauth.db")
    database.init_db()
    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "INSERT INTO users (gmail_address) VALUES (%s)", ("user@example.com",))
        conn.commit()
    finally:
        database._release_connection(conn)
    return database


def test_oauth_token_is_encrypted_at_rest_and_round_trips(monkeypatch, tmp_path):
    database = setup_database(monkeypatch, tmp_path)
    token_json = json.dumps({"token": "oauth-secret", "refresh_token": "refresh-secret"})
    database.save_user_token("user@example.com", token_json)

    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "SELECT token, token_key_version, token_encrypted_at FROM users WHERE gmail_address = %s", ("user@example.com",))
        row = cur.fetchone()
    finally:
        database._release_connection(conn)

    assert row["token"] != token_json
    assert "oauth-secret" not in row["token"]
    assert row["token"].startswith("2:")
    assert row["token_key_version"] == 2
    assert row["token_encrypted_at"] is not None
    assert database.get_user_token("user@example.com") == token_json


def test_corrupt_oauth_token_returns_none(monkeypatch, tmp_path):
    database = setup_database(monkeypatch, tmp_path)
    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "UPDATE users SET token = %s WHERE gmail_address = %s", ("v2:corrupt", "user@example.com"))
        conn.commit()
    finally:
        database._release_connection(conn)
    assert database.get_user_token("user@example.com") is None


def test_rotate_plaintext_tokens_migration(monkeypatch, tmp_path):
    database = setup_database(monkeypatch, tmp_path)
    token_json = '{"token":"legacy"}'
    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "UPDATE users SET token = %s WHERE gmail_address = %s", (token_json, "user@example.com"))
        conn.commit()
    finally:
        database._release_connection(conn)

    changed = database.rotate_encryption_keys(migrate_plaintext=True)
    assert changed == 1
    assert database.get_user_token("user@example.com") == token_json
