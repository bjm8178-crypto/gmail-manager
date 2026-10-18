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


def test_predict_load_model_concurrency_with_slow_loader(monkeypatch):
    """
    Task 3: Verify load_model uses a lock so that 8 threads calling load_model concurrently
    with a fake slow loader only run the loader exactly once.
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    import predict

    # Reset cache
    monkeypatch.setattr(predict, "_model", None)
    
    class DummyPath:
        def exists(self):
            return True
        def __str__(self):
            return "dummy_scam_classifier.pkl"
    monkeypatch.setattr(predict, "_model_path", DummyPath())

    load_count = 0
    load_lock = threading.Lock()

    def fake_slow_loader(path):
        nonlocal load_count
        with load_lock:
            load_count += 1
        time.sleep(0.05)
        return {"fake": "model"}

    monkeypatch.setattr(predict.joblib, "load", fake_slow_loader)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(predict.load_model) for _ in range(8)]
        results = [f.result() for f in futures]

    assert load_count == 1
    assert all(r == {"fake": "model"} for r in results)


@pytest.mark.asyncio
async def test_startup_with_missing_model_file_does_not_crash(monkeypatch):
    """
    Task 3: Verify that application startup (lifespan) completes without error
    even if the model file is missing or corrupt.
    """
    import asyncio
    import predict
    from main import app, lifespan

    def mock_missing_model():
        raise FileNotFoundError("Model file not found: scam_classifier_v2.pkl")

    monkeypatch.setattr(predict, "load_model", mock_missing_model)
    monkeypatch.setenv("ML_PRELOAD", "1")
    monkeypatch.setattr("main.init_db", lambda: None)
    monkeypatch.setattr("main.load_active_model", lambda: None)
    monkeypatch.setattr("main.migrate_legacy_tokens", lambda: None)

    # Lifespan should complete startup cleanly
    async with lifespan(app):
        pass
    # Allow background event loop turn for preload task to run and handle exception
    await asyncio.sleep(0.05)
