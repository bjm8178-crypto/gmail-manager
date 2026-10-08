"""Offline routing/security regression tests: no model, secrets, DB or API access."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

BACKEND = Path(__file__).resolve().parents[1]


def load_module(name):
    dependencies = {
        'logger_setup': types.SimpleNamespace(get_logger=lambda _: Mock()),
        'predict': types.SimpleNamespace(predict_email=Mock()),
        'dotenv': types.SimpleNamespace(load_dotenv=lambda: None),
        'httpx': types.SimpleNamespace(AsyncClient=Mock, TimeoutException=type('TimeoutException', (Exception,), {}), HTTPStatusError=type('HTTPStatusError', (Exception,), {})),
    }
    spec = importlib.util.spec_from_file_location('_test_' + name, BACKEND / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, dependencies):
        spec.loader.exec_module(module)
    return module


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = load_module('v2_routing')
        self.router.V2_AVAILABLE = True
        self.router.predict_email = Mock(return_value={'probabilities': {'phishing': 0.1}})
        self.ai = AsyncMock(return_value={'data': {'label': 'Work', 'scam_score': 1, 'scam_indicators': [], 'reasoning': 'ordinary'}, 'provider_used': 'test'})

    async def route(self, **kwargs):
        return await self.router.route_email_with_v2('email', 'subject', 'sender', 'body', 'snippet', self.ai, '', available_label_names=['Finance', 'Work', 'Spam'], **kwargs)

    async def test_ai_invalid_shapes_cannot_create_verdicts(self):
        self.router.V2_AVAILABLE = False
        for payload in (None, [], 'text', {'data': []}, {'data': 'text'}, {'data': {'label': 'Work'}},
                        {'data': {'label': 'Work', 'scam_score': 5, 'scam_indicators': 'bad'}},
                        {'data': {'label': 'Work', 'scam_score': 5, 'scam_indicators': [1]}},
                        {'data': {'label': 'Work', 'scam_score': 5, 'reasoning': []}}):
            with self.subTest(payload=payload):
                self.ai.return_value = payload
                with self.assertRaises(self.router.AnalysisUnavailableError):
                    await self.route()
                malicious = await self.route(url_threat_confirmed=True)
                self.assertEqual(malicious['scam_score'], 100)

    async def test_invalid_ai_numbers_are_not_coerced_clamped_or_defaulted(self):
        self.router.V2_AVAILABLE = False
        for score in (None, True, '12', float('nan'), float('inf'), -1, 101, {}, []):
            with self.subTest(score=score):
                self.ai.return_value = {'data': {'label': 'Work', 'scam_score': score}}
                with self.assertRaises(self.router.AnalysisUnavailableError) as caught:
                    await self.route()
                self.assertIsNone(caught.exception.result['scam_score'])

    async def test_invalid_model_probabilities_fall_back_to_valid_ai(self):
        for score in (True, '0.1', float('nan'), float('inf'), -1, 2, None):
            with self.subTest(score=score):
                self.router.predict_email.return_value = {'probabilities': {'phishing': score}}
                result = await self.route()
                self.assertEqual(result['scam_score'], 1)
                self.assertIsNone(result['v2_score'])
                self.assertEqual(result['routing_decision'], 'ai_cascade')

    async def test_category_validation_and_canonicalization(self):
        for label, expected in ((' work ', 'Work'), ('Invented', 'Unknown'), ([], 'Unknown'), (None, 'Unknown')):
            with self.subTest(label=label):
                self.ai.return_value = {'data': {'label': label, 'scam_score': 1}}
                result = await self.route()
                self.assertEqual(result['label'], expected)
                self.assertEqual(result['category_status'], 'complete' if expected == 'Work' else 'unavailable')

    async def test_unavailable_analysis_raises_with_nullable_risk(self):
        self.router.V2_AVAILABLE = False
        self.ai.return_value = {'data': None}
        try:
            await self.route()
        except Exception as exc:
            self.assertEqual(type(exc).__name__, 'AnalysisUnavailableError')
            self.assertIsNone(exc.result['scam_score'])
            self.assertEqual(exc.result['analysis_status'], 'unavailable')
            self.assertEqual(exc.result['label'], 'Unknown')
        else:
            self.fail('Unavailable providers/model must not return a successful result')

    async def test_provider_exception_cannot_erase_malicious_evidence(self):
        self.router.V2_AVAILABLE = False
        self.ai.side_effect = RuntimeError('provider down')
        result = await self.route(url_threat_confirmed=True, url_scan_unavailable=True)
        self.assertEqual(result['scam_score'], 100)
        self.assertEqual(result['analysis_status'], 'partial')
        self.assertTrue(result['url_threat_confirmed'])
        self.assertIn('Confirmed malicious URL', result['scam_indicators'])

    async def test_category_is_independent_of_model_and_url_verdict(self):
        for score in (0.1, 0.6, 0.99):
            for malicious in (False, True):
                with self.subTest(score=score, malicious=malicious):
                    self.router.predict_email.return_value = {'probabilities': {'phishing': score}}
                    result = await self.route(url_threat_confirmed=malicious)
                    self.assertEqual(result['label'], 'Work')
                    self.assertEqual(result['category_status'], 'complete')

    async def test_missing_category_is_unknown_never_first_label_or_spam(self):
        self.ai.return_value = {'data': None}
        for score in (0.1, 0.6, 0.99):
            with self.subTest(score=score):
                self.router.predict_email.return_value = {'probabilities': {'phishing': score}}
                result = await self.route()
                self.assertEqual(result['label'], 'Unknown')
                self.assertEqual(result['category_status'], 'unavailable')
                self.assertEqual(result['analysis_status'], 'partial')
                self.assertIsNotNone(result['scam_score'])

    async def test_confirmed_url_overrides_every_model_band_and_ai(self):
        for score in (0.1, 0.6, 0.99):
            with self.subTest(score=score):
                self.router.predict_email.return_value = {'probabilities': {'phishing': score}}
                result = await self.route(url_threat_confirmed=True)
                self.assertEqual(result['scam_score'], 100)
                self.assertIn('Confirmed malicious URL', result['scam_indicators'])
                self.assertEqual(result['routing_decision'], 'url_threat_override')


if __name__ == '__main__':
    unittest.main()
