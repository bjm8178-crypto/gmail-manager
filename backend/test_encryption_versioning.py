import importlib

import pytest
from cryptography.fernet import Fernet


def load_encryption(monkeypatch):
    key_v1 = Fernet.generate_key().decode()
    key_v2 = Fernet.generate_key().decode()
    monkeypatch.setenv("DB_ENCRYPTION_KEY", key_v1)
    monkeypatch.setenv("DB_ENCRYPTION_KEY_V2", key_v2)
    monkeypatch.setenv("FORCE_SQLITE", "true")
    import encryption
    return importlib.reload(encryption), key_v1, key_v2


def test_encrypt_tags_current_key_version(monkeypatch):
    encryption, _, _ = load_encryption(monkeypatch)
    ciphertext = encryption.encrypt_key("secret")
    assert ciphertext.startswith("2:")
    assert encryption.decrypt_key(ciphertext) == "secret"
    assert encryption.get_current_version() == 2


def test_decrypts_old_and_legacy_v1_ciphertext(monkeypatch):
    encryption, key_v1, _ = load_encryption(monkeypatch)
    v1 = Fernet(key_v1.encode()).encrypt(b"old-secret").decode()
    assert encryption.decrypt_key(f"v1:{v1}") == "old-secret"
    assert encryption.decrypt_key(v1) == "old-secret"


def test_unknown_or_corrupt_ciphertext_returns_none(monkeypatch):
    encryption, _, _ = load_encryption(monkeypatch)
    assert encryption.decrypt_key("v99:abc") is None
    assert encryption.decrypt_key("v2:not-valid") is None


def test_rotate_encryption_keys_reencrypts_tokens(monkeypatch, tmp_path):
    encryption, key_v1, key_v2 = load_encryption(monkeypatch)
    import database
    database = importlib.reload(database)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rotate.db")
    database.init_db()
    database._execute
    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "INSERT INTO users (gmail_address, token) VALUES (%s, %s)", ("old@example.com", Fernet(key_v1.encode()).encrypt(b'{\"token\":\"old\"}').decode()))
        conn.commit()
    finally:
        database._release_connection(conn)

    changed = database.rotate_encryption_keys()
    assert changed == 1
    conn = database._get_connection()
    try:
        cur = conn.cursor()
        database._execute(cur, "SELECT token, token_key_version FROM users WHERE gmail_address = %s", ("old@example.com",))
        row = cur.fetchone()
    finally:
        database._release_connection(conn)
    assert row["token"].startswith("2:")
    assert row["token_key_version"] == 2
    assert encryption.decrypt_key(row["token"]) == '{"token":"old"}'
