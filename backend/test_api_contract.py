"""Test that database function calls include required user_id parameters."""

import pytest
from unittest.mock import patch, MagicMock
import database


def test_update_analyzed_email_requires_user_id():
    """Verify update_analyzed_email enforces user_id as keyword-only."""
    with pytest.raises(TypeError, match="user_id"):
        database.update_analyzed_email(
            "email123",
            1,
            50,
            "[]",
            0,
            "labeled"
        )


def test_update_analyzed_email_accepts_user_id():
    """Verify update_analyzed_email works when user_id is provided."""
    with patch.object(database, "_get_connection") as mock_get_conn, \
         patch.object(database, "_release_connection") as mock_release_conn, \
         patch.object(database, "_execute") as mock_execute:
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        database.update_analyzed_email(
            email_id="email123",
            label_id=1,
            scam_score=50,
            scam_indicators="[]",
            is_quarantined=0,
            status="labeled",
            user_id=1
        )
        
        assert mock_execute.called
        assert mock_release_conn.called


def test_update_email_label_id_requires_user_id():
    """Verify update_email_label_id enforces user_id as keyword-only."""
    with pytest.raises(TypeError, match="user_id"):
        database.update_email_label_id("email123", 2)


def test_update_email_label_id_accepts_user_id():
    """Verify update_email_label_id works when user_id is provided."""
    with patch.object(database, "_get_connection") as mock_get_conn, \
         patch.object(database, "_release_connection") as mock_release_conn, \
         patch.object(database, "_execute") as mock_execute:
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        
        database.update_email_label_id(
            email_id="email123",
            label_id=2,
            user_id=1
        )
        
        assert mock_execute.called
        assert mock_release_conn.called
