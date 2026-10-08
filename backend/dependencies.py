"""
dependencies.py — FastAPI Dependency Injection for Authentication
Centralized auth dependency that replaces inline _is_authenticated() + _require_user_id() boilerplate.
"""

from fastapi import Depends, HTTPException, Request
from jwt_auth import get_user_from_token


def require_auth(request: Request) -> dict:
    """
    Dependency that returns the authenticated user dict with keys: user_id, email.
    Checks the HttpOnly JWT cookie first, then falls back to the session cookie.
    Raises HTTPException(401) if neither is valid.
    """
    user_data = get_user_from_token(request)
    if user_data and user_data.get("user_id"):
        return user_data

    user_id = request.session.get("user_id")
    email = request.session.get("gmail_address")
    if user_id and email:
        return {"user_id": user_id, "email": email}

    raise HTTPException(status_code=401, detail="Not logged in.")


def get_user_id(current_user: dict = Depends(require_auth)) -> int:
    """
    Dependency that extracts user_id from the authenticated user.
    Simplifies endpoint signatures by providing user_id directly.
    """
    return current_user["user_id"]
