"""Offline regressions. Gmail/AI/DB boundaries are mocked; no mailbox is accessed."""
import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def load_gmail():
    modules = {name: MagicMock() for name in ('auth', 'database', 'ml_inference')}
    spec = importlib.util.spec_from_file_location('gmail_under_test', BACKEND / 'gmail.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class GmailActionsTests(unittest.TestCase):
    def setUp(self):
        self.gmail = load_gmail()

    def test_apply_unavailable_raises(self):
        with patch.object(self.gmail, 'get_gmail_service', return_value=None):
            with self.assertRaises(RuntimeError):
                self.gmail.apply_label('test@example.test', 'm1', 'l1')

    def test_apply_api_failure_raises(self):
        service = MagicMock()
        service.users().messages().modify().execute.side_effect = RuntimeError('offline')
        with patch.object(self.gmail, 'get_gmail_service', return_value=service):
            with self.assertRaises(RuntimeError):
                self.gmail.apply_label('test@example.test', 'm1', 'l1')

    def test_apply_readback_must_contain_label(self):
        service = MagicMock()
        service.users().messages().get().execute.return_value = {'labelIds': []}
        with patch.object(self.gmail, 'get_gmail_service', return_value=service):
            with self.assertRaises(RuntimeError):
                self.gmail.apply_label('test@example.test', 'm1', 'l1')

    def test_apply_confirmed_returns_true(self):
        service = MagicMock()
        service.users().messages().get().execute.return_value = {'labelIds': ['l1']}
        with patch.object(self.gmail, 'get_gmail_service', return_value=service):
            self.assertTrue(self.gmail.apply_label('test@example.test', 'm1', 'l1'))

    def test_received_timestamp_uses_internal_date(self):
        email = self.gmail._parse_email_metadata('m1', {
            'internalDate': '1704067200000',
            'payload': {'headers': [{'name': 'subject', 'value': 'Receipt'}]},
        })
        self.assertEqual(email['received_at'], '2024-01-01T00:00:00+00:00')
        self.assertEqual(email['subject'], 'Receipt')


class AnalysisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = load_gmail()
        self.gmail.is_already_analyzed.return_value = False
        self.gmail.get_label_id_by_name.return_value = 12
        self.db = MagicMock()
        self.security = ModuleType('security')
        self.security.extract_urls = MagicMock(return_value=[])
        self.security.scan_url = AsyncMock(return_value={'is_safe': 1, 'threat_type': None})
        self.routing = ModuleType('v2_routing')
        self.routing.route_email_with_v2 = AsyncMock(return_value={
            'label': 'Finance', 'scam_score': 10, 'scam_indicators': [],
            'reasoning': 'Receipt from supplier', 'routing_decision': 'v2_auto_clear',
            'v2_score': 0.1, 'analysis_status': 'completed', 'category_status': 'completed',
            'provider_used': 'test',
        })
        self.email = {'id': 'm1', 'body': '<p>Invoice paid</p>', 'subject': 'Invoice',
                      'sender': 'supplier@example.test', 'received_at': '2024-01-01T00:00:00+00:00'}

    async def analyze(self):
        with patch.dict(sys.modules, {'database': self.db, 'security': self.security, 'v2_routing': self.routing}):
            return await self.gmail._analyze_one(
                self.email, asyncio.Semaphore(1), MagicMock(), '{body}',
                7, 'test@example.test', MagicMock(), MagicMock(), asyncio.Semaphore(1),
                ['Work', 'Finance'], {}, update_mode=True,
            )

    async def test_review_first_does_not_modify_gmail(self):
        with patch.object(self.gmail, 'get_or_create_label') as create, patch.object(self.gmail, 'apply_label') as apply:
            result = await self.analyze()
        self.assertEqual(result['status'], 'success')
        create.assert_not_called()
        apply.assert_not_called()

    async def test_evidence_and_account_are_persisted(self):
        await self.analyze()
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['user_id'], 7)
        self.assertEqual(saved['reasoning'], 'Receipt from supplier')
        self.assertEqual(saved['v2_score'], 0.1)
        self.assertEqual(saved['received_at'], self.email['received_at'])

    async def test_failure_is_not_zero_risk(self):
        self.routing.route_email_with_v2.side_effect = RuntimeError('No provider')
        result = await self.analyze()
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['scam_score'])
        self.assertIsNone(self.db.update_analyzed_email.call_args.kwargs['scam_score'])

    async def test_partial_link_coverage_is_persisted(self):
        self.security.extract_urls.return_value = [f'https://example.test/{i}' for i in range(24)]
        await self.analyze()
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['urls_total'], 24)
        self.assertEqual(saved['urls_checked'], 10)
        self.assertEqual(saved['url_scan_status'], 'partial')
        self.assertEqual(saved['analysis_status'], 'partial')

    async def test_threat_review_is_independent_of_category(self):
        self.routing.route_email_with_v2.return_value.update(scam_score=95)
        result = await self.analyze()
        self.assertEqual(result['label'], 'Finance')
        self.assertEqual(result['is_quarantined'], 1)

    async def test_local_model_fallback_records_provider_marker(self):
        self.routing.route_email_with_v2.return_value.update(provider_used=None)
        await self.analyze()
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['provider_used'], 'local_ml_v2')

    async def test_unknown_category_never_uses_first_label(self):
        self.routing.route_email_with_v2.return_value.update(label='Unknown', category_status='unavailable', analysis_status='partial')
        result = await self.analyze()
        self.assertEqual(result['label'], 'Unknown')
        self.assertIsNone(self.db.update_analyzed_email.call_args.kwargs['label_id'])


if __name__ == '__main__':
    unittest.main()
