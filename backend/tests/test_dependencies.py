"""Test FastAPI authentication dependencies."""

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch
from dependencies import require_auth, get_user_id


def test_require_auth_with_valid_jwt():
    """Verify require_auth extracts user from JWT token."""
    request = MagicMock()
    request.cookies = {"access_token": "valid_jwt"}
    request.session = {}
    
    with patch('dependencies.get_user_from_token', return_value={"user_id": 123, "email": "test@example.com"}):
        user_data = require_auth(request)
        assert user_data["user_id"] == 123
        assert user_data["email"] == "test@example.com"


def test_require_auth_with_session():
    """Verify require_auth falls back to session when JWT is absent."""
    request = MagicMock()
    request.cookies = {}
    request.session = {"user_id": 456, "gmail_address": "session@example.com"}
    
    with patch('dependencies.get_user_from_token', return_value=None):
        user_data = require_auth(request)
        assert user_data["user_id"] == 456
        assert user_data["email"] == "session@example.com"


def test_require_auth_raises_401_when_not_authenticated():
    """Verify require_auth raises 401 when neither JWT nor session is valid."""
    request = MagicMock()
    request.cookies = {}
    request.session = {}
    
    with patch('dependencies.get_user_from_token', return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)
        assert exc_info.value.status_code == 401
        assert "Not logged in" in exc_info.value.detail


def test_get_user_id_extracts_user_id():
    """Verify get_user_id extracts user_id from current_user dict."""
    current_user = {"user_id": 789, "email": "extracted@example.com"}
    user_id = get_user_id(current_user)
    assert user_id == 789


def test_get_user_id_returns_int():
    """Verify get_user_id returns an integer."""
    current_user = {"user_id": 999, "email": "test@example.com"}
    user_id = get_user_id(current_user)
    assert isinstance(user_id, int)
