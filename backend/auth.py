"""
auth.py — Google OAuth 2.0 Authentication Module (Restructured)
Handles the full OAuth flow: login URL generation, callback token exchange,
token persistence (token.json), automatic token refresh, and user upsert.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import json
import hashlib
import secrets
import time
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from database import (
    save_user_token,
    get_user_token,
    delete_user_token,
)

# Load environment variables from .env file
load_dotenv()

# ---------- CONFIGURATION ----------

# OAuth 2.0 scopes required for Gmail access
# H3: Minimized scope list - only essential permissions needed
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    # Gmail scopes - minimal set for core functionality:
    "https://www.googleapis.com/auth/gmail.readonly",     # Read emails
    "https://www.googleapis.com/auth/gmail.labels",       # Read/manage labels
    "https://www.googleapis.com/auth/gmail.modify",       # Modify emails (add/remove labels)
    # Removed:
    # - gmail.compose (not sending emails)
    # - gmail.settings.basic (not modifying settings)
    # - gmail.addons.* (no add-on functionality)
    # - drive.* (no Drive integration)
    # - mail.google.com (overly broad, replaced by specific scopes above)
]

# Google OAuth credentials from environment variables
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

# Build the client config dict (equivalent to a client_secret.json file)
CLIENT_CONFIG = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI],
    }
}


# ---------- TOKEN MANAGEMENT (DB-BACKED, per-user) ----------

def load_token(user_email: str) -> Credentials | None:
    """
    Load a user's saved OAuth token from the database (keyed by gmail_address).
    If the token is expired but has a refresh token, it is auto-refreshed and
    persisted back to the DB. Returns a Credentials object, or None.
    NOTE: user_email is required — there is no shared/legacy file fallback.
    """
    if not user_email:
        return None

    token_json = get_user_token(user_email)
    if not token_json:
        return None

    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            logger.info(f"[AUTH] Token expired for {user_email}, refreshing...")
            creds.refresh(Request())
            save_token(creds, user_email)
            logger.info(f"[AUTH] Token refreshed for {user_email}.")

        return creds if creds and creds.valid else None

    except Exception as e:
        logger.info(f"[AUTH] Error loading token for {user_email}: {e}")
        return None


def save_token(creds: Credentials, user_email: str) -> None:
    """
    Persist OAuth credentials to the database, keyed by the user's gmail_address.
    Replaces the old shared file-based token storage (security + ephemeral-FS fix).
    """
    if not user_email:
        raise ValueError("user_email is required to save a token (no shared file storage)")

    save_user_token(user_email, creds.to_json())
    logger.info(f"[AUTH] Token saved for user: {user_email}")


def delete_token(user_email: str = None) -> None:
    """
    Remove the saved token for a specific user (used on logout).
    No-op if user_email is not provided.
    """
    if not user_email:
        return
    delete_user_token(user_email)
    logger.info(f"[AUTH] Token deleted for {user_email}.")


def is_logged_in(user_email: str) -> bool:
    """
    Check if a valid (non-expired) token exists for the given user.
    user_email is required.
    """
    if not user_email:
        return False
    creds = load_token(user_email)
    return creds is not None and creds.valid


def _email_from_userinfo(creds: Credentials) -> str | None:
    """Best-effort: resolve the Gmail address from Google's userinfo endpoint."""
    if not creds or not creds.valid:
        return None
    try:
        import requests
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("email")
    except Exception as e:
        logger.info(f"[AUTH] Error fetching user email: {e}")
    return None


def get_user_email(user_email: str) -> str | None:
    """
    Confirm the authenticated user's email address by validating their token
    against the Google userinfo endpoint. Requires user_email to locate the token.
    """
    creds = load_token(user_email)
    if not creds or not creds.valid:
        return None
    return _email_from_userinfo(creds)


def migrate_legacy_tokens() -> None:
    """
    One-time, best-effort migration of old file-based tokens into the DB.
    Scans token.json (legacy single-user) and tokens/token_<email>.json, imports
    each into the DB, then deletes the files. Safe to call on every startup.
    """
    try:
        base = Path(__file__).parent

        # Legacy single-user token.json
        legacy = base / "token.json"
        if legacy.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(legacy), SCOPES)
                email = _email_from_userinfo(creds) if creds else None
                if email:
                    save_token(creds, user_email=email)
                legacy.unlink(missing_ok=True)
                logger.info(f"[AUTH MIGRATE] Imported legacy token.json for {email}.")
            except Exception as e:
                logger.info(f"[AUTH MIGRATE] Skipped legacy token.json: {e}")

        # Per-user tokens/token_<email>.json
        token_dir = base / "tokens"
        if token_dir.exists():
            for f in token_dir.glob("token_*.json"):
                try:
                    creds = Credentials.from_authorized_user_file(str(f), SCOPES)
                    email = _email_from_userinfo(creds) if creds else None
                    if email:
                        save_token(creds, user_email=email)
                    f.unlink(missing_ok=True)
                    logger.info(f"[AUTH MIGRATE] Imported {f.name} for {email}.")
                except Exception as e:
                    logger.info(f"[AUTH MIGRATE] Skipped {f.name}: {e}")
    except Exception as e:
        logger.info(f"[AUTH MIGRATE] Migration failed (non-fatal): {e}")


# ---------- OAUTH FLOW ----------

def _oauth_state_connection():
    from database import _get_connection, _execute
    conn = _get_connection()
    try:
        _execute(conn.cursor(), """CREATE TABLE IF NOT EXISTS oauth_login_states (
            state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
            verifier TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL
        )""")
        conn.commit()
        return conn
    except Exception:
        from database import _release_connection
        conn.rollback()
        _release_connection(conn)
        raise


def get_auth_url(session: dict) -> str:
    """Start a browser-bound, ten-minute, single-use OAuth + PKCE flow."""
    from database import _execute, _release_connection
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, autogenerate_code_verifier=True)
    flow.redirect_uri = REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="select_account consent",
    )
    browser = secrets.token_urlsafe(32)
    conn = _oauth_state_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, "DELETE FROM oauth_login_states WHERE expires_at < %s", (time.time(),))
        _execute(cursor, "INSERT INTO oauth_login_states (state_hash, browser_hash, verifier, expires_at) VALUES (%s, %s, %s, %s)",
                 (hashlib.sha256(state.encode()).hexdigest(), hashlib.sha256(browser.encode()).hexdigest(),
                  flow.code_verifier, time.time() + 600))
        conn.commit()
        session["oauth_browser"] = browser
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)
    return auth_url


def consume_oauth_state(state: str, session: dict) -> str | None:
    """Atomically consume state before any provider call (also across workers)."""
    from database import _execute, _release_connection
    browser = session.pop("oauth_browser", None)
    if not isinstance(state, str) or not state or len(state) > 1024 or not isinstance(browser, str):
        return None
    conn = _oauth_state_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """DELETE FROM oauth_login_states
            WHERE state_hash = %s AND browser_hash = %s AND expires_at >= %s
            RETURNING verifier""", (hashlib.sha256(state.encode()).hexdigest(),
                                    hashlib.sha256(browser.encode()).hexdigest(), time.time()))
        row = cursor.fetchone()
        conn.commit()
        return (row['verifier'] if hasattr(row, 'keys') else row[0]) if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


_SCOPE_ALIASES = {
    "email": "https://www.googleapis.com/auth/userinfo.email",
    "profile": "https://www.googleapis.com/auth/userinfo.profile",
}


def _scope_response_payload(response: object) -> dict:
    """Decode a token response without weakening oauthlib's own parser."""
    try:
        payload = response.json()
    except (AttributeError, ValueError):
        from urllib.parse import parse_qs

        try:
            values = parse_qs(response.text, keep_blank_values=True, strict_parsing=True)
        except (AttributeError, ValueError) as exc:
            raise ValueError("Malformed OAuth token response") from exc
        payload = {key: items[-1] for key, items in values.items()}

    if not isinstance(payload, dict):
        raise ValueError("Malformed OAuth token response")
    return payload


def _scope_values(raw_scope: object) -> list[str]:
    """Validate the RFC 6749 space-delimited scope response form."""
    if not isinstance(raw_scope, str) or not raw_scope:
        raise ValueError("Malformed OAuth scope response")
    if raw_scope != raw_scope.strip():
        raise ValueError("Malformed OAuth scope response")

    values = raw_scope.split(" ")
    if (any(not value for value in values)
            or any(any(character.isspace() for character in value) for value in values)
            or any(
                any(
                    not (
                        ord(character) == 0x21
                        or 0x23 <= ord(character) <= 0x5B
                        or 0x5D <= ord(character) <= 0x7E
                    )
                    for character in value
                )
                for value in values
            )):
        raise ValueError("Malformed OAuth scope response")
    return values


def _scope_validation_hook(session, required_scopes):
    """Validate required grants and align oauthlib with Google's actual grant."""
    required = {_SCOPE_ALIASES.get(scope, scope) for scope in required_scopes}

    def validate(response):
        payload = _scope_response_payload(response)
        if "scope" not in payload:
            return response

        granted = _scope_values(payload["scope"])
        normalized_granted = list(dict.fromkeys(granted))
        normalized_granted_set = {
            _SCOPE_ALIASES.get(scope, scope) for scope in normalized_granted
        }
        missing = sorted(required - normalized_granted_set)
        if missing:
            raise ValueError(
                "OAuth token response is missing required scope(s): "
                + ", ".join(missing)
            )

        # Normalize duplicate tokens before oauthlib constructs Credentials so
        # the persisted grant reflects the canonical provider response.
        if normalized_granted != granted and hasattr(response, "_content"):
            payload["scope"] = " ".join(normalized_granted)
            content_type = response.headers.get("Content-Type", "").lower()
            if "json" in content_type:
                response._content = json.dumps(payload).encode("utf-8")
            else:
                from urllib.parse import urlencode
                response._content = urlencode(payload).encode("utf-8")
            response.encoding = "utf-8"

        # oauthlib 3.3.1 raises Warning for a scope superset. Updating only
        # this OAuth2Session keeps parsing strict while retaining the provider's
        # actual grant in session.token and google Credentials.granted_scopes.
        session.scope = normalized_granted
        return response

    return validate


def _install_scope_validation_hook(flow):
    flow.oauth2session.register_compliance_hook(
        "access_token_response",
        _scope_validation_hook(flow.oauth2session, SCOPES),
    )


def handle_callback(authorization_code: str, code_verifier: str | None = None) -> dict:
    """
    Exchange the authorization code for tokens.
    After token exchange:
      1. Extract Gmail address from Google userinfo endpoint
      2. Save token for THIS SPECIFIC USER (multi-user support)
      3. Call upsert_user(gmail_address, access_token) to get user_id
      4. Call seed_default_labels(user_id)
      5. Return user_id and gmail_address for session storage
    """
    from database import upsert_user, seed_default_labels

    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI

    # Validate the required scopes in a per-session response hook before
    # userinfo lookup or any database/token persistence can occur.
    _install_scope_validation_hook(flow)
    flow.fetch_token(
        code=authorization_code,
        code_verifier=code_verifier,
        include_client_id=True,
    )
    creds = flow.credentials

    # Extract Gmail address from Google userinfo endpoint FIRST
    import requests
    gmail_address = None
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            gmail_address = resp.json().get("email")
    except Exception as e:
        logger.info(f"[AUTH] Error fetching user email during callback: {e}")

    if not gmail_address:
        logger.info("[AUTH] WARNING: Could not retrieve Gmail address from userinfo endpoint.")
        return {
            "success": False,
            "message": "Could not retrieve Gmail address.",
        }

    # Create the row before save_user_token's UPDATE, including on first login.
    access_token = creds.token
    user_id = upsert_user(gmail_address, access_token)
    save_token(creds, user_email=gmail_address)

    # Seed default labels if this user has none
    seed_default_labels(user_id)

    logger.info(f"[AUTH] OAuth callback successful. user_id={user_id}, email={gmail_address}")

    return {
        "success": True,
        "message": "Authentication successful",
        "user_id": user_id,
        "gmail_address": gmail_address,
    }


def get_credentials(user_email: str = None) -> Credentials | None:
    """
    Get valid credentials for making Gmail API calls for a specific user.
    user_email is required to load that user's token from the database.
    Returns None if the user is not logged in.
    """
    return load_token(user_email)
