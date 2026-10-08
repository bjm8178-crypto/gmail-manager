"""Regression tests for label rollback ownership scoping."""

from unittest.mock import patch

import main


def test_label_change_rollback_keeps_user_scope():
    labels = [
        {"label_id": 10, "label_name": "Old"},
        {"label_id": 20, "label_name": "New"},
    ]
    emails = [{"email_id": "email-1", "label_id": 10}]

    with patch("database.get_labels", return_value=labels), \
         patch("database.get_analyzed_emails", return_value=emails), \
         patch("database.update_email_label_id") as update_label, \
         patch("gmail.get_gmail_service", return_value=None):
        result = main._apply_label_change("email-1", "New", user_id=7, user_email="user@example.com")

    assert result["success"] is False
    assert update_label.call_count == 2
    assert all(call.kwargs["user_id"] == 7 for call in update_label.call_args_list)
