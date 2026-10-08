"""Cross-backend verification for audit SQL placeholder handling."""

import database
import audit


def test_active_backend_exposes_expected_placeholder():
    conn = database._get_connection()
    try:
        cursor = conn.cursor()
        audit._execute(cursor, "SELECT %s AS value", ("dialect-ok",))
        row = cursor.fetchone()
        value = row["value"] if hasattr(row, "keys") else row[0]
        assert value == "dialect-ok"
        assert database._PLACEHOLDER in {"%s", "?"}
    finally:
        database._release_connection(conn)
