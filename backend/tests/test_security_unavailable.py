"""Regression tests for security.py unavailable states.

Ensures that missing/failed scans are never represented as safe verdicts.
"""
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import sys
import types
import importlib.util


BACKEND = Path(__file__).resolve().parents[1]


def load_security_module():
    """Load security.py with mocked dependencies."""
    dependencies = {
        'logger_setup': types.SimpleNamespace(get_logger=lambda _: Mock()),
        'dotenv': types.SimpleNamespace(load_dotenv=lambda: None),
        'httpx': types.SimpleNamespace(
            AsyncClient=Mock,
            TimeoutException=type('TimeoutException', (Exception,), {}),
            HTTPStatusError=type('HTTPStatusError', (Exception,), {})
        ),
        'database': types.SimpleNamespace(
            get_cached_url=lambda url: None,
            save_url_result=Mock()
        ),
    }
    
    spec = importlib.util.spec_from_file_location('_test_security', BACKEND / 'security.py')
    module = importlib.util.module_from_spec(spec)
    
    with patch.dict(sys.modules, dependencies):
        spec.loader.exec_module(module)
    
    return module


class SafeBrowsingUnavailableTests(unittest.IsolatedAsyncioTestCase):
    """Test that unavailable scans are never represented as safe."""
    
    async def test_missing_api_key_returns_unavailable_not_safe(self):
        """When SAFE_BROWSING_KEY is missing, return unavailable verdict, not safe."""
        security = load_security_module()
        
        # Simulate missing API key
        security.SAFE_BROWSING_KEY = None
        
        mock_client = AsyncMock()
        mock_semaphore = asyncio.Semaphore(1)
        
        result = await security.scan_url(
            url="https://example.com",
            email_id="test123",
            client=mock_client,
            semaphore=mock_semaphore
        )
        
        # CRITICAL: Must be None (unavailable), never 1 (safe)
        self.assertIsNone(result['is_safe'], 
            "Missing API key must return is_safe=None, not 1 (safe)")
        
        # Must indicate unavailable state
        self.assertIn('scan_failed', result)
        self.assertTrue(result.get('scan_failed') or result.get('verdict') == 'unavailable',
            "Result must indicate scan was unavailable")
        
        # Must NOT be cached as safe
        # The function should not even attempt to cache when unavailable
        # (Result has scan_failed=True and is_safe=None)
    
    async def test_placeholder_api_key_returns_unavailable(self):
        """Placeholder key 'your_key_here' should also return unavailable."""
        security = load_security_module()
        
        security.SAFE_BROWSING_KEY = "your_key_here"
        
        mock_client = AsyncMock()
        mock_semaphore = asyncio.Semaphore(1)
        
        result = await security.scan_url(
            url="https://example.com",
            email_id="test123",
            client=mock_client,
            semaphore=mock_semaphore
        )
        
        self.assertIsNone(result['is_safe'],
            "Placeholder API key must return is_safe=None, not 1")
    
    async def test_api_timeout_returns_unavailable_not_safe(self):
        """API timeout should return unavailable, not safe."""
        security = load_security_module()
        
        security.SAFE_BROWSING_KEY = "valid-key-123"
        
        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError()
        mock_semaphore = asyncio.Semaphore(1)
        
        result = await security.scan_url(
            url="https://example.com",
            email_id="test123",
            client=mock_client,
            semaphore=mock_semaphore
        )
        
        # Timeout = scan failed, must be None
        self.assertIsNone(result['is_safe'],
            "Timeout must return is_safe=None, not default to safe")
        self.assertTrue(result.get('scan_failed', False))
    
    async def test_api_rate_limit_returns_unavailable(self):
        """HTTP 429 rate limit should return unavailable."""
        security = load_security_module()
        
        security.SAFE_BROWSING_KEY = "valid-key-123"
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Quota exceeded"
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_semaphore = asyncio.Semaphore(1)
        
        result = await security.scan_url(
            url="https://example.com",
            email_id="test123",
            client=mock_client,
            semaphore=mock_semaphore
        )
        
        self.assertIsNone(result['is_safe'],
            "Rate limit must return is_safe=None, not safe or threat")
        self.assertTrue(result.get('scan_failed', False))


if __name__ == '__main__':
    unittest.main()
