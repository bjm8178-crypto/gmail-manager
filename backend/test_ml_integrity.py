"""Test ML model integrity verification (Task 4.1)."""

import pytest
import hashlib
import pickle
from unittest.mock import MagicMock
from ml_inference import load_active_model


@pytest.fixture
def mock_model():
    """Create a simple mock model for testing."""
    return {"model_type": "test", "version": "v1"}


@pytest.fixture
def create_model_blob(mock_model):
    """Helper to create model blob and its hash."""
    def _create():
        model_blob = pickle.dumps(mock_model)
        model_hash = hashlib.sha256(model_blob).hexdigest()
        return model_blob, model_hash
    return _create


def test_load_model_with_valid_hash(monkeypatch, mock_model, create_model_blob):
    """Verify load_active_model succeeds when hash matches."""
    model_blob, model_hash = create_model_blob()
    
    # Mock database response
    mock_row = ("v20260820_001758", model_blob, 0.95, model_hash)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_row
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    def mock_get_connection():
        return mock_conn
    
    def mock_release_connection(conn):
        pass
    
    def mock_execute(cursor, query):
        pass
    
    monkeypatch.setattr("ml_inference._get_connection", mock_get_connection)
    monkeypatch.setattr("ml_inference._release_connection", mock_release_connection)
    monkeypatch.setattr("ml_inference._execute", mock_execute)
    
    # Load model
    result = load_active_model()
    
    # Verify model loaded successfully
    assert result is not None
    assert result == mock_model


def test_load_model_with_hash_mismatch(monkeypatch, mock_model, create_model_blob):
    """Verify load_active_model rejects model when hash mismatches."""
    model_blob, correct_hash = create_model_blob()
    
    # Use a different hash (tampered)
    tampered_hash = "0" * 64
    
    # Mock database response with tampered hash
    mock_row = ("v20260820_001758", model_blob, 0.95, tampered_hash)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_row
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    def mock_get_connection():
        return mock_conn
    
    def mock_release_connection(conn):
        pass
    
    def mock_execute(cursor, query):
        pass
    
    monkeypatch.setattr("ml_inference._get_connection", mock_get_connection)
    monkeypatch.setattr("ml_inference._release_connection", mock_release_connection)
    monkeypatch.setattr("ml_inference._execute", mock_execute)
    
    # Load model
    result = load_active_model()
    
    # Verify model was rejected
    assert result is None


def test_load_model_without_hash(monkeypatch, mock_model, create_model_blob):
    """Verify load_active_model logs warning but loads when hash is missing (legacy models)."""
    model_blob, _ = create_model_blob()
    
    # Mock database response without hash (legacy model)
    mock_row = ("v20260820_001758", model_blob, 0.95, None)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = mock_row
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    def mock_get_connection():
        return mock_conn
    
    def mock_release_connection(conn):
        pass
    
    def mock_execute(cursor, query):
        pass
    
    monkeypatch.setattr("ml_inference._get_connection", mock_get_connection)
    monkeypatch.setattr("ml_inference._release_connection", mock_release_connection)
    monkeypatch.setattr("ml_inference._execute", mock_execute)
    
    # Load model
    result = load_active_model()
    
    # Verify model loaded (backward compatibility)
    assert result is not None
    assert result == mock_model


def test_load_model_no_active_model(monkeypatch):
    """Verify load_active_model returns None when no active model exists."""
    # Mock empty database response
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    def mock_get_connection():
        return mock_conn
    
    def mock_release_connection(conn):
        pass
    
    def mock_execute(cursor, query):
        pass
    
    monkeypatch.setattr("ml_inference._get_connection", mock_get_connection)
    monkeypatch.setattr("ml_inference._release_connection", mock_release_connection)
    monkeypatch.setattr("ml_inference._execute", mock_execute)
    
    # Load model
    result = load_active_model()
    
    # Verify returns None for AI-only mode
    assert result is None
