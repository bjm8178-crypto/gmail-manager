"""
jwt_auth.py - JWT Token Management for Cross-Domain Authentication
Handles JWT token creation, validation, and extraction for secure cross-domain auth.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY env var is required. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7


def create_access_token(user_id: int, email: str) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The user's database ID
        email: The user's Gmail address
    
    Returns:
        Encoded JWT token string
    """
    expiration = datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)
    
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expiration,
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> Optional[Dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token string
    
    Returns:
        Decoded token payload dict, or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("[JWT] Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.info(f"[JWT] Invalid token: {e}")
        return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract the JWT only from the HttpOnly cookie."""
    return request.cookies.get("jwt_token")


def get_user_from_token(request: Request) -> Optional[Dict]:
    """
    Extract and verify user information from JWT token in request.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        Dict with user_id and email, or None if no valid token
    """
    token = extract_token_from_request(request)
    
    if not token:
        return None
    
    payload = verify_token(token)
    
    if not payload:
        return None
    
    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email")
    }


def require_auth(request: Request) -> Dict:
    """
    Require valid JWT authentication. Raises HTTPException if not authenticated.
    Checks JWT token first, then falls back to session for backward compatibility.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        Dict with user_id and email
    
    Raises:
        HTTPException: 401 if not authenticated
    """
    # Try JWT token first
    user = get_user_from_token(request)
    
    if user:
        logger.info(f"[JWT AUTH] Authenticated via JWT: {user['email']}")
        return user
    
    # Fallback to session for backward compatibility
    user_id = request.session.get("user_id")
    email = request.session.get("gmail_address")
    
    if user_id and email:
        logger.info(f"[SESSION AUTH] Authenticated via session: {email}")
        return {"user_id": user_id, "email": email}
    
    # Not authenticated
    logger.info("[AUTH] No valid JWT token or session found")
    raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
