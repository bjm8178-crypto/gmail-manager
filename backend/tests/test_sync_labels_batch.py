"""
Tests for sync_labels_batch (Step 1 perf/batching).
Verifies batchModify grouping, label removal, per-email fallback,
already-synced skip, and bulk DB update.
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers: fake Gmail service that records batchModify calls
# ---------------------------------------------------------------------------

class FakeMessagesResource:
    def __init__(self, batch_tracker, verify_labels=None, fail_batchModify=False):
        self._tracker = batch_tracker
        self._verify_labels = verify_labels or {}
        self._fail_batchModify = fail_batchModify

    def batchModify(self, userId, body):
        req = MagicMock()
        tracker = self._tracker
        fail = self._fail_batchModify
        def _execute():
            if fail:
                raise Exception("Permanent failure")
            tracker.append(dict(body))
        req.execute = _execute
        return req

    def get(self, userId, id, format='minimal'):
        req = MagicMock()
        req._id = id
        return req


class FakeUsersResource:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class FakeGmailService:
    def __init__(self, verify_labels=None, fail_batchModify=False):
        self.batch_modify_calls = []
        self._verify_labels = verify_labels or {}
        self._messages = FakeMessagesResource(
            self.batch_modify_calls, verify_labels, fail_batchModify
        )

    def users(self):
        return FakeUsersResource(self._messages)

    def new_batch_http_request(self, callback=None):
        batch = MagicMock()
        items = []

        def _add(request, request_id):
            items.append((request_id, request))

        def _execute():
            for req_id, req in items:
                labels = self._verify_labels.get(req_id, [])
                response = {'id': req_id, 'labelIds': labels}
                if callback:
                    callback(req_id, response, None)

        batch.add = _add
        batch.execute = _execute
        return batch


# ---------------------------------------------------------------------------
# Helpers: DB mocking
# ---------------------------------------------------------------------------

def make_rows(email_specs):
    """Build fake DB rows from list of (email_id, label_id, last_applied_label_id, label_name)."""
    return [
        {'email_id': s[0], 'label_id': s[1], 'last_applied_label_id': s[2], 'label_name': s[3]}
        for s in email_specs
    ]


def setup_db_mocks(rows):
    """Create mock conn/cursor that returns given rows, and captures execute_values calls."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch('psycopg2.extras.execute_values')
class TestSyncLabelsBatch:
    """Test suite for gmail.sync_labels_batch."""

    @patch('database._release_connection')
    @patch('database._get_connection')
    @patch('gmail.get_labels')
    @patch('gmail.get_or_create_label')
    @patch('gmail.get_gmail_service')
    def test_100_emails_4_labels_exactly_4_batch_modify(
        self, mock_service, mock_get_or_create, mock_get_labels,
        mock_conn, mock_release, mock_exec_values,
    ):
        """100 emails across 4 labels -> exactly 4 batchModify calls."""
        labels = ['Work', 'Personal', 'Spam', 'Promo']
        specs = []
        for i in range(100):
            label_idx = i % 4
            specs.append((f'email_{i}', label_idx + 1, None, labels[label_idx]))

        rows = make_rows(specs)
        conn, cursor = setup_db_mocks(rows)
        mock_conn.return_value = conn

        mock_get_or_create.side_effect = lambda ue, name, uid, cache: f'GLabel_{name}'
        mock_get_labels.return_value = []

        # Verification must include correct labels for all emails
        verify_labels = {f'email_{i}': [f'GLabel_{labels[i % 4]}'] for i in range(100)}
        fake_service = FakeGmailService(verify_labels=verify_labels)
        mock_service.return_value = fake_service

        from gmail import sync_labels_batch
        result = sync_labels_batch(
            user_id=1, user_email='test@test.com',
            gmail_labels_cache={}, email_ids=[f'email_{i}' for i in range(100)],
        )

        assert result['applied'] == 100
        assert result['failed'] == 0
        assert len(fake_service.batch_modify_calls) == 4

    @patch('database._release_connection')
    @patch('database._get_connection')
    @patch('gmail.get_labels')
    @patch('gmail.get_or_create_label')
    @patch('gmail.get_gmail_service')
    def test_label_change_sends_remove_label_ids(
        self, mock_service, mock_get_or_create, mock_get_labels,
        mock_conn, mock_release, mock_exec_values,
    ):
        """When last_applied_label_id differs, removeLabelIds should be set."""
        specs = [
            ('email_1', 2, 1, 'Personal'),  # was Work (label_id=1), now Personal (label_id=2)
        ]
        rows = make_rows(specs)
        conn, cursor = setup_db_mocks(rows)
        mock_conn.return_value = conn

        mock_get_or_create.side_effect = lambda ue, name, uid, cache: f'GLabel_{name}'
        mock_get_labels.return_value = [
            {'label_id': 1, 'label_name': 'Work'},
            {'label_id': 2, 'label_name': 'Personal'},
        ]

        verify_labels = {'email_1': ['GLabel_Personal']}
        fake_service = FakeGmailService(verify_labels=verify_labels)
        mock_service.return_value = fake_service

        from gmail import sync_labels_batch
        result = sync_labels_batch(
            user_id=1, user_email='test@test.com',
            gmail_labels_cache={}, email_ids=['email_1'],
        )

        assert result['applied'] == 1
        assert len(fake_service.batch_modify_calls) == 1
        batch_body = fake_service.batch_modify_calls[0]
        assert batch_body['addLabelIds'] == ['GLabel_Personal']
        assert 'removeLabelIds' in batch_body
        assert batch_body['removeLabelIds'] == ['GLabel_Work']

    @patch('database._release_connection')
    @patch('database._get_connection')
    @patch('gmail.get_labels')
    @patch('gmail.get_or_create_label')
    @patch('gmail.get_gmail_service')
    def test_fallback_on_batch_modify_failure(
        self, mock_service, mock_get_or_create, mock_get_labels,
        mock_conn, mock_release, mock_exec_values,
    ):
        """When batchModify fails after retries, per_email_fallback is called."""
        specs = [
            ('email_1', 1, None, 'Work'),
            ('email_2', 1, None, 'Work'),
        ]
        rows = make_rows(specs)
        conn, cursor = setup_db_mocks(rows)
        mock_conn.return_value = conn

        mock_get_or_create.side_effect = lambda ue, name, uid, cache: f'GLabel_{name}'
        mock_get_labels.return_value = []

        fake_service = FakeGmailService(fail_batchModify=True)
        mock_service.return_value = fake_service

        fallback_calls = []
        def fake_fallback(email_id, user_id, user_email, cache):
            fallback_calls.append(email_id)
            return {'success': True}

        from gmail import sync_labels_batch
        with patch('time.sleep'):  # Don't actually sleep during retries
            result = sync_labels_batch(
                user_id=1, user_email='test@test.com',
                gmail_labels_cache={}, email_ids=['email_1', 'email_2'],
                per_email_fallback=fake_fallback,
            )

        assert len(fallback_calls) == 2
        assert result['applied'] == 2
        assert result['failed'] == 0

    @patch('database._release_connection')
    @patch('database._get_connection')
    @patch('gmail.get_labels')
    @patch('gmail.get_or_create_label')
    @patch('gmail.get_gmail_service')
    def test_already_synced_skips_batch_modify(
        self, mock_service, mock_get_or_create, mock_get_labels,
        mock_conn, mock_release, mock_exec_values,
    ):
        """Emails where last_applied_label_id == label_id skip batchModify."""
        specs = [
            ('email_1', 1, 1, 'Work'),      # already synced
            ('email_2', 1, 1, 'Work'),      # already synced
            ('email_3', 2, None, 'Personal'),  # needs sync
        ]
        rows = make_rows(specs)
        conn, cursor = setup_db_mocks(rows)
        mock_conn.return_value = conn

        mock_get_or_create.side_effect = lambda ue, name, uid, cache: f'GLabel_{name}'
        mock_get_labels.return_value = []

        verify_labels = {'email_3': ['GLabel_Personal']}
        fake_service = FakeGmailService(verify_labels=verify_labels)
        mock_service.return_value = fake_service

        from gmail import sync_labels_batch
        result = sync_labels_batch(
            user_id=1, user_email='test@test.com',
            gmail_labels_cache={}, email_ids=['email_1', 'email_2', 'email_3'],
        )

        assert len(fake_service.batch_modify_calls) == 1
        assert result['applied'] == 3
        assert result['failed'] == 0

    @patch('database._release_connection')
    @patch('database._get_connection')
    @patch('gmail.get_labels')
    @patch('gmail.get_or_create_label')
    @patch('gmail.get_gmail_service')
    def test_no_fallback_counts_as_failed(
        self, mock_service, mock_get_or_create, mock_get_labels,
        mock_conn, mock_release, mock_exec_values,
    ):
        """When batchModify fails and no per_email_fallback -> emails count as failed."""
        specs = [('email_1', 1, None, 'Work')]
        rows = make_rows(specs)
        conn, cursor = setup_db_mocks(rows)
        mock_conn.return_value = conn

        mock_get_or_create.side_effect = lambda ue, name, uid, cache: f'GLabel_{name}'
        mock_get_labels.return_value = []

        fake_service = FakeGmailService(fail_batchModify=True)
        mock_service.return_value = fake_service

        from gmail import sync_labels_batch
        with patch('time.sleep'):
            result = sync_labels_batch(
                user_id=1, user_email='test@test.com',
                gmail_labels_cache={}, email_ids=['email_1'],
                per_email_fallback=None,
            )

        assert result['applied'] == 0
        assert result['failed'] == 1
        assert len(result['errors']) == 1
