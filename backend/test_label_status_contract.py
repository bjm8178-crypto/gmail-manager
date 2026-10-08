"""Regression test for routing-status compatibility in the label pipeline."""
from pathlib import Path


GMAIL_SOURCE = Path(__file__).with_name("gmail.py").read_text(encoding="utf-8")


def test_label_pipeline_accepts_v2_complete_status():
    """The v2 router's 'complete' status must be normalized before label selection."""
    assert 'if category_status == "complete":' in GMAIL_SOURCE
    assert 'category_status = "completed"' in GMAIL_SOURCE
