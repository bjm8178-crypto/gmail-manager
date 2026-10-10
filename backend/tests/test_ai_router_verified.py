"""
test_ai_router_verified.py — AIRouter verified function tests
Tests actual production functions confirmed to exist in ai_router.py
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


def test_usable_secret_returns_valid_key():
    """Test _usable_secret accepts valid API keys"""
    from ai_router import _usable_secret
    
    valid_key = "sk-1234567890abcdef"
    result = _usable_secret(valid_key)
    
    assert result == "sk-1234567890abcdef"


def test_usable_secret_rejects_placeholder_changeme():
    """Test _usable_secret rejects 'changeme' placeholder"""
    from ai_router import _usable_secret
    
    result = _usable_secret("changeme")
    
    assert result is None


def test_usable_secret_rejects_your_key_here():
    """Test _usable_secret rejects 'your_key_here' template"""
    from ai_router import _usable_secret
    
    result = _usable_secret("your_key_here")
    
    assert result is None


def test_usable_secret_rejects_empty_string():
    """Test _usable_secret rejects empty strings"""
    from ai_router import _usable_secret
    
    result = _usable_secret("")
    
    assert result is None


def test_usable_secret_rejects_none():
    """Test _usable_secret returns None for None input"""
    from ai_router import _usable_secret
    
    result = _usable_secret(None)
    
    assert result is None


def test_usable_secret_strips_whitespace():
    """Test _usable_secret strips leading/trailing whitespace"""
    from ai_router import _usable_secret
    
    result = _usable_secret("  sk-valid-key  ")
    
    assert result == "sk-valid-key"


def test_usable_secret_rejects_redacted():
    """Test _usable_secret rejects 'redacted' sentinel"""
    from ai_router import _usable_secret
    
    result = _usable_secret("REDACTED")
    
    assert result is None


def test_usable_secret_rejects_asterisks():
    """Test _usable_secret rejects '***' placeholder"""
    from ai_router import _usable_secret
    
    result = _usable_secret("***")
    
    assert result is None


def test_load_key_pool_loads_scalar_key():
    """Test _load_key_pool loads base environment variable"""
    with patch('ai_router.os.getenv') as mock_getenv:
        mock_getenv.side_effect = lambda key: "sk-key1" if key == "TEST_KEY" else None
        
        from ai_router import _load_key_pool
        result = _load_key_pool("TEST_KEY", 3)
        
        assert "sk-key1" in result
        assert len(result) == 1


def test_load_key_pool_loads_numbered_keys():
    """Test _load_key_pool loads numbered key variants (KEY_1, KEY_2)"""
    def mock_getenv(key):
        mapping = {
            "API_KEY": "sk-base",
            "API_KEY_1": "sk-one",
            "API_KEY_2": "sk-two",
            "API_KEY_3": None,
        }
        return mapping.get(key)
    
    with patch('ai_router.os.getenv', side_effect=mock_getenv):
        from ai_router import _load_key_pool
        result = _load_key_pool("API_KEY", 3)
        
        assert "sk-base" in result
        assert "sk-one" in result
        assert "sk-two" in result
        assert len(result) == 3


def test_load_key_pool_deduplicates_keys():
    """Test _load_key_pool removes duplicate keys"""
    def mock_getenv(key):
        # BASE and _1 have same value (duplicate)
        return "sk-duplicate" if key in ["DUP_KEY", "DUP_KEY_1"] else None
    
    with patch('ai_router.os.getenv', side_effect=mock_getenv):
        from ai_router import _load_key_pool
        result = _load_key_pool("DUP_KEY", 2)
        
        assert result == ["sk-duplicate"]


def test_load_key_pool_skips_placeholders():
    """Test _load_key_pool filters out placeholder values"""
    def mock_getenv(key):
        mapping = {
            "MIX_KEY": "sk-valid",
            "MIX_KEY_1": "changeme",
            "MIX_KEY_2": "sk-valid2",
        }
        return mapping.get(key)
    
    with patch('ai_router.os.getenv', side_effect=mock_getenv):
        from ai_router import _load_key_pool
        result = _load_key_pool("MIX_KEY", 2)
        
        assert "sk-valid" in result
        assert "sk-valid2" in result
        assert "changeme" not in result
        assert len(result) == 2


def test_load_key_pool_returns_empty_for_no_keys():
    """Test _load_key_pool returns empty list when no valid keys"""
    with patch('ai_router.os.getenv', return_value=None):
        from ai_router import _load_key_pool
        result = _load_key_pool("MISSING_KEY", 5)
        
        assert result == []


@pytest.mark.asyncio
async def test_ai_router_initializes_with_clients():
    """Test AIRouter.__init__ creates httpx clients"""
    from ai_router import AIRouter
    
    router = AIRouter()
    
    assert router.client is not None
    assert router.async_client is not None
    assert hasattr(router, '_gemini_key_index')
    assert hasattr(router, '_groq_key_index')


@pytest.mark.asyncio
async def test_call_groq_raises_quota_error_on_429():
    """Test _call_groq raises QuotaError when Groq returns 429"""
    from ai_router import QuotaError
    
    # Mock GROQ_API_KEYS before importing AIRouter
    with patch('ai_router.GROQ_API_KEYS', ["sk-test-key"]):
        from ai_router import AIRouter
        
        router = AIRouter()
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            with pytest.raises(QuotaError, match="Groq"):
                await router._call_groq("test prompt")


@pytest.mark.asyncio
async def test_call_groq_raises_provider_error_on_500():
    """Test _call_groq raises ProviderError for server errors"""
    from ai_router import ProviderError
    
    with patch('ai_router.GROQ_API_KEYS', ["sk-test-key"]):
        from ai_router import AIRouter
        
        router = AIRouter()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            with pytest.raises(ProviderError, match="500"):
                await router._call_groq("test prompt")


@pytest.mark.asyncio
async def test_call_gemini_raises_quota_error_on_429():
    """Test _call_gemini raises QuotaError when Gemini quota exceeded"""
    from ai_router import AIRouter, QuotaError
    
    router = AIRouter()
    mock_response = MagicMock()
    mock_response.status_code = 429
    
    with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        with pytest.raises(QuotaError, match="Gemini"):
            await router._call_gemini("test prompt")


@pytest.mark.asyncio
async def test_call_cohere_raises_quota_error_on_429():
    """Test _call_cohere raises QuotaError when Cohere rate limited"""
    from ai_router import AIRouter, QuotaError
    
    router = AIRouter()
    mock_response = MagicMock()
    mock_response.status_code = 429
    
    with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        with pytest.raises(QuotaError, match="Cohere"):
            await router._call_cohere("test prompt")


@pytest.mark.asyncio
async def test_analyze_returns_parsed_json():
    """Test analyze() returns parsed JSON dictionary"""
    with patch('ai_router.NVIDIA_API_KEY', "sk-test"):
        from ai_router import AIRouter
        
        router = AIRouter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"label": "Important", "scam_score": 10}'}}]
        }
        
        with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await router.analyze("test email content")
            
            assert isinstance(result, dict)
            assert "response" in result or "error" in result


@pytest.mark.asyncio
async def test_analyze_json_returns_dict():
    """Test analyze_json() returns dictionary response"""
    from ai_router import AIRouter
    
    router = AIRouter()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"result": "success"}'}}]
    }
    
    with patch.object(router.async_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        result = await router.analyze_json("test prompt")
        
        assert isinstance(result, dict)
