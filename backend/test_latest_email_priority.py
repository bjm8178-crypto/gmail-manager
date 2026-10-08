"""
test_latest_email_priority.py — Verify that analysis always fetches latest emails first

Confirms that both analyze_bulk_ordered() and fetch_only_pipeline() no longer use
cursor-based pagination, ensuring they always start from the newest emails.
"""
import importlib.util
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, Mock, patch, AsyncMock

BACKEND = Path(__file__).resolve().parent
_modules = {name: MagicMock() for name in ("auth", "database", "ml_inference")}
_spec = importlib.util.spec_from_file_location("gmail", BACKEND / "gmail.py")
_gmail = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, _modules):
    _spec.loader.exec_module(_gmail)
sys.modules["gmail"] = _gmail

from gmail import analyze_bulk_ordered, fetch_only_pipeline


@pytest.mark.anyio
async def test_analyze_bulk_ordered_fetches_latest_emails():
    """Verify analyze_bulk_ordered() passes page_token=None to fetch_emails"""
    mock_fetch_result = {"emails": [], "next_page_token": "some_token"}

    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.fetch_emails", return_value=mock_fetch_result) as mock_fetch, \
         patch("gmail.get_user_email_by_id", return_value="user@test.com"), \
         patch("gmail.get_labels", return_value=[]):
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}

        gen = analyze_bulk_ordered(limit=50, user_id=1, user_email="user@test.com")
        initializing = await gen.__anext__()
        complete = await gen.__anext__()

        assert initializing["type"] == "initializing"
        assert complete["type"] == "complete"
        mock_fetch.assert_called_once_with(
            limit=50,
            page_token=None,
            user_email="user@test.com",
        )



@pytest.mark.anyio
async def test_fetch_only_pipeline_fetches_latest_emails():
    """Verify fetch_only_pipeline() passes page_token=None to fetch_emails"""
    
    mock_fetch_result = {
        "emails": [
            {"id": "msg2", "subject": "Newest", "sender": "sender@test.com", "snippet": "", "body": "", "labels": []},
        ],
        "next_page_token": None
    }
    
    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.fetch_emails", return_value=mock_fetch_result) as mock_fetch, \
         patch("gmail.get_user_email_by_id", return_value="user@test.com"), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("gmail.save_analyzed_email"), \
         patch("gmail._get_email_body", return_value="body text"), \
         patch("gmail.asyncio.to_thread", new=AsyncMock(side_effect=lambda f, *args, **kwargs: f(*args, **kwargs))):
        
        mock_service.return_value = Mock()
        
        # Run through the generator
        gen = fetch_only_pipeline(limit=50, user_id=1, user_email="user@test.com")
        events = [event async for event in gen]
        assert all(event.get("type") != "error" for event in events)
        assert events[-1]["type"] == "complete"
        
        # Verify fetch_emails was called with page_token=None
        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args[1]
        assert call_kwargs["page_token"] is None, "Should always fetch from latest (page_token=None)"
        assert call_kwargs["limit"] == 50


@pytest.mark.anyio
async def test_cursor_functions_not_called_during_analysis():
    """Verify that get_scan_cursor and save_scan_cursor are NOT called during analysis"""
    
    mock_fetch_result = {
        "emails": [],
        "next_page_token": None
    }
    
    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.fetch_emails", return_value=mock_fetch_result), \
         patch("gmail.get_user_email_by_id", return_value="user@test.com"), \
         patch("gmail.get_scan_cursor") as mock_get_cursor, \
         patch("gmail.save_scan_cursor") as mock_save_cursor, \
         patch("gmail.get_labels", return_value=[]), \
         patch("gmail.asyncio.to_thread", new=AsyncMock(side_effect=lambda f, *args, **kwargs: f(*args, **kwargs))):
        
        mock_service.return_value = Mock()
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}
        
        # Run analyze_bulk_ordered
        gen = analyze_bulk_ordered(limit=50, user_id=1, user_email="user@test.com")
        async for event in gen:
            pass
        
        # Verify cursor functions were NEVER called
        mock_get_cursor.assert_not_called()
        mock_save_cursor.assert_not_called()


def test_each_fetch_restarts_at_first_page_and_sees_new_arrival():
    """A new run requests Gmail again, not the previous run's next page."""
    from gmail import fetch_emails

    service = Mock()
    listing = service.users.return_value.messages.return_value.list
    listing.return_value.execute.side_effect = [
        {"messages": [{"id": "older"}], "nextPageToken": "historical-page"},
        {"messages": [{"id": "new-arrival"}], "nextPageToken": "other-page"},
    ]
    with patch("gmail.get_gmail_service", return_value=service), \
         patch("gmail.get_credentials", return_value=object()), \
         patch("gmail._get_email_details_batch_threadsafe",
               side_effect=lambda creds, ids: [{"id": mid} for mid in ids]):
        first = fetch_emails(limit=1, user_email="user@test.com")
        second = fetch_emails(limit=1, user_email="user@test.com")

    assert [email["id"] for email in first["emails"]] == ["older"]
    assert [email["id"] for email in second["emails"]] == ["new-arrival"]
    assert listing.call_count == 2
    assert all(call.kwargs["pageToken"] is None for call in listing.call_args_list)


@pytest.mark.anyio
async def test_analyze_bulk_ordered_continues_after_deduplicating_a_page():
    """Analysis follows next_page_token until it has enough new emails."""
    first_page = {
        "emails": [{"id": "already-seen"}],
        "next_page_token": "page-2",
    }
    second_page = {
        "emails": [{"id": "new-email", "subject": "New", "sender": "sender@test.com"}],
        "next_page_token": None,
    }
    analysis_result = {
        "status": "success", "email_id": "new-email", "sender": "sender@test.com",
        "subject": "New", "label": "Finance", "scam_score": 0, "is_quarantined": 0,
    }

    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.fetch_emails", side_effect=[first_page, second_page]) as mock_fetch, \
         patch("gmail.get_labels", return_value=[]), \
         patch("gmail.is_already_analyzed", side_effect=[True, False]), \
         patch("gmail._analyze_one", new=AsyncMock(return_value=analysis_result)):
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}
        events = [event async for event in analyze_bulk_ordered(limit=1, user_id=1, user_email="user@test.com")]

    assert events[-1]["type"] == "complete"
    assert events[-1]["analyzed"] == 1
    assert [call.kwargs for call in mock_fetch.call_args_list] == [
        {"limit": 1, "page_token": None, "user_email": "user@test.com"},
        {"limit": 1, "page_token": "page-2", "user_email": "user@test.com"},
    ]


@pytest.mark.anyio
async def test_fetch_only_pipeline_continues_after_deduplicating_a_page():
    """Fetch-only follows next_page_token until it has enough new emails."""
    first_page = {
        "emails": [{"id": "already-seen"}],
        "next_page_token": "page-2",
    }
    second_page = {
        "emails": [{"id": "new-email", "subject": "New", "sender": "sender@test.com", "snippet": "", "body": "", "labels": []}],
        "next_page_token": None,
    }

    with patch("gmail.get_gmail_service", return_value=Mock()), \
         patch("gmail.fetch_emails", side_effect=[first_page, second_page]) as mock_fetch, \
         patch("gmail.is_already_analyzed", side_effect=[True, False]), \
         patch("gmail.save_analyzed_email") as mock_save, \
         patch("gmail._get_email_body", return_value="body text"):
        events = [event async for event in fetch_only_pipeline(limit=1, user_id=1, user_email="user@test.com")]

    assert events[-1] == {"type": "complete", "fetched": 1, "skipped": 1}
    mock_save.assert_called_once()
    assert [call.kwargs for call in mock_fetch.call_args_list] == [
        {"limit": 1, "page_token": None, "user_email": "user@test.com"},
        {"limit": 1, "page_token": "page-2", "user_email": "user@test.com"},
    ]
