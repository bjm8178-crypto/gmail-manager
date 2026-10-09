"""Local smoke tests for analyze_email with mocked dependencies."""
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
    """Load gmail.py with all external dependencies mocked."""
    modules = {name: MagicMock() for name in ('auth', 'database', 'ml_inference')}
    spec = importlib.util.spec_from_file_location('gmail_under_test', BACKEND / 'gmail.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class AnalyzeEmailSmokeTests(unittest.IsolatedAsyncioTestCase):
    """Test one fake email with two URLs through analyze_email."""

    def setUp(self):
        self.gmail = load_gmail()
        self.gmail.is_already_analyzed.return_value = False
        self.gmail.get_label_id_by_name.return_value = 12
        self.db = MagicMock()
        
        # Set up security module
        self.security = ModuleType('security')
        self.security.extract_urls = MagicMock(return_value=[
            'https://example.test/link1',
            'https://example.test/link2',
        ])
        
        # Set up routing module
        self.routing = ModuleType('v2_routing')
        
        # Test email with two URLs
        self.email = {
            'id': 'test_email_001',
            'body': '<p>Check out <a href="https://example.test/link1">link1</a> and <a href="https://example.test/link2">link2</a></p>',
            'subject': 'Test Email',
            'sender': 'sender@example.test',
            'received_at': '2024-01-01T00:00:00+00:00',
            'snippet': 'Check out link1 and link2',
        }

    async def analyze(self, scan_url_mock, routing_mock):
        """Helper to run _analyze_one with mocked scan_url and routing."""
        self.security.scan_url = scan_url_mock
        self.routing.route_email_with_v2 = routing_mock
        
        with patch.dict(sys.modules, {'database': self.db, 'security': self.security, 'v2_routing': self.routing}):
            return await self.gmail._analyze_one(
                self.email,
                asyncio.Semaphore(1),
                MagicMock(),
                '{body}',
                7,
                'test@example.test',
                MagicMock(),
                MagicMock(),
                asyncio.Semaphore(1),
                ['Work', 'Finance'],
                {},
                update_mode=True,
            )

    async def test_both_urls_safe_with_valid_routing_completes(self):
        """Case 1: scan_url is_safe=1 for both URLs + valid routing → analysis_status completed."""
        scan_url_mock = AsyncMock(return_value={'is_safe': 1, 'threat_type': None})
        routing_mock = AsyncMock(return_value={
            'label': 'Finance',
            'scam_score': 10,
            'scam_indicators': [],
            'reasoning': 'Valid email',
            'routing_decision': 'v2_auto_clear',
            'v2_score': 0.1,
            'analysis_status': 'completed',
            'category_status': 'completed',
            'provider_used': 'test',
        })

        result = await self.analyze(scan_url_mock, routing_mock)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['analysis_status'], 'completed')
        self.assertEqual(result['url_scan_status'], 'completed')
        self.assertEqual(result['urls_total'], 2)
        self.assertEqual(result['urls_checked'], 2)
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['analysis_status'], 'completed')
        self.assertEqual(saved['url_scan_status'], 'completed')

    async def test_scan_url_failure_results_in_partial_and_unavailable(self):
        """Case 2: scan_url scan_failed=True → partial + url_scan_status unavailable."""
        scan_url_mock = AsyncMock(return_value={'scan_failed': True, 'is_safe': None, 'reason': 'api_error'})
        routing_mock = AsyncMock(return_value={
            'label': 'Work',
            'scam_score': 20,
            'scam_indicators': [],
            'reasoning': 'Business email',
            'routing_decision': 'v2_auto_clear',
            'v2_score': 0.2,
            'analysis_status': 'completed',
            'category_status': 'completed',
            'provider_used': 'test',
        })

        result = await self.analyze(scan_url_mock, routing_mock)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['analysis_status'], 'partial')
        self.assertEqual(result['url_scan_status'], 'unavailable')
        self.assertEqual(result['urls_total'], 2)
        self.assertEqual(result['urls_checked'], 0)
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['analysis_status'], 'partial')
        self.assertEqual(saved['url_scan_status'], 'unavailable')

    async def test_routing_exception_results_in_failed_status(self):
        """Case 3: routing exception → analysis_status failed."""
        scan_url_mock = AsyncMock(return_value={'is_safe': 1, 'threat_type': None})
        routing_mock = AsyncMock(side_effect=RuntimeError('Routing service unavailable'))

        result = await self.analyze(scan_url_mock, routing_mock)

        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['analysis_status'], 'failed')
        self.assertIsNone(result['scam_score'])
        saved = self.db.update_analyzed_email.call_args.kwargs
        self.assertEqual(saved['analysis_status'], 'failed')
        self.assertEqual(saved['category_status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
