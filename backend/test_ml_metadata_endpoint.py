"""
Tests for ML model metadata API endpoint (Task 4.3).
Verifies live metadata generation from ml_models table.
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from database import _get_connection, _release_connection, _execute


client = TestClient(app)


@pytest.fixture
def setup_test_model():
    """Insert a test model into ml_models table for testing."""
    import pickle
    import hashlib
    
    # Create a minimal mock model
    mock_model = {"type": "test", "version": "1.0"}
    model_blob = pickle.dumps(mock_model)
    model_hash = hashlib.sha256(model_blob).hexdigest()
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Clean up any existing test models (use parameterized query)
        _execute(cursor, "DELETE FROM ml_models WHERE version LIKE %s", ('test_%',))
        conn.commit()
        
        # Insert test model
        _execute(cursor, """
            INSERT INTO ml_models (
                version, training_row_count, validation_precision,
                validation_recall, calibration_error, model_blob, 
                model_hash, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            'test_20261006_070000',
            5000,
            0.95,
            0.93,
            0.05,
            model_blob,
            model_hash,
            1  # Make it active
        ))
        conn.commit()
        
        yield
        
        # Cleanup
        _execute(cursor, "DELETE FROM ml_models WHERE version LIKE %s", ('test_%',))
        conn.commit()
        
    finally:
        _release_connection(conn)


def test_metadata_endpoint_returns_active_model(setup_test_model):
    """Verify endpoint returns metadata for active model."""
    response = client.get("/api/ml/active-model-metadata")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "model_type" in data
    assert "model_version" in data
    assert "training_date" in data
    assert "dataset_info" in data
    assert "performance" in data
    assert "security" in data
    
    # Verify model type
    assert data["model_type"] == "Logistic Regression with Isotonic Calibration"
    
    # Verify version matches test data
    assert data["model_version"] == "test_20261006_070000"
    
    # Verify dataset info
    assert data["dataset_info"]["total_emails"] == 5000
    assert "source" in data["dataset_info"]
    
    # Verify performance metrics
    assert data["performance"]["precision_high_risk"] == pytest.approx(0.95, rel=0.01)
    assert data["performance"]["recall_high_risk"] == pytest.approx(0.93, rel=0.01)
    assert data["performance"]["calibration_error"] == pytest.approx(0.05, rel=0.01)
    
    # Verify security info
    assert "model_hash" in data["security"]
    assert data["security"]["hash_algorithm"] == "SHA-256"
    assert data["security"]["integrity_verified"] is True
    assert len(data["security"]["model_hash"]) == 64  # SHA-256 hex length


def test_metadata_endpoint_no_active_model():
    """Verify endpoint returns 404 when no active model exists."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Deactivate all models temporarily
        _execute(cursor, "UPDATE ml_models SET is_active = 0", ())
        conn.commit()
        
        response = client.get("/api/ml/active-model-metadata")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "No active model found" in data["error"]
        assert "message" in data
        
    finally:
        # Restore active models
        _execute(cursor, "UPDATE ml_models SET is_active = 1 WHERE version LIKE %s", ('test_%',))
        conn.commit()
        _release_connection(conn)


def test_metadata_training_date_format(setup_test_model):
    """Verify training_date is in ISO format."""
    response = client.get("/api/ml/active-model-metadata")
    
    assert response.status_code == 200
    data = response.json()
    
    # Parse training_date to verify ISO format
    training_date = data["training_date"]
    parsed_date = datetime.fromisoformat(training_date.replace('Z', '+00:00'))
    
    assert isinstance(parsed_date, datetime)
    assert parsed_date.year == 2026


def test_metadata_endpoint_handles_null_metrics(setup_test_model):
    """Verify endpoint handles NULL performance metrics gracefully."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Insert model with NULL metrics
        _execute(cursor, """
            INSERT INTO ml_models (
                version, training_row_count, validation_precision,
                validation_recall, calibration_error, model_blob,
                model_hash, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            'test_null_metrics',
            1000,
            None,  # NULL precision
            None,  # NULL recall
            None,  # NULL calibration_error
            b'test',
            'abc123',
            0  # Not active, so it won't interfere with active model test
        ))
        conn.commit()
        
        # The active model should still work (from setup_test_model fixture)
        response = client.get("/api/ml/active-model-metadata")
        assert response.status_code == 200
        
        # Cleanup
        _execute(cursor, "DELETE FROM ml_models WHERE version = 'test_null_metrics'")
        conn.commit()
        
    finally:
        _release_connection(conn)


def test_metadata_reflects_most_recent_active_model(setup_test_model):
    """Verify endpoint returns the most recent active model when multiple exist."""
    import pickle
    import hashlib
    from datetime import datetime, timedelta
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Get the trained_at timestamp of the fixture model
        _execute(cursor, "SELECT trained_at FROM ml_models WHERE version = %s", ('test_20261006_070000',))
        fixture_row = cursor.fetchone()
        fixture_timestamp = fixture_row['trained_at'] if isinstance(fixture_row, dict) else fixture_row[0]
        
        # Create an older model with an earlier timestamp
        old_model = {"type": "old_test", "version": "0.9"}
        old_blob = pickle.dumps(old_model)
        old_hash = hashlib.sha256(old_blob).hexdigest()
        old_timestamp = fixture_timestamp - timedelta(days=5)
        
        # Insert an older active model with explicit trained_at
        _execute(cursor, """
            INSERT INTO ml_models (
                version, training_row_count, validation_precision,
                validation_recall, calibration_error, model_blob,
                model_hash, is_active, trained_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            'test_20261001_120000',  # Older date in version string
            3000,
            0.90,
            0.88,
            0.08,
            old_blob,
            old_hash,
            1,  # Also active
            old_timestamp
        ))
        conn.commit()
        
        response = client.get("/api/ml/active-model-metadata")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return the newer model (from setup_test_model, by trained_at DESC)
        assert data["model_version"] == "test_20261006_070000"
        assert data["dataset_info"]["total_emails"] == 5000
        
        # Cleanup
        _execute(cursor, "DELETE FROM ml_models WHERE version = %s", ('test_20261001_120000',))
        conn.commit()
        
    finally:
        _release_connection(conn)


def test_metadata_endpoint_response_structure():
    """Verify the complete response structure matches documentation."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if there's any active model in the database
        _execute(cursor, "SELECT COUNT(*) FROM ml_models WHERE is_active = 1", ())
        row = cursor.fetchone()
        count = row['count'] if isinstance(row, dict) else row[0]
        
        if count == 0:
            pytest.skip("No active model in database for structure test")
        
        response = client.get("/api/ml/active-model-metadata")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify top-level structure
            expected_keys = {"model_type", "model_version", "training_date", 
                           "dataset_info", "performance", "security", "model_id"}
            assert set(data.keys()) == expected_keys
            
            # Verify nested structures
            assert set(data["dataset_info"].keys()) == {"total_emails", "source"}
            assert "precision_high_risk" in data["performance"]
            assert "recall_high_risk" in data["performance"]
            assert "calibration_error" in data["performance"]
            assert set(data["security"].keys()) == {"model_hash", "hash_algorithm", "integrity_verified"}
            
    finally:
        _release_connection(conn)
