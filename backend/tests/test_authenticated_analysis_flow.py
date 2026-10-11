"""Authenticated analysis route regression without external Gmail credentials."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

import main


async def _fake_analysis_pipeline(*, limit, user_id):
    yield {"type": "email_done", "email_id": "message-1", "status": "success"}
    yield {"type": "complete", "fetched": 1, "analyzed": 1, "failed": 0}


def test_authenticated_analysis_post_returns_successful_sse_result():
    csrf_value = "test-csrf-token-32-chars-long-12345"
    original = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[main.require_auth] = lambda: {
        "user_id": 999,
        "email": "test@example.com",
    }
    try:
        with patch.object(main, "get_labels", return_value=[{"id": 1, "name": "Work"}]), \
             patch.object(main, "analyze_bulk_ordered", new=_fake_analysis_pipeline):
            response = TestClient(main.app).post(
                "/emails/analyze-bulk?count=1",
                cookies={"csrf_token": csrf_value},
                headers={"X-CSRF-Token": csrf_value},
            )
    finally:
        main.app.dependency_overrides = original

    assert response.status_code == 200, response.text
    assert "\"fetched\": 1" in response.text
    assert "\"analyzed\": 1" in response.text
    assert "\"failed\": 0" in response.text
