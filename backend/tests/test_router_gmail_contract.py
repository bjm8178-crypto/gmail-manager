"""Contract: the REAL v2_routing output must flow through gmail._analyze_one unchanged in meaning.

test_gmail_reliability.py mocks the router, so it cannot notice a status-vocabulary mismatch
('complete' from the router vs 'completed' stored/displayed). This test uses the real router.
"""
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def load_gmail():
    modules = {name: MagicMock() for name in ('auth', 'database', 'ml_inference')}
    spec = importlib.util.spec_from_file_location('gmail_contract_under_test', BACKEND / 'gmail.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


def load_real_router():
    deps = {
        'logger_setup': types.SimpleNamespace(get_logger=lambda _: Mock()),
        'predict': types.SimpleNamespace(predict_email=Mock()),
    }
    spec = importlib.util.spec_from_file_location('v2_routing_contract_under_test', BACKEND / 'v2_routing.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, deps):
        spec.loader.exec_module(module)
    module.V2_AVAILABLE = False  # AI-only path: deterministic, no model file needed
    return module


class RouterToGmailContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = load_gmail()
        self.gmail.is_already_analyzed.return_value = False
        self.gmail.get_label_id_by_name.return_value = 4
        self.db = MagicMock()
        self.router = load_real_router()
        self.security = types.ModuleType('security')
        self.security.extract_urls = MagicMock(return_value=[])
        # Phase 3: Mock scan_urls_batch (replaces scan_url)
        self.security.scan_urls_batch = AsyncMock(return_value={})
        self.security.scan_url = AsyncMock(return_value={'is_safe': 1, 'threat_type': None})  # Legacy, kept for compat
        self.ai = MagicMock()
        self.ai.analyze_json = AsyncMock(return_value={
            'data': {'label': 'Work', 'scam_score': 0, 'scam_indicators': [], 'reasoning': 'ordinary'},
            'provider_used': 'Gemini',
        })
        self.email = {'id': 'm1', 'body': '<p>hi</p>', 'subject': 'Hi', 'sender': 'a@example.test',
                      'received_at': '2024-01-01T00:00:00+00:00'}

    async def analyze(self):
        modules = {'database': self.db, 'security': self.security, 'v2_routing': self.router}
        with patch.dict(sys.modules, modules):
            await self.gmail._analyze_one(
                self.email, asyncio.Semaphore(1), self.ai, '{body}', 7, 'test@example.test',
                MagicMock(), MagicMock(), asyncio.Semaphore(1), ['Work', 'Finance'], {}, update_mode=True)
        return self.db.update_analyzed_email.call_args.kwargs

    async def test_fully_scanned_link_heavy_email_is_completed_not_partial(self):
        # The exact production case: 15 links, all scanned, valid AI score of 0.
        urls = [f'https://example.test/{i}' for i in range(15)]
        self.security.extract_urls.return_value = urls
        # Phase 3: scan_urls_batch returns dict[url -> result]
        self.security.scan_urls_batch.return_value = {
            url: {'url': url, 'is_safe': 1, 'threat_type': None, 'scan_failed': False}
            for url in urls
        }
        saved = await self.analyze()
        self.assertEqual(saved['urls_total'], 15)
        self.assertEqual(saved['urls_checked'], 15)
        self.assertEqual(saved['url_scan_status'], 'completed')
        self.assertEqual(saved['analysis_status'], 'completed')
        self.assertEqual(saved['category_status'], 'completed')
        self.assertEqual(saved['scam_score'], 0)

    async def test_more_links_than_cap_is_honestly_partial(self):
        urls = [f'https://example.test/{i}' for i in range(self.gmail.MAX_URLS_SCANNED + 5)]
        self.security.extract_urls.return_value = urls
        # Phase 3: Only the first MAX_URLS_SCANNED are passed to scan_urls_batch
        selected_urls = urls[:self.gmail.MAX_URLS_SCANNED]
        self.security.scan_urls_batch.return_value = {
            url: {'url': url, 'is_safe': 1, 'threat_type': None, 'scan_failed': False}
            for url in selected_urls
        }
        saved = await self.analyze()
        self.assertEqual(saved['urls_checked'], self.gmail.MAX_URLS_SCANNED)
        self.assertEqual(saved['url_scan_status'], 'partial')
        self.assertEqual(saved['analysis_status'], 'completed')

    async def test_failed_scan_downgrades_to_partial(self):
        urls = ['https://example.test/a', 'https://example.test/b']
        self.security.extract_urls.return_value = urls
        # Phase 3: Batch scan returns one success, one failure
        self.security.scan_urls_batch.return_value = {
            'https://example.test/a': {'url': 'https://example.test/a', 'is_safe': 1, 'threat_type': None, 'scan_failed': False},
            'https://example.test/b': {'url': 'https://example.test/b', 'is_safe': None, 'threat_type': None, 'scan_failed': True},
        }
        saved = await self.analyze()
        self.assertEqual(saved['url_scan_status'], 'partial')
        # Phase 4 Task 12: analysis_status='completed' iff score AND label exist (regardless of ML/URL)
        # This test has valid scam_score (from AI) and valid label_id (mocked as 4)
        # URL scan failure isolated to url_scan_status, does NOT affect analysis_status
        self.assertEqual(saved['analysis_status'], 'completed')  # Score + label exist


if __name__ == '__main__':
    unittest.main()
