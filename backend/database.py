"""
database.py — PostgreSQL-only database module
Multi-user schema with 6 tables: users, custom_labels, scan_cursor,
analyzed_emails, url_cache, retry_queue.
All queries are parameterized to prevent SQL injection.
SQLite is intentionally unsupported for this application.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

MAX_RETRIES = 5

# Load the same local configuration used by the backend entrypoint before
# deciding which database backend is available.
load_dotenv(Path(__file__).parent / ".env", override=False)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

# PostgreSQL is mandatory for local and deployed application runs.
DATABASE_URL = os.getenv("DATABASE_URL")
FORCE_SQLITE = os.getenv("FORCE_SQLITE", "false").lower() == "true"
if FORCE_SQLITE:
    raise RuntimeError("SQLite is disabled; unset FORCE_SQLITE and configure DATABASE_URL for PostgreSQL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required; PostgreSQL-only mode refuses to start without it")
USE_POSTGRES = True

if USE_POSTGRES:
    import psycopg2
    from psycopg2 import pool as psycopg2_pool
    from psycopg2.extras import RealDictCursor
    _pg_pool = psycopg2_pool.ThreadedConnectionPool(
        minconn=2, maxconn=50, dsn=DATABASE_URL,
        cursor_factory=RealDictCursor
    )
    logger.info("[DB] Using Postgres (DATABASE_URL detected) with connection pool (2-50 connections)")
_PLACEHOLDER = "%s"


def _get_connection():
    """
    Get a database connection (from pool for Postgres, fresh for SQLite).
    Returns a connection with dict-like row access.
    """
    global _PLACEHOLDER
    if USE_POSTGRES:
        # Postgres connection from pool
        for attempt in range(5):
            try:
                conn = _pg_pool.getconn()
                _PLACEHOLDER = "%s"
                return conn
            except psycopg2_pool.PoolError:
                if attempt == 4:
                    raise
                time.sleep(0.1 * (2 ** attempt))
    else:
        # PostgreSQL required; SQLite fallback removed
        raise RuntimeError(
            "DATABASE_URL not configured. PostgreSQL is required. "
            "Set DATABASE_URL in backend/.env or .env"
        )


def _release_connection(conn, close=False):
    """
    Release a database connection (back to pool for Postgres, close for SQLite).
    """
    if USE_POSTGRES:
        _pg_pool.putconn(conn, close=close)
    else:
        conn.close()


def _execute(cursor, query, params=None):
    """Execute query with the correct placeholder for the current database backend."""
    if params is None:
        params = ()
    query = query.replace("%s", _PLACEHOLDER)
    cursor.execute(query, params)


def _column_exists(cursor, table: str, column: str) -> bool:
    """Check whether a column exists on a table (works on Postgres and SQLite)."""
    if USE_POSTGRES:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column),
        )
        return cursor.fetchone() is not None
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def init_db():
    """
    Initialize the PostgreSQL database.
    Creates all required tables in the required order if they don't already exist.
    Called at FastAPI startup.
    """
    conn = None
    initialization_failed = False
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Determine SQL syntax based on database type
        pk_syntax = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
        timestamp_default = "DEFAULT NOW()" if USE_POSTGRES else "DEFAULT CURRENT_TIMESTAMP"

        # TABLE 1: users
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS users (
                user_id {pk_syntax},
                gmail_address TEXT UNIQUE NOT NULL,
                access_token TEXT,
                token TEXT,
                delete_mode TEXT DEFAULT 'trash',
                created_at TIMESTAMP {timestamp_default}
            )
        """)

        # Migration: add delete_mode column if table already exists without it (SQLite only)
        if not USE_POSTGRES:
            if not _column_exists(cursor, "users", "delete_mode"):
                _execute(cursor, "ALTER TABLE users ADD COLUMN delete_mode TEXT DEFAULT 'trash'")
                logger.info("[DB] Migrated: added delete_mode column to users table")

        # Migration: add token column (DB-backed OAuth tokens; replaces file storage)
        if not _column_exists(cursor, "users", "token"):
            _execute(cursor, "ALTER TABLE users ADD COLUMN token TEXT")
            logger.info("[DB] Migrated: added token column to users table")

        # Migration: add OAuth token encryption metadata.
        if not _column_exists(cursor, "users", "token_key_version"):
            _execute(cursor, "ALTER TABLE users ADD COLUMN token_key_version INTEGER DEFAULT 1")
            logger.info("[DB] Migrated: added token_key_version column to users table")
        if not _column_exists(cursor, "users", "token_encrypted_at"):
            _execute(cursor, "ALTER TABLE users ADD COLUMN token_encrypted_at TIMESTAMP")
            logger.info("[DB] Migrated: added token_encrypted_at column to users table")

        # Migration: add per-user encrypted AI provider key columns (BYOK feature)
        for col in ("groq_api_key", "gemini_api_key", "cohere_api_key", "nvidia_api_key"):
            if not _column_exists(cursor, "users", col):
                _execute(cursor, f"ALTER TABLE users ADD COLUMN {col} TEXT")
                logger.info(f"[DB] Migrated: added {col} column to users table")

        # TABLE 2: custom_labels
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS custom_labels (
                label_id {pk_syntax},
                user_id INTEGER NOT NULL,
                label_name TEXT NOT NULL,
                bg_color TEXT DEFAULT '#3B82F6',
                text_color TEXT DEFAULT '#FFFFFF',
                created_at TIMESTAMP {timestamp_default},
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # TABLE 3: scan_cursor
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS scan_cursor (
                cursor_id {pk_syntax},
                user_id INTEGER NOT NULL UNIQUE,
                last_page_token TEXT,
                last_scan_at TIMESTAMP {timestamp_default},
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # TABLE 4: analyzed_emails
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS analyzed_emails (
                email_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                label_id INTEGER,
                scam_score INTEGER,
                scam_indicators TEXT DEFAULT '[]',
                is_quarantined INTEGER DEFAULT 0,
                snippet TEXT,
                sender TEXT,
                subject TEXT,
                status TEXT NOT NULL DEFAULT 'labeled',
                analyzed_at TIMESTAMP {timestamp_default},
                body TEXT,
                 applied_to_gmail INTEGER DEFAULT 0,
                 last_applied_label_id INTEGER DEFAULT NULL,
                 source TEXT DEFAULT 'ai',
                 ml_confidence REAL,
                 provider_used TEXT,
                 FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES custom_labels(label_id) ON DELETE RESTRICT
            )
        """)

        # TABLE 5: url_cache
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS url_cache (
                url_id {pk_syntax},
                email_id TEXT NOT NULL,
                url TEXT NOT NULL,
                is_safe INTEGER DEFAULT 1,
                threat_type TEXT,
                checked_at TIMESTAMP {timestamp_default},
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(email_id) ON DELETE CASCADE
            )
        """)

        # TABLE 6: retry_queue
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS retry_queue (
                retry_id {pk_syntax},
                email_id TEXT NOT NULL UNIQUE,
                retry_count INTEGER DEFAULT 0,
                last_attempted TIMESTAMP,
                error_reason TEXT,
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(email_id) ON DELETE CASCADE
            )
        """)

        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id {pk_syntax},
                email_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                error_message TEXT NOT NULL,
                final_retry_count INTEGER NOT NULL,
                moved_at TIMESTAMP {timestamp_default},
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(email_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        _execute(cursor, """
            CREATE INDEX IF NOT EXISTS idx_retry_queue_retry_count_last_attempted_email_id
            ON retry_queue(retry_count, last_attempted, email_id)
        """)

        # Migration: add applied_to_gmail and last_applied_label_id columns if not exist (Phase 38)
        if USE_POSTGRES:
            # Postgres: use information_schema to check column existence
            _execute(cursor,"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s ORDER BY ordinal_position
            """, ('analyzed_emails',))
            columns = [row['column_name'] for row in cursor.fetchall()]
        else:
            # SQLite: use PRAGMA table_info
            _execute(cursor,"PRAGMA table_info(analyzed_emails)")
            columns = [row[1] for row in cursor.fetchall()]

        if 'applied_to_gmail' not in columns:
            logger.info("[DB MIGRATION] Adding applied_to_gmail column to analyzed_emails...")
            _execute(cursor,"""
                ALTER TABLE analyzed_emails
                ADD COLUMN applied_to_gmail INTEGER DEFAULT 0
            """)
            conn.commit()
            logger.info("[DB MIGRATION] applied_to_gmail column added successfully.")

        if 'last_applied_label_id' not in columns:
            logger.info("[DB MIGRATION] Adding last_applied_label_id column to analyzed_emails...")
            _execute(cursor,"""
                ALTER TABLE analyzed_emails
                ADD COLUMN last_applied_label_id INTEGER DEFAULT NULL
            """)
            conn.commit()
            logger.info("[DB MIGRATION] last_applied_label_id column added successfully.")

        for column, definition in (
            ("source", "TEXT DEFAULT 'ai'"),
            ("ml_confidence", "REAL"),
            ("provider_used", "TEXT"),
            ("reasoning", "TEXT"),
            ("routing_decision", "TEXT"),
            ("v2_score", "REAL"),
            ("analysis_status", "TEXT"),
            ("category_status", "TEXT"),
            ("url_scan_status", "TEXT"),
            ("urls_total", "INTEGER"),
            ("urls_checked", "INTEGER"),
            ("received_at", "TEXT"),
            ("user_decision", "TEXT"),
            ("gmail_sync_state", "TEXT DEFAULT 'not_required'"),
            ("gmail_sync_error", "TEXT"),
            ("gmail_sync_attempts", "INTEGER DEFAULT 0"),
            ("last_synced_at", "TIMESTAMP"),
            ("attachment_risk", "TEXT DEFAULT 'clean'"),  # Phase 5: clean, suspicious, malicious
            ("attachment_details", "TEXT"),  # Phase 5: JSON with scan results
        ):
            if column not in columns:
                _execute(cursor, f"ALTER TABLE analyzed_emails ADD COLUMN {column} {definition}")
                conn.commit()

        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS ml_models (
                model_id {pk_syntax}, version TEXT NOT NULL, trained_at TIMESTAMP {timestamp_default},
                training_row_count INTEGER NOT NULL, validation_precision REAL,
                validation_recall REAL, calibration_error REAL, model_blob {("BYTEA" if USE_POSTGRES else "BLOB")},
                model_hash TEXT,
                is_active INTEGER DEFAULT 0
            )
        """)
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS ml_disagreements (
                disagreement_id {pk_syntax}, email_id TEXT NOT NULL, ml_prediction TEXT,
                ml_confidence REAL, ai_prediction TEXT, agreed INTEGER NOT NULL DEFAULT 0,
                logged_at TIMESTAMP {timestamp_default},
                FOREIGN KEY (email_id) REFERENCES analyzed_emails(email_id) ON DELETE CASCADE
            )
        """)

        # TABLE 8: audit_log (Phase 6 - Security & Compliance)
        _execute(cursor, f"""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id {pk_syntax},
                user_id INTEGER,
                timestamp TIMESTAMP {timestamp_default},
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                metadata TEXT,
                severity TEXT DEFAULT 'info',
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Phase 6: Create indexes for audit_log performance
        _execute(cursor, "CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, timestamp DESC)")
        _execute(cursor, "CREATE INDEX IF NOT EXISTS idx_audit_action_time ON audit_log(action, timestamp DESC)")
        _execute(cursor, "CREATE INDEX IF NOT EXISTS idx_audit_severity_time ON audit_log(severity, timestamp DESC)")

        conn.commit()
        logger.info("[DB] Database initialized successfully")
    except Exception:
        initialization_failed = True
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            logger.warning("[DB] Database initialization rollback failed")
        raise
    finally:
        if conn is not None:
            try:
                _release_connection(conn, close=initialization_failed)
            except Exception:
                if not initialization_failed:
                    raise
                logger.warning("[DB] Failed to discard connection after initialization failure")


# ---------- SEED DEFAULT LABELS ----------

def seed_default_labels(user_id: int):
    """
    Seed 8 default labels for a user if they have zero labels.
    Called after a user logs in for the first time.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        _execute(cursor, "SELECT COUNT(*) as count FROM custom_labels WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        count = result['count'] if isinstance(result, dict) else result[0]

        if count == 0:
            defaults = [
                (user_id, "Work", "#1D4ED8", "#FFFFFF"),
                (user_id, "Finance", "#15803D", "#FFFFFF"),
                (user_id, "Newsletter", "#7C3AED", "#FFFFFF"),
                (user_id, "Promotional", "#B45309", "#FFFFFF"),
                (user_id, "Personal", "#0369A1", "#FFFFFF"),
                (user_id, "Spam", "#DC2626", "#FFFFFF"),
                (user_id, "Social", "#0891B2", "#FFFFFF"),
                (user_id, "Receipt", "#065F46", "#FFFFFF"),
            ]
            query = "INSERT INTO custom_labels (user_id, label_name, bg_color, text_color) VALUES (%s, %s, %s, %s)".replace("%s", _PLACEHOLDER)
            for default in defaults:
                _execute(cursor, query, default)
            conn.commit()
            logger.info(f"[DB] Seeded 8 default labels for user_id={user_id}")
        else:
            logger.info(f"[DB] User {user_id} already has {count} labels, skipping seed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- USER MANAGEMENT ----------

def upsert_user(gmail_address: str, access_token: str) -> int:
    """Insert or update user, return user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        _execute(cursor,
            """
            INSERT INTO users (gmail_address, access_token)
            VALUES (%s, %s)
            ON CONFLICT(gmail_address) DO UPDATE SET access_token = excluded.access_token
            """,
            (gmail_address, access_token),
        )
        conn.commit()

        _execute(cursor,"SELECT user_id FROM users WHERE gmail_address = %s", (gmail_address,))
        user_id = cursor.fetchone()['user_id']

        logger.info(f"[DB] Upserted user '{gmail_address}' -> user_id={user_id}")
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_user_id(gmail_address: str) -> int:
    """Return user_id for given gmail_address."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,"SELECT user_id FROM users WHERE gmail_address = %s", (gmail_address,))
        row = cursor.fetchone()

        if row is None:
            raise ValueError(f"User not found: {gmail_address}")
        return row['user_id']
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- OAUTH TOKEN STORAGE (DB-BACKED, per-user) ----------

def save_user_token(user_email: str, token_json: str) -> None:
    """
    Persist a user's serialized OAuth token (credentials.to_json()) to the DB,
    keyed by gmail_address. Replaces the old shared file-based storage.
    """
    from encryption import encrypt_key, get_current_version

    encrypted_token = encrypt_key(token_json)
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            UPDATE users
            SET token = %s, token_key_version = %s, token_encrypted_at = CURRENT_TIMESTAMP
            WHERE gmail_address = %s
        """, (encrypted_token, get_current_version(), user_email))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_user_token(user_email: str) -> str | None:
    """Return decrypted OAuth token JSON, or None if absent/invalid."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, "SELECT token FROM users WHERE gmail_address = %s", (user_email,))
        row = cursor.fetchone()
        if not row or not row['token']:
            return None

        from encryption import decrypt_key
        stored_token = row['token']
        decrypted = decrypt_key(stored_token)
        if decrypted is not None:
            return decrypted

        # Legacy plaintext JSON remains readable so the migration script can
        # convert it without interrupting existing OAuth sessions.
        if stored_token.lstrip().startswith("{"):
            return stored_token
        return None
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def delete_user_token(user_email: str) -> None:
    """Clear a user's stored OAuth token (used on logout)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            UPDATE users
            SET token = NULL, token_key_version = 1, token_encrypted_at = NULL
            WHERE gmail_address = %s
        """, (user_email,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def rotate_encryption_keys(migrate_plaintext: bool = False) -> int:
    """Re-encrypt stored OAuth tokens with the active key and return row count."""
    from encryption import decrypt_key, encrypt_key, get_current_version

    conn = _get_connection()
    changed = 0
    try:
        cursor = conn.cursor()
        _execute(cursor, "SELECT user_id, token FROM users WHERE token IS NOT NULL")
        rows = cursor.fetchall()
        for row in rows:
            stored_token = row["token"]
            plaintext = decrypt_key(stored_token)
            if plaintext is None and migrate_plaintext and stored_token.lstrip().startswith("{"):
                plaintext = stored_token
            if plaintext is None:
                continue
            _execute(cursor, """
                UPDATE users
                SET token = %s, token_key_version = %s, token_encrypted_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (encrypt_key(plaintext), get_current_version(), row["user_id"]))
            changed += 1
        conn.commit()
        return changed
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_user_email_by_id(user_id: int) -> str | None:
    """Return the gmail_address for a given user_id, or None."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, "SELECT gmail_address FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row['gmail_address'] if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- PER-USER AI PROVIDER KEYS (BYOK) ----------

# Valid provider names for the BYOK feature (the 4 fixed cascade providers).
AI_PROVIDERS = ("groq", "gemini", "cohere", "nvidia")

# Maps a provider name to the column that stores its (encrypted) key.
_AI_KEY_COLUMNS = {
    "groq": "groq_api_key",
    "gemini": "gemini_api_key",
    "cohere": "cohere_api_key",
    "nvidia": "nvidia_api_key",
}


def save_user_ai_key(user_id: int, provider: str, encrypted_key: str) -> None:
    """
    Store an encrypted API key for a user + provider.
    `encrypted_key` must already be encrypted (see backend/encryption.py).
    Raises ValueError if provider is not one of the supported providers.
    """
    if provider not in AI_PROVIDERS:
        raise ValueError(f"Unknown AI provider: {provider}")
    column = _AI_KEY_COLUMNS[provider]
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, f"UPDATE users SET {column} = %s WHERE user_id = %s", (encrypted_key, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_user_ai_keys(user_id: int) -> dict:
    """
    Return the (encrypted) API keys for a user as a dict keyed by provider name:
        {"groq": "...", "gemini": None, "cohere": "...", "nvidia": None}
    Values are the raw stored (encrypted) strings; callers must decrypt before use.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(
            cursor,
            "SELECT groq_api_key, gemini_api_key, cohere_api_key, nvidia_api_key "
            "FROM users WHERE user_id = %s",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {p: None for p in AI_PROVIDERS}
        return {
            "groq": row["groq_api_key"],
            "gemini": row["gemini_api_key"],
            "cohere": row["cohere_api_key"],
            "nvidia": row["nvidia_api_key"],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def delete_user_ai_key(user_id: int, provider: str) -> None:
    """
    Remove a user's stored API key for a single provider (sets the column to NULL).
    Raises ValueError if provider is not one of the supported providers.
    """
    if provider not in AI_PROVIDERS:
        raise ValueError(f"Unknown AI provider: {provider}")
    column = _AI_KEY_COLUMNS[provider]
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, f"UPDATE users SET {column} = NULL WHERE user_id = %s", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- LABEL MANAGEMENT ----------

def get_labels(user_id: int) -> list[dict]:
    """Return list of {label_id, label_name, bg_color, text_color} for a user."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "SELECT label_id, label_name, bg_color, text_color FROM custom_labels WHERE user_id = %s ORDER BY created_at ASC",
            (user_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_label_id_by_name(user_id: int, label_name: str) -> int:
    """
    Return label_id for given label_name and user_id.
    If exact name not found, try case-insensitive match, then fall back
    to the first available custom label for that user.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # 1. Exact match
        _execute(cursor,
            "SELECT label_id FROM custom_labels WHERE user_id = %s AND label_name = %s",
            (user_id, label_name),
        )
        row = cursor.fetchone()
        if row:
            return row['label_id']

        # 2. Case-insensitive match (AI may return "work" instead of "Work")
        _execute(cursor,
            "SELECT label_id FROM custom_labels WHERE user_id = %s AND LOWER(label_name) = LOWER(%s)",
            (user_id, label_name),
        )
        ci_row = cursor.fetchone()
        if ci_row:
            return ci_row['label_id']

        # 3. Fallback — first available label for this user
        _execute(cursor,
            "SELECT label_id, label_name FROM custom_labels WHERE user_id = %s ORDER BY label_id ASC LIMIT 1",
            (user_id,),
        )
        fallback = cursor.fetchone()

        if fallback:
            logger.info(f"[DB] Label '{label_name}' not found, falling back to '{fallback[1]}' (id={fallback[0]})")
            return fallback[0]

        raise ValueError(f"No labels found for user_id={user_id}. Create at least one label.")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def add_label(user_id: int, label_name: str, bg_color: str, text_color: str) -> int:
    """Insert new label, return label_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "INSERT INTO custom_labels (user_id, label_name, bg_color, text_color) VALUES (%s, %s, %s, %s)",
            (user_id, label_name, bg_color, text_color),
        )
        conn.commit()
        label_id = cursor.lastrowid
        logger.info(f"[DB] Added label '{label_name}' (id={label_id}) for user_id={user_id}")
        return label_id
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def delete_label(label_id: int, user_id: int) -> None:
    """Delete label only if user_id matches."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "DELETE FROM custom_labels WHERE label_id = %s AND user_id = %s",
            (label_id, user_id),
        )
        conn.commit()
        logger.info(f"[DB] Deleted label_id={label_id} for user_id={user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- ANALYZED EMAILS ----------

_UNSET = object()
_ANALYSIS_FIELDS = ('reasoning', 'routing_decision', 'v2_score', 'analysis_status', 'category_status', 'url_scan_status', 'urls_total', 'urls_checked', 'received_at', 'user_decision', 'attachment_risk', 'attachment_details')

def save_analyzed_email(email_id: str, user_id: int, label_id: int, scam_score: int,
                         scam_indicators: str, is_quarantined: int,
                         snippet: str, sender: str, subject: str,
                         status: str = 'labeled', body: str = None,
                         source: str = 'ai', ml_confidence: float = None,
                         provider_used: str = None, *,
                         reasoning=_UNSET, routing_decision=_UNSET, v2_score=_UNSET, analysis_status=_UNSET, category_status=_UNSET, url_scan_status=_UNSET, urls_total=_UNSET, urls_checked=_UNSET, received_at=_UNSET, user_decision=_UNSET, attachment_risk=_UNSET, attachment_details=_UNSET) -> None:
    """Upsert within one account; omitted metadata is preserved, None clears it."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Composite (user_id, email_id) migration is deferred: url_cache,
        # retry_queue and ml_disagreements reference the global email_id PK.
        # Rebuilding those tables/FKs is not an additive migration. Fail closed
        # atomically on ownership conflicts until that coordinated migration.
        fields = ("email_id", "user_id", "label_id", "scam_score", "scam_indicators",
                  "is_quarantined", "snippet", "sender", "subject", "status", "body",
                  "source", "ml_confidence", "provider_used")
        values = (email_id, user_id, label_id, scam_score, scam_indicators,
                  is_quarantined, snippet, sender, subject, status, body,
                  source, ml_confidence, provider_used)
        metadata = dict(zip(_ANALYSIS_FIELDS, (reasoning, routing_decision, v2_score,
            analysis_status, category_status, url_scan_status, urls_total, urls_checked,
            received_at, user_decision, attachment_risk, attachment_details)))
        metadata = {key: value for key, value in metadata.items() if value is not _UNSET}
        fields += tuple(metadata)
        values += tuple(metadata.values())
        assignments = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
        _execute(cursor, f"""
            INSERT INTO analyzed_emails ({', '.join(fields)})
            VALUES ({', '.join(['%s'] * len(fields))})
            ON CONFLICT (email_id) DO UPDATE SET {assignments}
            WHERE analyzed_emails.user_id = excluded.user_id
        """, values)
        if cursor.rowcount != 1:
            raise ValueError("Email ID belongs to a different account")

        conn.commit()
        logger.info(f"[DB] Saved email {email_id[:12]}... label_id={label_id}, scam_score={scam_score}, status={status}, source={source}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def update_analyzed_email(email_id: str, label_id: int, scam_score: int,
                          scam_indicators: str, is_quarantined: int, status: str = 'labeled',
                          source: str = 'ai', ml_confidence: float = None,
                          provider_used: str = None, *, user_id: int,
                         reasoning=_UNSET, routing_decision=_UNSET, v2_score=_UNSET, analysis_status=_UNSET, category_status=_UNSET, url_scan_status=_UNSET, urls_total=_UNSET, urls_checked=_UNSET, received_at=_UNSET, user_decision=_UNSET, attachment_risk=_UNSET, attachment_details=_UNSET) -> None:
    """
    Update an existing analyzed_emails row with AI results.
    Preserves the original analyzed_at timestamp and body.
    Used by label_only_pipeline via _analyze_one(update_mode=True).
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        values = dict(label_id=label_id, scam_score=scam_score,
            scam_indicators=scam_indicators, is_quarantined=is_quarantined,
            status=status, source=source, ml_confidence=ml_confidence, provider_used=provider_used)
        values.update({key: value for key, value in zip(_ANALYSIS_FIELDS,
            (reasoning, routing_decision, v2_score, analysis_status, category_status,
             url_scan_status, urls_total, urls_checked, received_at, user_decision,
             attachment_risk, attachment_details))
            if value is not _UNSET})
        assignments = ", ".join(f"{key} = %s" for key in values)
        _execute(cursor, f"UPDATE analyzed_emails SET {assignments} "
                 "WHERE email_id = %s AND user_id = %s",
                 (*values.values(), email_id, user_id))
        conn.commit()
        logger.info(f"[DB] Updated email {email_id[:12]}... to status={status}, label_id={label_id}, score={scam_score}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def update_email_label_id(email_id: str, label_id: int, *, user_id: int) -> None:
    """
    Update only the label_id for an email (manual label override).
    Does NOT touch scam_score, scam_indicators, or is_quarantined.
    Sets applied_to_gmail=0 (needs re-applying).
    Does NOT update last_applied_label_id (only _sync_label_to_gmail does that).
    
    Args:
        email_id: Gmail message ID
        label_id: New label ID to apply
        user_id: Owner user ID (ownership check)
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,"""
            UPDATE analyzed_emails
            SET label_id = %s, applied_to_gmail = 0
            WHERE email_id = %s AND user_id = %s
        """, (label_id, email_id, user_id))
        conn.commit()
        logger.info(f"[DB] Updated label_id for email {email_id[:12]}... to {label_id}, marked as pending (user_id={user_id})")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_emails_by_status(user_id: int, status: str, limit: int = None) -> list[dict]:
    """
    Return emails with a specific status, ordered by analyzed_at DESC (newest first).
    Used by label_only_pipeline to fetch status='fetched' rows.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        query = """SELECT * FROM analyzed_emails
                   WHERE user_id = %s AND status = %s
                   ORDER BY COALESCE(NULLIF(received_at, ''), CAST(analyzed_at AS TEXT)) DESC"""
        params = (user_id, status)
        if limit is not None:
            query += " LIMIT %s"
            params += (limit,)
        _execute(cursor, query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["id"] = row["email_id"]
            row["from"] = row["sender"] or ""
            for key in ("snippet", "sender", "subject", "body"):
                row[key] = row[key] or ""
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_emails_by_ids(user_id: int, email_ids: list[str]) -> list[dict]:
    """
    Return specific emails by their IDs (exact retry targets).
    Used by retry endpoint to fetch precise emails for re-analysis.
    
    Args:
        user_id: User ID (ownership check)
        email_ids: List of Gmail message IDs to fetch
    
    Returns:
        List of email dicts matching the provided IDs
    """
    if not email_ids:
        return []
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Build parameterized IN clause
        placeholders = ', '.join(['%s'] * len(email_ids))
        query = f"""SELECT * FROM analyzed_emails
                    WHERE user_id = %s AND email_id IN ({placeholders})
                    ORDER BY COALESCE(NULLIF(received_at, ''), CAST(analyzed_at AS TEXT)) DESC"""
        params = (user_id,) + tuple(email_ids)
        
        _execute(cursor, query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["id"] = row["email_id"]
            row["from"] = row["sender"] or ""
            for key in ("snippet", "sender", "subject", "body"):
                row[key] = row[key] or ""
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)



def is_already_analyzed(email_id: str, user_id: int) -> bool:
    """Return True if email_id exists in analyzed_emails for this user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "SELECT 1 FROM analyzed_emails WHERE email_id = %s AND user_id = %s",
            (email_id, user_id),
        )
        result = cursor.fetchone() is not None
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_analyzed_emails(user_id: int, limit: int = None) -> list[dict]:
    """
    Return all analyzed emails for user joined with custom_labels.
    Now includes retry_queue error_reason for failed emails.
    Each dict contains: email_id, label_name, bg_color, text_color,
    scam_score, scam_indicators, is_quarantined, snippet, sender, subject, analyzed_at, body,
    applied_to_gmail, last_applied_label_id, label_id, status, error_reason
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            """
            SELECT ae.*, cl.label_name, cl.bg_color, cl.text_color,
                   rq.error_reason, rq.retry_count
            FROM analyzed_emails ae
            LEFT JOIN custom_labels cl ON ae.label_id = cl.label_id
            LEFT JOIN retry_queue rq ON ae.email_id = rq.email_id
            WHERE ae.user_id = %s
            ORDER BY COALESCE(NULLIF(ae.received_at, ''), CAST(ae.analyzed_at AS TEXT)) DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- URL CACHE ----------

def save_url_result(email_id: str, url: str, is_safe: int, threat_type: str) -> None:
    """Insert one URL result, ignore if same email_id + url already exists."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Check for existing entry with same email_id + url
        _execute(cursor,
            "SELECT 1 FROM url_cache WHERE email_id = %s AND url = %s",
            (email_id, url),
        )
        if cursor.fetchone() is not None:
            return

        _execute(cursor,
            "INSERT INTO url_cache (email_id, url, is_safe, threat_type) VALUES (%s, %s, %s, %s)",
            (email_id, url, is_safe, threat_type),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_cached_url(url: str) -> dict | None:
    """
    Return most recent url_cache row for this url, or None.
    Only return if checked_at is within last 24 hours.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "SELECT url, is_safe, threat_type, checked_at FROM url_cache WHERE url = %s ORDER BY checked_at DESC LIMIT 1",
            (url,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        row_dict = dict(row)

        # Check if cache is less than 24 hours old
        try:
            checked_at = datetime.fromisoformat(row_dict["checked_at"])
            if datetime.now() - checked_at > timedelta(hours=24):
                return None  # Cache expired
        except (ValueError, TypeError):
            return None

        return {
            "url": row_dict["url"],
            "is_safe": row_dict["is_safe"],
            "threat_type": row_dict["threat_type"],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- RETRY QUEUE ----------

def add_to_retry_queue(email_id: str, user_id: int, error_reason: str) -> None:
    """
    Insert into retry_queue, update retry_count if email_id already exists for this user.
    Do not insert if retry_count >= 3.
    
    Args:
        email_id: Gmail message ID
        user_id: Owner user ID (ownership check)
        error_reason: Error description for debugging
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Check if already in queue for this user
        _execute(cursor,"""
            SELECT rq.retry_count FROM retry_queue rq
            JOIN analyzed_emails ae ON rq.email_id = ae.email_id
            WHERE rq.email_id = %s AND ae.user_id = %s
        """, (email_id, user_id))
        row = cursor.fetchone()

        if row is not None:
            if row['retry_count'] >= MAX_RETRIES:
                _execute(cursor, """
                    INSERT INTO dead_letter_queue
                        (email_id, user_id, error_message, final_retry_count, moved_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT(email_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        error_message = excluded.error_message,
                        final_retry_count = excluded.final_retry_count,
                        moved_at = CURRENT_TIMESTAMP
                """, (email_id, user_id, error_reason, row['retry_count']))
                _execute(cursor, "DELETE FROM retry_queue WHERE email_id = %s", (email_id,))
                conn.commit()
                logger.info(f"[DB] Moved {email_id[:12]}... to dead-letter queue (user_id={user_id})")
                return
            _execute(cursor,
                """
                UPDATE retry_queue
                SET retry_count = retry_count + 1, last_attempted = CURRENT_TIMESTAMP, error_reason = %s
                WHERE email_id = %s
                """,
                (error_reason, email_id),
            )
        else:
            _execute(cursor,
                """
                INSERT INTO retry_queue (email_id, retry_count, last_attempted, error_reason)
                VALUES (%s, 0, CURRENT_TIMESTAMP, %s)
                """,
                (email_id, error_reason),
            )

        conn.commit()
        logger.info(f"[DB] Added/updated {email_id[:12]}... in retry queue (user_id={user_id})")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_pending_retry_queue(user_id: int, max_retries: int = 5) -> list[dict]:
    """Return retryable queue rows for a user below the retry limit."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            SELECT rq.retry_id, rq.email_id, rq.retry_count, rq.last_attempted, rq.error_reason,
                   ae.subject, ae.sender, ae.snippet, ae.body
            FROM retry_queue rq
            JOIN analyzed_emails ae ON rq.email_id = ae.email_id
            WHERE ae.user_id = %s AND rq.retry_count < %s
            ORDER BY rq.last_attempted ASC
        """, (user_id, max_retries))
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def mark_retry_attempt(email_id: str, user_id: int) -> None:
    """
    Increment retry count and record the current retry attempt.
    
    Args:
        email_id: Gmail message ID
        user_id: Owner user ID (ownership check)
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            UPDATE retry_queue
            SET retry_count = retry_count + 1, last_attempted = CURRENT_TIMESTAMP
            WHERE email_id = %s
            AND email_id IN (SELECT email_id FROM analyzed_emails WHERE user_id = %s)
        """, (email_id, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_retry_queue(user_id: int) -> list[dict]:
    """Return retry_queue rows joined with analyzed_emails for this user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            """
            SELECT rq.retry_id, rq.email_id, rq.retry_count, rq.last_attempted, rq.error_reason
            FROM retry_queue rq
            JOIN analyzed_emails ae ON rq.email_id = ae.email_id
            WHERE ae.user_id = %s
            ORDER BY rq.last_attempted ASC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def get_dead_letter_queue(user_id: int) -> list[dict]:
    """Return dead-lettered retry failures owned by the authenticated user."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            SELECT id, email_id, user_id, error_message, final_retry_count, moved_at
            FROM dead_letter_queue
            WHERE user_id = %s
            ORDER BY moved_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def remove_from_retry_queue(email_id: str) -> None:
    """Delete row from retry_queue by email_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,"DELETE FROM retry_queue WHERE email_id = %s", (email_id,))
        conn.commit()
        logger.info(f"[DB] Removed {email_id[:12]}... from retry queue")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- SCAN CURSOR ----------

def get_scan_cursor(user_id: int) -> str | None:
    """Return last_page_token for user_id, or None."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,"SELECT last_page_token FROM scan_cursor WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row['last_page_token'] if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def save_scan_cursor(user_id: int, last_page_token: str) -> None:
    """Upsert scan_cursor for user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            """
            INSERT INTO scan_cursor (user_id, last_page_token, last_scan_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET last_page_token = excluded.last_page_token,
                                               last_scan_at = CURRENT_TIMESTAMP
            """,
            (user_id, last_page_token),
        )
        conn.commit()
        logger.info(f"[DB] Saved scan cursor for user_id={user_id}: {last_page_token[:20] if last_page_token else 'None'}...")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def clear_scan_cursor(user_id: int) -> None:
    """Set last_page_token to NULL for user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "UPDATE scan_cursor SET last_page_token = NULL WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()
        logger.info(f"[DB] Cleared scan cursor for user_id={user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- ADMIN ----------

def reset_database(user_id: int) -> None:
    """
    Delete all analyzed_emails, url_cache, retry_queue, scan_cursor for this user_id.
    Do NOT delete users or custom_labels.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Delete in FK-safe order (children first)
        # url_cache and retry_queue reference analyzed_emails, so delete those first
        _execute(cursor,
            "DELETE FROM url_cache WHERE email_id IN (SELECT email_id FROM analyzed_emails WHERE user_id = %s)",
            (user_id,),
        )
        _execute(cursor,
            "DELETE FROM retry_queue WHERE email_id IN (SELECT email_id FROM analyzed_emails WHERE user_id = %s)",
            (user_id,),
        )
        _execute(cursor,"DELETE FROM analyzed_emails WHERE user_id = %s", (user_id,))
        _execute(cursor,"DELETE FROM scan_cursor WHERE user_id = %s", (user_id,))

        conn.commit()
        logger.info(f"[DB] Reset all analysis data for user_id={user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def mark_email_safe(email_id: str, user_id: int) -> None:
    """Set is_quarantined = 0 and scam_score = 0 for this email_id and user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "UPDATE analyzed_emails SET is_quarantined = 0, scam_score = 0 WHERE email_id = %s AND user_id = %s",
            (email_id, user_id),
        )
        conn.commit()
        logger.info(f"[DB] Marked email {email_id[:12]}... as safe for user_id={user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- DELETE MODE ----------

def get_delete_mode(user_id: int) -> str:
    """Return 'trash' or 'permanent' for the given user_id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,"SELECT delete_mode FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row['delete_mode'] if row and row['delete_mode'] else "trash"
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def set_delete_mode(user_id: int, mode: str) -> None:
    """Set delete_mode to 'trash' or 'permanent' for user_id."""
    if mode not in ("trash", "permanent"):
        raise ValueError(f"Invalid delete_mode: {mode}")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor,
            "UPDATE users SET delete_mode = %s WHERE user_id = %s",
            (mode, user_id),
        )
        conn.commit()
        logger.info(f"[DB] Set delete_mode={mode} for user_id={user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


# ---------- BULK OPERATIONS ----------

def bulk_mark_emails_safe(email_ids: list[str], user_id: int) -> int:
    """
    Mark multiple emails as safe (set is_quarantined=0, scam_score=0).
    Returns count of emails updated.
    
    Phase 2: Bulk Email Actions backend implementation.
    """
    if not email_ids:
        return 0
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Use parameterized query with IN clause
        placeholders = ','.join(['%s'] * len(email_ids))
        query = f"""
            UPDATE analyzed_emails 
            SET is_quarantined = 0, scam_score = 0, user_decision = 'user_safe'
            WHERE email_id IN ({placeholders}) AND user_id = %s
        """
        params = tuple(email_ids) + (user_id,)
        _execute(cursor, query, params)
        count = cursor.rowcount
        conn.commit()
        logger.info(f"[DB] Bulk marked {count} emails as safe for user_id={user_id}")
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def bulk_quarantine_emails(email_ids: list[str], user_id: int) -> int:
    """
    Quarantine multiple emails (set user_decision=user_quarantined, is_quarantined=1).
    Returns count of emails updated.
    
    Phase 2: Bulk Email Actions backend implementation.
    """
    if not email_ids:
        return 0
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(email_ids))
        query = f"""
            UPDATE analyzed_emails 
            SET user_decision = 'user_quarantined', is_quarantined = 1
            WHERE email_id IN ({placeholders}) AND user_id = %s
        """
        params = tuple(email_ids) + (user_id,)
        _execute(cursor, query, params)
        count = cursor.rowcount
        conn.commit()
        logger.info(f"[DB] Bulk quarantined {count} emails for user_id={user_id}")
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def bulk_update_email_labels(email_ids: list[str], label_id: int, user_id: int) -> int:
    """
    Update the label_id for multiple emails belonging to one user.
    Returns the number of emails updated.
    """
    if not email_ids:
        return 0
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(email_ids))
        query = f"""
            UPDATE analyzed_emails
            SET label_id = %s
            WHERE email_id IN ({placeholders}) AND user_id = %s
        """
        params = (label_id,) + tuple(email_ids) + (user_id,)
        _execute(cursor, query, params)
        count = cursor.rowcount
        conn.commit()
        logger.info(f"[DB] Bulk updated {count} emails to label_id={label_id} for user_id={user_id}")
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)
