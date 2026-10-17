"""Tests for Step 4 cheap wins:
a) label_id_map in _analyze_one avoiding DB lookups
b) Thread-local Gmail service cache with token refresh
c) URL_AI_OVERLAP concurrent scan and AI
"""
import asyncio
import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from gmail import (
    _analyze_one,
    get_gmail_service_cached,
    clear_service_cache,
)


@pytest.fixture(autouse=True)
def clean_cache():
    clear_service_cache()
    yield
    clear_service_cache()


# ----------------------------------------------------------------------
# 4a: label_id_map tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_label_id_map_avoids_db_lookup():
    fake_email = {
        "id": "email_map_1",
        "subject": "Hello",
        "sender": "sender@test.com",
        "body": "Test body",
    }
    sem = asyncio.Semaphore(1)
    fake_router = MagicMock()
    fake_router.analyze_json = AsyncMock(return_value={
        "data": {
            "label": "Work",
            "scam_score": 10,
            "scam_indicators": [],
            "reasoning": "Standard work email",
        },
        "provider_used": "fake_ai",
    })

    with patch("database.is_already_analyzed", return_value=False), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("database.save_analyzed_email", return_value=None), \
         patch("gmail.save_analyzed_email", return_value=None), \
         patch("database.update_analyzed_email", return_value=None), \
         patch("database.get_label_id_by_name") as mock_get_label, \
         patch("gmail.get_label_id_by_name", mock_get_label), \
         patch("database.add_to_retry_queue", return_value=None), \
         patch("gmail.add_to_retry_queue", return_value=None), \
         patch("database.remove_from_retry_queue", return_value=None), \
         patch("security.extract_urls", return_value=[]), \
         patch("security.scan_urls_batch", return_value={}):

        label_id_map = {"work": 999, "personal": 888}

        res = await _analyze_one(
            email=fake_email,
            semaphore=sem,
            ai_router=fake_router,
            classification_prompt="",
            user_id=1,
            user_email="test@example.com",
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=sem,
            available_label_names=["Work", "Personal"],
            gmail_labels_cache={},
            update_mode=True,
            label_id_map=label_id_map,
        )

        assert res["status"] == "success"
        assert res["label"] == "Work"
        # Since "work" was in label_id_map, get_label_id_by_name should NEVER be called!
        assert mock_get_label.call_count == 0


@pytest.mark.asyncio
async def test_label_id_map_miss_falls_back_to_db():
    fake_email = {
        "id": "email_map_2",
        "subject": "Hello",
        "sender": "sender@test.com",
        "body": "Test body",
    }
    sem = asyncio.Semaphore(1)
    fake_router = MagicMock()
    fake_router.analyze_json = AsyncMock(return_value={
        "data": {
            "label": "Work",
            "scam_score": 10,
            "scam_indicators": [],
            "reasoning": "Standard work email",
        },
        "provider_used": "fake_ai",
    })

    with patch("database.is_already_analyzed", return_value=False), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("database.save_analyzed_email", return_value=None), \
         patch("gmail.save_analyzed_email", return_value=None), \
         patch("database.update_analyzed_email", return_value=None), \
         patch("database.get_label_id_by_name", return_value=555) as mock_get_label, \
         patch("gmail.get_label_id_by_name", mock_get_label), \
         patch("database.add_to_retry_queue", return_value=None), \
         patch("gmail.add_to_retry_queue", return_value=None), \
         patch("database.remove_from_retry_queue", return_value=None), \
         patch("security.extract_urls", return_value=[]), \
         patch("security.scan_urls_batch", return_value={}):

        # Empty map simulates cache miss
        label_id_map = {}

        res = await _analyze_one(
            email=fake_email,
            semaphore=sem,
            ai_router=fake_router,
            classification_prompt="",
            user_id=1,
            user_email="test@example.com",
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=sem,
            available_label_names=["Work"],
            gmail_labels_cache={},
            update_mode=True,
            label_id_map=label_id_map,
        )

        assert res["status"] == "success"
        # On miss, get_label_id_by_name should be called as fallback
        assert mock_get_label.call_count == 1


# ----------------------------------------------------------------------
# 4b: Thread-local Gmail service cache
# ----------------------------------------------------------------------

def test_get_gmail_service_cached_reuses_service():
    mock_service = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    with patch("gmail.get_credentials", return_value=mock_creds), \
         patch("gmail.build", return_value=mock_service) as mock_build:

        svc1 = get_gmail_service_cached("user@example.com")
        svc2 = get_gmail_service_cached("user@example.com")

        assert svc1 is mock_service
        assert svc2 is mock_service
        # Built only once!
        assert mock_build.call_count == 1


def test_get_gmail_service_cached_refreshes_expired_token():
    mock_service = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = True
    mock_creds.refresh_token = "rt_123"

    with patch("gmail.get_credentials", return_value=mock_creds), \
         patch("gmail.build", return_value=mock_service), \
         patch("auth.save_token") as mock_save_token:

        svc1 = get_gmail_service_cached("user@example.com")
        # Second call should trigger refresh since expired is True
        svc2 = get_gmail_service_cached("user@example.com")

        assert svc1 is mock_service
        assert svc2 is mock_service
        assert mock_creds.refresh.call_count == 1
        assert mock_save_token.call_count == 1


def test_clear_service_cache_resets():
    mock_service1 = MagicMock()
    mock_service2 = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    with patch("gmail.get_credentials", return_value=mock_creds), \
         patch("gmail.build", side_effect=[mock_service1, mock_service2]) as mock_build:

        svc1 = get_gmail_service_cached("user@example.com")
        assert svc1 is mock_service1

        clear_service_cache()

        svc2 = get_gmail_service_cached("user@example.com")
        assert svc2 is mock_service2
        assert mock_build.call_count == 2


# ----------------------------------------------------------------------
# 4c: URL_AI_OVERLAP
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_url_ai_overlap_concurrent_threat_override():
    fake_email = {
        "id": "email_overlap_1",
        "subject": "Click here",
        "sender": "phish@bad.com",
        "body": "Visit http://evil.com",
    }
    sem = asyncio.Semaphore(1)
    fake_router = MagicMock()
    fake_router.analyze_json = AsyncMock(return_value={
        "data": {
            "label": "Inbox",
            "scam_score": 10,
            "scam_indicators": [],
            "reasoning": "Looks okay to AI hint",
        },
        "provider_used": "fake_ai",
    })

    with patch("gmail.URL_AI_OVERLAP", 1), \
         patch("database.is_already_analyzed", return_value=False), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("database.save_analyzed_email", return_value=None), \
         patch("gmail.save_analyzed_email", return_value=None), \
         patch("database.update_analyzed_email", return_value=None), \
         patch("database.get_label_id_by_name", return_value=1), \
         patch("gmail.get_label_id_by_name", return_value=1), \
         patch("database.add_to_retry_queue", return_value=None), \
         patch("gmail.add_to_retry_queue", return_value=None), \
         patch("database.remove_from_retry_queue", return_value=None), \
         patch("security.extract_urls", return_value=["http://evil.com"]), \
         patch("security.scan_urls_batch", new_callable=AsyncMock) as mock_scan:

        # URL scan returns malicious link
        mock_scan.return_value = {
            "http://evil.com": {"is_safe": 0, "threat_type": "MALWARE"}
        }

        res = await _analyze_one(
            email=fake_email,
            semaphore=sem,
            ai_router=fake_router,
            classification_prompt="{sender} {subject} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            user_id=1,
            user_email="test@example.com",
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=sem,
            available_label_names=["Inbox", "Suspicious"],
            gmail_labels_cache={},
            update_mode=True,
        )

        assert res["status"] == "success"
        # Overlap concurrent threat override sets score to >= 95 and quarantines
        assert res["scam_score"] >= 95
        assert res["is_quarantined"] == 1
