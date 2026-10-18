"""
Tests for Step 2 (batch fetch & pre-filter in fetch_only_pipeline).
Verifies:
- 50 emails -> 2 batch requests of 25
- Existing emails filtered in 1 DB query (get_analyzed_email_ids), not N
- Bulk save inserts rows without downgrading existing records
- Progress events are preserved
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock


class TestBatchFetch:
    """Test suite for Step 2 batch fetching and bulk saving."""

    @pytest.mark.asyncio
    @patch('gmail.get_analyzed_email_ids')
    @patch('gmail.is_already_analyzed')
    @patch('gmail._fetch_email_details')
    @patch('gmail.list_message_ids')
    async def test_fetch_new_emails_filters_in_single_db_query(
        self, mock_list, mock_fetch_details, mock_is_analyzed, mock_get_analyzed_ids
    ):
        """When FETCH_BATCH=1, _fetch_new_emails calls get_analyzed_email_ids once, not is_already_analyzed N times."""
        mock_list.return_value = ([f'e_{i}' for i in range(50)], None)
        mock_fetch_details.side_effect = lambda ids, **kw: [{'id': mid, 'snippet': f'snip_{mid}'} for mid in ids]
        # Simulate that e_0 and e_1 are already analyzed
        mock_get_analyzed_ids.return_value = {'e_0', 'e_1'}

        from gmail import _fetch_new_emails
        with patch('gmail.FETCH_BATCH', 1):
            new_emails, skipped, fetched = await _fetch_new_emails(limit=50, user_id=1, user_email='test@test.com')

        assert fetched == 48
        assert skipped == 2
        assert len(new_emails) == 48
        # Called once in batch, never called sequentially
        mock_get_analyzed_ids.assert_called_once()
        mock_is_analyzed.assert_not_called()
        mock_fetch_details.assert_called_once()
        assert len(mock_fetch_details.call_args[0][0]) == 48

    @pytest.mark.asyncio
    @patch('gmail.get_analyzed_email_ids')
    @patch('gmail.is_already_analyzed')
    @patch('gmail._fetch_email_details')
    @patch('gmail.list_message_ids')
    async def test_fetch_new_emails_legacy_when_flag_off(
        self, mock_list, mock_fetch_details, mock_is_analyzed, mock_get_analyzed_ids
    ):
        """When FETCH_BATCH=0, _fetch_new_emails uses the sequential is_already_analyzed loop."""
        mock_list.return_value = ([f'e_{i}' for i in range(10)], None)
        mock_fetch_details.side_effect = lambda ids, **kw: [{'id': mid, 'snippet': f'snip_{mid}'} for mid in ids]
        mock_is_analyzed.return_value = False

        from gmail import _fetch_new_emails
        with patch('gmail.FETCH_BATCH', 0):
            new_emails, skipped, fetched = await _fetch_new_emails(limit=10, user_id=1, user_email='test@test.com')

        assert fetched == 10
        assert len(new_emails) == 10
        assert mock_is_analyzed.call_count == 10
        mock_get_analyzed_ids.assert_not_called()
        mock_fetch_details.assert_called_once()

    @pytest.mark.asyncio
    @patch('gmail.get_credentials')
    @patch('gmail.get_gmail_service')
    @patch('gmail._fetch_new_emails')
    @patch('gmail._get_email_bodies_batch')
    @patch('gmail.save_fetched_emails_bulk')
    async def test_fetch_only_pipeline_50_emails_2_batches_of_25(
        self, mock_save_bulk, mock_get_bodies_batch, mock_fetch_new,
        mock_get_svc, mock_get_creds
    ):
        """50 emails with FETCH_BATCH_SIZE=25 -> exactly 2 calls to _get_email_bodies_batch."""
        mock_get_svc.return_value = MagicMock()
        mock_get_creds.return_value = MagicMock()

        emails_50 = [
            {'id': f'email_{i}', 'snippet': f'snip_{i}', 'sender': 'a@b.com', 'subject': f'sub_{i}'}
            for i in range(50)
        ]
        mock_fetch_new.return_value = (emails_50, 0, 50)

        # Mock batch bodies return
        mock_get_bodies_batch.side_effect = lambda creds, ids: {mid: f'Body for {mid}' for mid in ids}

        from gmail import fetch_only_pipeline
        with patch('gmail.FETCH_BATCH', 1), \
             patch('gmail.FETCH_BATCH_SIZE', 25), \
             patch('gmail.FETCH_BATCH_PARALLEL', 2):

            events = []
            async for ev in fetch_only_pipeline(limit=50, user_id=1, user_email='test@test.com'):
                events.append(ev)

        # Verified: exactly 2 batch requests of 25
        assert mock_get_bodies_batch.call_count == 2
        batch_sizes = [len(call_args[0][1]) for call_args in mock_get_bodies_batch.call_args_list]
        assert batch_sizes == [25, 25]

        # Verified: save_fetched_emails_bulk was called for all 50 emails
        total_saved_rows = sum(len(c[0][1]) for c in mock_save_bulk.call_args_list)
        assert total_saved_rows == 50

        # Verified: completed event reported
        complete_events = [e for e in events if e.get('type') == 'complete']
        assert len(complete_events) == 1
        assert complete_events[0]['fetched'] == 50

    def test_save_fetched_emails_bulk_on_conflict(self, isolated_postgres_db):
        """save_fetched_emails_bulk inserts new rows and ignores conflicts without downgrade."""
        import database as db
        from database import save_fetched_emails_bulk, save_analyzed_email, get_analyzed_emails

        user_id = 992
        # Ensure test user exists to satisfy foreign key constraint
        conn = db._get_connection()
        try:
            cur = conn.cursor()
            db._execute(cur, "INSERT INTO users (user_id, gmail_address) VALUES (%s, 'batch_test@test.com') ON CONFLICT (user_id) DO NOTHING", (user_id,))
            conn.commit()
        finally:
            db._release_connection(conn)

        try:
            # Pre-insert an email with status='labeled' and scam_score=50
            save_analyzed_email(
                email_id="existing_labeled_123",
                user_id=user_id,
                label_id=None,
                scam_score=50,
                scam_indicators='["test"]',
                is_quarantined=0,
                snippet="Existing snippet",
                sender="existing@test.com",
                subject="Existing subject",
                status="labeled",
                body="Existing body",
            )

            # Bulk insert 2 rows: one new, one conflict
            rows = [
                {
                    "email_id": "existing_labeled_123",
                    "snippet": "Attempted overwrite snippet",
                    "sender": "existing@test.com",
                    "subject": "Existing subject",
                    "body": "Attempted overwrite body",
                    "received_at": "2026-10-11T02:57:00+00:00",
                },
                {
                    "email_id": "new_fetched_456",
                    "snippet": "New snippet",
                    "sender": "new@test.com",
                    "subject": "New subject",
                    "body": "New body",
                    "received_at": "2026-10-11T02:57:00+00:00",
                },
            ]

            save_fetched_emails_bulk(user_id=user_id, rows=rows)

            # Check existing row was NOT overwritten or downgraded
            all_emails = {e["email_id"]: e for e in get_analyzed_emails(user_id)}
            existing = all_emails["existing_labeled_123"]
            assert existing["status"] == "labeled"
            assert existing["scam_score"] == 50
            assert existing["snippet"] == "Existing snippet"
            # Verify received_at was safely backfilled on conflict without downgrade
            assert existing["received_at"] == "2026-10-11T02:57:00+00:00"

            # Check new row was inserted as 'fetched' with received_at
            new_row = all_emails["new_fetched_456"]
            assert new_row["status"] == "fetched"
            assert new_row["scam_score"] is None
            assert new_row["snippet"] == "New snippet"
            assert new_row["received_at"] == "2026-10-11T02:57:00+00:00"
        finally:
            conn = db._get_connection()
            try:
                cur = conn.cursor()
                db._execute(cur, "DELETE FROM analyzed_emails WHERE user_id = %s", (user_id,))
                db._execute(cur, "DELETE FROM users WHERE user_id = %s", (user_id,))
                conn.commit()
            finally:
                db._release_connection(conn)
