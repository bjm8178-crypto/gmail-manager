"""Regression test: verify concurrency semaphore covers the whole analysis work in _analyze_one."""
import asyncio
from unittest.mock import patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_analyze_one_concurrency_limits_parallel_runs():
    from gmail import _analyze_one
    import v2_routing

    current_concurrency = 0
    max_concurrency = 0
    lock = asyncio.Lock()

    async def fake_route(*args, **kwargs):
        nonlocal current_concurrency, max_concurrency
        async with lock:
            current_concurrency += 1
            if current_concurrency > max_concurrency:
                max_concurrency = current_concurrency
        try:
            await asyncio.sleep(0.2)
            return {
                "label": "Inbox",
                "scam_score": 15,
                "scam_indicators": ["clean"],
                "reasoning": "Looks safe",
                "routing_decision": "v2_ml",
                "v2_score": 0.15,
                "provider_used": "local_ml_v2",
                "category_status": "completed",
                "analysis_status": "completed",
                "timings": {"ml": 0.05, "ai": 0.0},
            }
        finally:
            async with lock:
                current_concurrency -= 1

    sem = asyncio.Semaphore(2)
    fake_emails = [
        {"id": f"email_{i}", "subject": f"Subject {i}", "sender": f"sender{i}@test.com", "body": f"Body {i}"}
        for i in range(8)
    ]

    with patch("database.is_already_analyzed", return_value=False), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("database.save_analyzed_email", return_value=None), \
         patch("gmail.save_analyzed_email", return_value=None), \
         patch("database.update_analyzed_email", return_value=None), \
         patch("database.get_label_id_by_name", return_value=1), \
         patch("gmail.get_label_id_by_name", return_value=1), \
         patch("database.add_to_retry_queue", return_value=None), \
         patch("gmail.add_to_retry_queue", return_value=None), \
         patch("database.remove_from_retry_queue", return_value=None), \
         patch("v2_routing.route_email_with_v2", side_effect=fake_route), \
         patch("security.scan_urls_batch", return_value={}), \
         patch("security.extract_urls", return_value=[]):

        tasks = [
            _analyze_one(
                email=email,
                semaphore=sem,
                ai_router=MagicMock(),
                classification_prompt="prompt",
                user_id=1,
                user_email="test@user.com",
                service=None,
                url_client=MagicMock(),
                url_semaphore=asyncio.Semaphore(2),
                available_label_names=["Inbox", "Spam"],
                gmail_labels_cache={},
                update_mode=False,
            )
            for email in fake_emails
        ]
        results = await asyncio.gather(*tasks)

    assert len(results) == 8
    for r in results:
        assert r.get("status") == "success", f"Expected status 'success', got {r.get('status')}: {r.get('error')}"

    # Verify semaphore properly throttled concurrent execution
    assert max_concurrency <= 2, f"Expected max concurrency <= 2, got {max_concurrency}"
