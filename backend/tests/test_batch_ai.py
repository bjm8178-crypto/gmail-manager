"""
Tests for Step 3 (batch AI calls in label_only_pipeline and AIRouter.analyze_batch).
Verifies:
- 10 emails with AI_BATCH_SIZE=5 -> exactly 2 batch AI calls
- Provider returning malformed JSON -> falls back to single calls, all complete successfully
- AI_BATCH_SIZE=1 behaves identically to original path
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from ai_router import AIRouter


class TestAIRouterBatch:
    """Test suite for AIRouter.analyze_batch and fallback behavior."""

    @pytest.mark.asyncio
    async def test_analyze_batch_success(self):
        """Batch call returns valid parsed results matching items."""
        router = AIRouter()
        items = [
            {"id": "e_1", "sender": "boss@co.com", "subject": "Meeting", "body": "Let's meet tomorrow."},
            {"id": "e_2", "sender": "spam@promo.com", "subject": "Sale", "body": "50% discount!"},
        ]
        available_labels = ["Work", "Promotions", "Spam"]

        fake_batch_output = (
            '[{"id": "e_1", "label": "Work", "scam_score": 5, "scam_indicators": [], "reasoning": "Work meeting"},'
            ' {"id": "e_2", "label": "Promotions", "scam_score": 15, "scam_indicators": [], "reasoning": "Ad"}]'
        )

        with patch.object(router, "_run_cascade", new_callable=AsyncMock) as mock_cascade:
            mock_cascade.return_value = {
                "data": [
                    {"id": "e_1", "label": "Work", "scam_score": 5, "scam_indicators": [], "reasoning": "Work meeting"},
                    {"id": "e_2", "label": "Promotions", "scam_score": 15, "scam_indicators": [], "reasoning": "Ad"},
                ],
                "provider_used": "fake_groq",
            }

            res = await router.analyze_batch(items, available_labels)

        assert len(res["results"]) == 2
        assert res["results"][0]["id"] == "e_1"
        assert res["results"][0]["label"] == "Work"
        assert res["results"][1]["id"] == "e_2"
        assert res["results"][1]["label"] == "Promotions"
        assert res["provider_used"] == "fake_groq"

    @pytest.mark.asyncio
    async def test_analyze_batch_malformed_json_falls_back_to_single_calls(self):
        """When batch call returns malformed/partial response, falls back to analyze_json."""
        router = AIRouter()
        items = [
            {"id": "e_1", "sender": "boss@co.com", "subject": "Meeting", "body": "Let's meet tomorrow."},
            {"id": "e_2", "sender": "spam@promo.com", "subject": "Sale", "body": "50% discount!"},
        ]
        available_labels = ["Work", "Promotions", "Spam"]

        # Batch cascade raises ValueError or returns error
        with patch.object(router, "_run_cascade", side_effect=Exception("Malformed JSON from all providers")), \
             patch.object(router, "analyze_json", new_callable=AsyncMock) as mock_single:

            mock_single.return_value = {
                "data": {"label": "Work", "scam_score": 10, "scam_indicators": [], "reasoning": "Fallback ok"},
                "provider_used": "groq",
            }

            res = await router.analyze_batch(items, available_labels)

        # Both items completed via fallback
        assert len(res["results"]) == 2
        assert mock_single.call_count == 2
        assert res["results"][0]["id"] == "e_1"
        assert res["results"][1]["id"] == "e_2"
        assert res["results"][0]["label"] == "Work"


class TestLabelOnlyPipelineBatching:
    """Test suite for label_only_pipeline with AI_BATCH_SIZE."""

    @pytest.mark.asyncio
    @patch('gmail.get_gmail_service')
    @patch('gmail.get_labels')
    @patch('database.get_emails_by_status')
    @patch('gmail._analyze_one')
    async def test_10_emails_batch_size_5_exactly_2_batch_calls(
        self, mock_analyze_one, mock_get_status, mock_get_labels, mock_svc
    ):
        """10 emails with AI_BATCH_SIZE=5 -> exactly 2 calls to ai_router.analyze_batch."""
        mock_svc.return_value = MagicMock()
        mock_get_labels.return_value = [{"label_id": 1, "label_name": "Work"}]

        emails_10 = [
            {"id": f"e_{i}", "subject": f"Sub {i}", "sender": "a@b.com", "body": "Test body", "snippet": "Test"}
            for i in range(10)
        ]
        mock_get_status.return_value = emails_10

        mock_analyze_one.side_effect = lambda **kwargs: {
            "email_id": kwargs["email"]["id"],
            "subject": kwargs["email"].get("subject"),
            "status": "success",
            "label": "Work",
            "scam_score": 10,
        }

        from gmail import label_only_pipeline
        fake_router = MagicMock()
        batch_call_count = [0]

        async def fake_analyze_batch(items, available_labels):
            batch_call_count[0] += 1
            return {
                "results": [
                    {"id": it["id"], "label": "Work", "scam_score": 10, "scam_indicators": [], "reasoning": "Ok"}
                    for it in items
                ],
                "provider_used": "mock_batch",
            }
        fake_router.analyze_batch = AsyncMock(side_effect=fake_analyze_batch)

        with patch('ai_router.AI_BATCH_SIZE', 5), \
             patch('ai_router.ai_router', fake_router), \
             patch('security.scan_urls_batch', return_value={}), \
             patch('security.extract_urls', return_value=[]):

            events = []
            async for ev in label_only_pipeline(limit=10, user_id=1, user_email="test@test.com"):
                events.append(ev)

        # Verified: exactly 2 batch AI calls for 10 emails
        assert batch_call_count[0] == 2
        # All 10 emails analyzed
        complete_events = [e for e in events if e.get("type") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["analyzed"] == 10

    @pytest.mark.asyncio
    @patch('gmail.get_gmail_service')
    @patch('gmail.get_labels')
    @patch('database.get_emails_by_status')
    @patch('gmail._analyze_one')
    async def test_batch_size_1_uses_original_path(
        self, mock_analyze_one, mock_get_status, mock_get_labels, mock_svc
    ):
        """When AI_BATCH_SIZE=1, analyze_batch is never called; standard per-email path runs."""
        mock_svc.return_value = MagicMock()
        mock_get_labels.return_value = [{"label_id": 1, "label_name": "Work"}]

        emails_3 = [
            {"id": f"e_{i}", "subject": f"Sub {i}", "sender": "a@b.com", "body": "Body", "snippet": "Snip"}
            for i in range(3)
        ]
        mock_get_status.return_value = emails_3

        mock_analyze_one.side_effect = lambda **kwargs: {
            "email_id": kwargs["email"]["id"],
            "subject": kwargs["email"].get("subject"),
            "status": "success",
            "label": "Work",
            "scam_score": 10,
        }

        from gmail import label_only_pipeline
        fake_router = MagicMock()
        fake_router.analyze_batch = AsyncMock()

        with patch('ai_router.AI_BATCH_SIZE', 1), \
             patch('ai_router.ai_router', fake_router):

            events = []
            async for ev in label_only_pipeline(limit=3, user_id=1, user_email="test@test.com"):
                events.append(ev)

        # analyze_batch was NOT called because AI_BATCH_SIZE=1
        fake_router.analyze_batch.assert_not_called()
        # _analyze_one was called 3 times
        assert mock_analyze_one.call_count == 3
