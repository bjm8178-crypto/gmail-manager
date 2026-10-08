"""Persistence regressions: real SQLite, never the application database."""
import importlib.util
from pathlib import Path
from contextlib import closing

FIELDS = dict(reasoning="reason", routing_decision="review", v2_score=0.91,
              analysis_status="complete", category_status="complete", url_scan_status="partial",
              urls_total=3, urls_checked=1, received_at="2024-01-01T00:00:00Z", user_decision="safe")


def test_metadata_roundtrip_and_scoped_update(db):
    save(db, ml_confidence=0.42, **FIELDS)
    for row in (db.get_analyzed_emails(1)[0], db.get_emails_by_status(1, "labeled")[0]):
        assert all(row[key] == value for key, value in FIELDS.items())
        assert row["ml_confidence"] == 0.42
    args = dict(label_id=None, scam_score=75, scam_indicators='["new"]', is_quarantined=0)
    with pytest.raises(TypeError):
        db.update_analyzed_email("mail", **args)
    db.update_analyzed_email("mail", user_id=2, **args)
    assert db.get_analyzed_emails(1)[0]["scam_score"] == 90
    db.update_analyzed_email("mail", user_id=1, **args, **{**FIELDS, "v2_score": 0.8})
    assert db.get_analyzed_emails(1)[0]["v2_score"] == 0.8
    # Omitted additive fields survive old callers and re-analysis.
    save(db)
    assert db.get_analyzed_emails(1)[0]["v2_score"] == 0.8


def test_received_order_falls_back_to_analysis(db):
    save(db, "old", received_at="2001-01-01T00:00:00Z")
    save(db, "new", received_at="2020-01-01T00:00:00Z")
    save(db, "fallback")
    for rows in (db.get_analyzed_emails(1), db.get_emails_by_status(1, "labeled")):
        assert [r["email_id"] for r in rows] == ["fallback", "new", "old"]
    assert db.get_emails_by_status(1, "labeled", limit=1)[0]["email_id"] == "fallback"

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("FORCE_SQLITE", "true")
    backend = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(backend))
    spec = importlib.util.spec_from_file_location("isolated_database_reliability", backend / "database.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = tmp_path / "test.sqlite"
    module.init_db()
    module.upsert_user("one@example.test", "")
    module.upsert_user("two@example.test", "")
    return module


def save(db, email_id="mail", user_id=1, **kwargs):
    values = dict(label_id=None, scam_score=90, scam_indicators='["danger"]',
                  is_quarantined=1, snippet="snippet", sender="sender", subject="subject")
    values.update(kwargs)
    db.save_analyzed_email(email_id, user_id, **values)


def test_upsert_preserves_children_and_rejects_cross_account(db):
    save(db)
    db.save_url_result("mail", "https://example.test", 0, "phishing")
    db.add_to_retry_queue("mail", 1, "retry")
    save(db, subject="updated")
    with db._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM url_cache").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM retry_queue").fetchone()[0] == 1
    with pytest.raises(ValueError, match="account"):
        save(db, user_id=2)
    assert db.get_analyzed_emails(1)[0]["subject"] == "updated"
    assert db.get_analyzed_emails(2) == []
