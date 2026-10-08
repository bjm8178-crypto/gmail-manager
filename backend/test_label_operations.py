"""Regression coverage for Task 3.2 label-update user scoping."""

import ast
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import database
import main


BACKEND_DIR = Path(__file__).parent


def _find_unscoped_label_update_calls() -> list[tuple[str, int]]:
    """Return application call sites missing the required user_id keyword."""
    missing = []
    for source_path in BACKEND_DIR.glob("*.py"):
        if source_path.name.startswith("test_"):
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            is_label_update = (
                isinstance(node.func, ast.Name)
                and node.func.id == "update_email_label_id"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "update_email_label_id"
            )
            if is_label_update and not any(
                keyword.arg == "user_id" for keyword in node.keywords
            ):
                missing.append((str(source_path), node.lineno))

    return missing


def test_all_application_label_update_calls_pass_user_id():
    """Every production update_email_label_id call must pass user_id."""
    assert _find_unscoped_label_update_calls() == []


def test_label_change_success_passes_user_id_to_database_update():
    """The successful label path forwards the authenticated owner ID."""
    labels = [
        {"label_id": 10, "label_name": "Old"},
        {"label_id": 20, "label_name": "New"},
    ]
    emails = [{"email_id": "email-1", "label_id": 10}]
    service = MagicMock()
    service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": []
    }

    with patch("database.get_labels", return_value=labels), \
         patch("database.get_analyzed_emails", return_value=emails), \
         patch("database.update_email_label_id") as update_label, \
         patch("gmail.get_gmail_service", return_value=service), \
         patch("gmail.get_or_create_label", side_effect=["gmail-old", "gmail-new"]), \
         patch("gmail.change_label") as change_label:
        result = main._apply_label_change(
            "email-1", "New", user_id=7, user_email="user@example.com"
        )

    assert result == {"success": True}
    update_label.assert_called_once_with("email-1", 20, user_id=7)
    change_label.assert_called_once_with(
        "user@example.com", "email-1", "gmail-old", "gmail-new"
    )


def test_update_email_label_id_sql_enforces_owner_scope():
    """The database update retains the email and user ownership predicates."""
    with patch.object(database, "_get_connection") as mock_get_conn, \
         patch.object(database, "_release_connection"), \
         patch.object(database, "_execute") as mock_execute:
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        database.update_email_label_id(
            email_id="email-1", label_id=20, user_id=7
        )

    query, params = mock_execute.call_args.args[1:3]
    normalized_query = " ".join(query.split())
    assert "WHERE email_id = %s AND user_id = %s" in normalized_query
    assert params == (20, "email-1", 7)
