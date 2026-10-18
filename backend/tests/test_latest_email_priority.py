"""
test_latest_email_priority.py — Verify that analysis always fetches latest emails first

Confirms that both analyze_bulk_ordered() and fetch_only_pipeline() no longer use
cursor-based pagination, ensuring they always start from the newest emails.
"""
import importlib.util
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, Mock, patch, AsyncMock, call

BACKEND = Path(__file__).resolve().parents[1]
_modules = {name: MagicMock() for name in ("auth", "database", "ml_inference")}
_spec = importlib.util.spec_from_file_location("gmail", BACKEND / "gmail.py")
_gmail = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, _modules):
    _spec.loader.exec_module(_gmail)
analyze_bulk_ordered = _gmail.analyze_bulk_ordered
fetch_only_pipeline = _gmail.fetch_only_pipeline
label_only_pipeline = _gmail.label_only_pipeline


@pytest.fixture(autouse=True)
def isolated_gmail_module():
    """Expose this module only while its own tests run, never during collection."""
    with patch.dict(sys.modules, {"gmail": _gmail}):
        yield


@pytest.mark.anyio
async def test_analyze_bulk_ordered_fetches_latest_emails():
    """Verify analyze_bulk_ordered() passes page_token=None to list_message_ids"""
    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.list_message_ids", return_value=([], None)) as mock_list, \
         patch("gmail.get_user_email_by_id", return_value="user@test.com"), \
         patch("gmail.get_labels", return_value=[]):
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}

        gen = analyze_bulk_ordered(limit=50, user_id=1, user_email="user@test.com")
        initializing = await gen.__anext__()
        complete = await gen.__anext__()

        assert initializing["type"] == "initializing"
        assert complete["type"] == "complete"
        mock_list.assert_called_once_with(
            user_id=1,
            max_results=50,
            page_token=None,
            user_email="user@test.com",
        )



@pytest.mark.anyio
async def test_fetch_only_pipeline_fetches_latest_emails():
    """Verify fetch_only_pipeline() passes page_token=None to list_message_ids"""
    
    mock_email = {"id": "msg2", "subject": "Newest", "sender": "sender@test.com", "snippet": "", "body": "", "labels": []}
    
    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.list_message_ids", return_value=(["msg2"], None)) as mock_list, \
         patch("gmail._fetch_email_details", return_value=[mock_email]), \
         patch("gmail.get_user_email_by_id", return_value="user@test.com"), \
         patch("gmail.is_already_analyzed", return_value=False), \
         patch("gmail.get_analyzed_email_ids", return_value=set()), \
         patch("gmail.save_analyzed_email"), \
         patch("gmail.save_fetched_emails_bulk"), \
         patch("gmail.get_credentials", return_value=Mock()), \
         patch("gmail._get_email_bodies_batch", return_value={"msg2": "body text"}), \
         patch("gmail._get_email_body", return_value="body text"), \
         patch("gmail.asyncio.to_thread", new=AsyncMock(side_effect=lambda f, *args, **kwargs: f(*args, **kwargs))):
        
        mock_service.return_value = Mock()
        
        # Run through the generator
        gen = fetch_only_pipeline(limit=50, user_id=1, user_email="user@test.com")
        events = [event async for event in gen]
        assert all(event.get("type") != "error" for event in events)
        assert events[-1]["type"] == "complete"
        
        # Verify list_message_ids was called with page_token=None
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["page_token"] is None, "Should always fetch from latest (page_token=None)"
        assert call_kwargs["user_email"] == "user@test.com"


@pytest.mark.anyio
async def test_cursor_functions_not_called_during_analysis():
    """Verify that get_scan_cursor and save_scan_cursor are NOT called during analysis"""
    
    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.list_message_ids", return_value=([], None)), \
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
    first_page_ids = (["already-seen"], "page-2")
    second_page_ids = (["new-email"], None)
    email_details = [{"id": "new-email", "subject": "New", "sender": "sender@test.com"}]
    analysis_result = {
        "status": "success", "email_id": "new-email", "sender": "sender@test.com",
        "subject": "New", "label": "Finance", "scam_score": 0, "is_quarantined": 0,
    }

    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail.list_message_ids", side_effect=[first_page_ids, second_page_ids]) as mock_list, \
         patch("gmail._fetch_email_details", return_value=email_details) as mock_details, \
         patch("gmail.get_labels", return_value=[]), \
         patch("gmail.get_analyzed_email_ids", side_effect=[{"already-seen"}, set()]), \
         patch("gmail.is_already_analyzed", side_effect=[True, False]), \
         patch("gmail._analyze_one", new=AsyncMock(return_value=analysis_result)):
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}
        events = [event async for event in analyze_bulk_ordered(limit=1, user_id=1, user_email="user@test.com")]

    assert events[-1]["type"] == "complete"
    assert events[-1]["analyzed"] == 1
    assert [call.kwargs["page_token"] for call in mock_list.call_args_list] == [None, "page-2"]
    mock_details.assert_called_once()
    assert mock_details.call_args[0][0] == ["new-email"]


@pytest.mark.anyio
async def test_fetch_only_pipeline_continues_after_deduplicating_a_page():
    """Fetch-only follows next_page_token until it has enough new emails."""
    first_page_ids = (["already-seen"], "page-2")
    second_page_ids = (["new-email"], None)
    email_details = [{"id": "new-email", "subject": "New", "sender": "sender@test.com", "snippet": "", "body": "", "labels": []}]

    with patch("gmail.get_gmail_service", return_value=Mock()), \
         patch("gmail.list_message_ids", side_effect=[first_page_ids, second_page_ids]) as mock_list, \
         patch("gmail._fetch_email_details", return_value=email_details) as mock_details, \
         patch("gmail.get_analyzed_email_ids", side_effect=[{"already-seen"}, set()]), \
         patch("gmail.is_already_analyzed", side_effect=[True, False]), \
         patch("gmail.save_analyzed_email") as mock_save, \
         patch("gmail.save_fetched_emails_bulk") as mock_save_bulk, \
         patch("gmail.get_credentials", return_value=Mock()), \
         patch("gmail._get_email_bodies_batch", return_value={"new-email": "body text"}), \
         patch("gmail._get_email_body", return_value="body text"):
        events = [event async for event in fetch_only_pipeline(limit=1, user_id=1, user_email="user@test.com")]

    assert events[-1] == {"type": "complete", "fetched": 1, "skipped": 1}
    # Exactly one email saved — via bulk (FETCH_BATCH=1) or per-email (FETCH_BATCH=0)
    assert mock_save.call_count + mock_save_bulk.call_count == 1
    assert [call.kwargs["page_token"] for call in mock_list.call_args_list] == [None, "page-2"]
    mock_details.assert_called_once()
    assert mock_details.call_args[0][0] == ["new-email"]


@pytest.mark.anyio
async def test_fetch_only_130_of_130_already_analyzed_fetches_zero_details():
    """
    Task 4: When 130 of 130 listed IDs are already analyzed across pages,
    verify that 0 email details are fetched, skipping all 130.
    """
    page1_ids = ([f"msg_{i}" for i in range(1, 51)], "page-2")
    page2_ids = ([f"msg_{i}" for i in range(51, 101)], "page-3")
    page3_ids = ([f"msg_{i}" for i in range(101, 131)], None)
    all_130_ids = {f"msg_{i}" for i in range(1, 131)}

    with patch("gmail.get_gmail_service", return_value=Mock()), \
         patch("gmail.list_message_ids", side_effect=[page1_ids, page2_ids, page3_ids]) as mock_list, \
         patch("gmail._fetch_email_details") as mock_fetch_details, \
         patch("gmail.get_analyzed_email_ids", return_value=all_130_ids), \
         patch("gmail.is_already_analyzed", return_value=True):
        events = [event async for event in fetch_only_pipeline(limit=20, user_id=1, user_email="user@test.com")]

    mock_fetch_details.assert_not_called()
    assert mock_list.call_count == 3
    assert events[-1] == {"type": "complete", "fetched": 0, "skipped": 130}


@pytest.mark.anyio
async def test_analyze_bulk_ordered_repairs_failed_result_in_same_job():
    email = {"id": "repair-me", "subject": "Retry", "sender": "sender@test.com", "body": "body"}
    calls = []

    async def fake_analyze_one(*args, **kwargs):
        calls.append(kwargs.get("update_mode", False))
        if kwargs.get("update_mode"):
            return {
                "status": "success", "analysis_status": "completed", "email_id": "repair-me",
                "subject": "Retry", "sender": "sender@test.com", "label": "Work",
                "scam_score": 10, "is_quarantined": 0,
            }
        return {
            "status": "failed", "analysis_status": "failed", "email_id": "repair-me",
            "subject": "Retry", "sender": "sender@test.com", "label": "Unknown",
            "scam_score": None, "is_quarantined": 0,
        }

    with patch("gmail.get_gmail_service") as mock_service, \
         patch("gmail._fetch_new_emails", new=AsyncMock(return_value=([email], 0, 1))), \
         patch("gmail.get_labels", return_value=[{"label_name": "Work"}]), \
         patch("gmail._analyze_one", new=AsyncMock(side_effect=fake_analyze_one)) as analyze, \
         patch("gmail.asyncio.sleep", new=AsyncMock()) as sleep:
        mock_service.return_value.users().labels().list().execute.return_value = {"labels": []}
        events = [event async for event in analyze_bulk_ordered(limit=1, user_id=1, user_email="user@test.com")]

    assert analyze.await_count == 2
    assert sleep.await_args_list == [call(5)]
    assert events[-1]["analyzed"] == 1
    assert events[-1]["failed"] == 0
    assert events[-1]["repair"] == {
        "attempted": 1, "resolved": 1, "unresolved": 0, "unresolved_ids": [],
    }
