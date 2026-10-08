"""Regression coverage for Task 3.3 email-update user scoping."""

import ast
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import database


BACKEND_DIR = Path(__file__).parent


def _find_unscoped_email_update_calls() -> list[tuple[str, int]]:
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

            is_email_update = (
                isinstance(node.func, ast.Name)
                and node.func.id == "update_analyzed_email"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "update_analyzed_email"
            )
            if is_email_update and not any(
                keyword.arg == "user_id" for keyword in node.keywords
            ):
                missing.append((str(source_path), node.lineno))

    return missing


def test_all_application_email_update_calls_pass_user_id():
    """Every production update_analyzed_email call must pass user_id."""
    assert _find_unscoped_email_update_calls() == []


def test_update_analyzed_email_sql_enforces_owner_scope():
    """The database update retains the email and user ownership predicates."""
    with patch.object(database, "_get_connection") as mock_get_conn, \
         patch.object(database, "_release_connection"), \
         patch.object(database, "_execute") as mock_execute:
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        database.update_analyzed_email(
            email_id="email-1",
            label_id=20,
            scam_score=75,
            scam_indicators="[]",
            is_quarantined=0,
            user_id=7,
        )

    query, params = mock_execute.call_args.args[1:3]
    normalized_query = " ".join(query.split())
    assert "WHERE email_id = %s AND user_id = %s" in normalized_query
    assert params[-2:] == ("email-1", 7)


def test_reanalysis_and_update_mode_are_scoped_by_static_scan():
    """Both known update paths remain covered by the application-wide scan."""
    source_files = {
        path.name: path.read_text(encoding="utf-8")
        for path in (BACKEND_DIR / "main.py", BACKEND_DIR / "gmail.py")
    }

    assert "user_id=user_id" in source_files["main.py"]
    assert "update_analyzed_email(email_id=email_id, user_id=user_id" in source_files["gmail.py"]
