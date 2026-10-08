"""
encryption.py — Symmetric encryption for per-user API keys at rest.

Uses the `cryptography` library's Fernet (AES-128 in CBC mode with HMAC).
The key is read from the required DB_ENCRYPTION_KEY environment variable, which
must be provided (e.g. in the Railway dashboard). If it is missing the app
refuses to start, mirroring the existing SESSION_SECRET_KEY / JWT_SECRET_KEY
fail-fast pattern.

IMPORTANT: decrypted keys are never logged or printed.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
from cryptography.fernet import Fernet, InvalidToken

# Fail fast if the encryption key is not configured.
_DB_ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY")
if not _DB_ENCRYPTION_KEY:
    raise RuntimeError(
        "DB_ENCRYPTION_KEY env var is required to encrypt/decrypt stored API keys. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\""
    )

# Support for key rotation: ENCRYPTION_KEYS maps version to Fernet instances.
ENCRYPTION_KEYS = {
    1: Fernet(_DB_ENCRYPTION_KEY.encode() if isinstance(_DB_ENCRYPTION_KEY, str) else _DB_ENCRYPTION_KEY)
}

# Add V2 key if configured (for rotation)
_DB_ENCRYPTION_KEY_V2 = os.getenv("DB_ENCRYPTION_KEY_V2")
if _DB_ENCRYPTION_KEY_V2:
    ENCRYPTION_KEYS[2] = Fernet(_DB_ENCRYPTION_KEY_V2.encode() if isinstance(_DB_ENCRYPTION_KEY_V2, str) else _DB_ENCRYPTION_KEY_V2)
    logger.info("[ENCRYPTION] V2 key loaded - rotation enabled")

_ENCRYPTION_KEYS = ENCRYPTION_KEYS

# Current active version for new encryptions (always use highest version)
_CURRENT_VERSION = max(_ENCRYPTION_KEYS.keys())
_fernet = _ENCRYPTION_KEYS[_CURRENT_VERSION]  # Backwards compatibility

logger.info(f"[ENCRYPTION] Active key version: {_CURRENT_VERSION}")


def encrypt_key(plain: str) -> str:
    """
    Encrypt a plaintext API key and return versioned ciphertext.
    Format: "{version}:{base64_ciphertext}"
    Never logs or prints the plaintext or ciphertext.
    """
    if plain is None:
        return None
    token = _fernet.encrypt(plain.encode("utf-8"))
    # Prefix with version for rotation support
    return f"{_CURRENT_VERSION}:{token.decode('utf-8')}"


def decrypt_key(encrypted: str) -> str:
    """
    Decrypt a ciphertext (as stored in the DB) back to the plaintext API key.
    Supports both versioned (N:{ciphertext} or vN:{ciphertext}) and legacy (no prefix) formats.
    Never logs or prints the plaintext or ciphertext.
    Returns None if encrypted is None/empty.
    """
    if not encrypted:
        return None
    
    # Parse numeric or legacy v-prefixed version if present
    if ":" in encrypted:
        try:
            version_str, ciphertext = encrypted.split(":", 1)
            version = int(version_str[1:] if version_str.startswith("v") else version_str)
            
            if version not in _ENCRYPTION_KEYS:
                logger.warning(f"[ENCRYPTION] Unknown key version {version}, cannot decrypt")
                return None
            
            fernet = _ENCRYPTION_KEYS[version]
            return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, KeyError) as e:
            logger.warning(f"[ENCRYPTION] Decrypt failed for versioned key: {type(e).__name__}")
            return None
    else:
        # Legacy format (no version prefix) - use V1 key
        try:
            return _ENCRYPTION_KEYS[1].decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            # Corrupt or key-mismatched value
            return None


def get_current_version() -> int:
    """Return the current active encryption key version."""
    return _CURRENT_VERSION
