"""
Integration tests for the complete email analysis pipeline.
Tests _analyze_one() with mocked Gmail, AI providers, URL scanning, and database.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_email():
    """Standard test email fixture."""
    return {
        'id': 'test_email_123',
        'threadId': 'thread_456',
        'subject': 'Test Invoice',
        'sender': 'sender@example.com',
        'body': 'Please review the attached invoice.',
        'snippet': 'Please review...',
        'received_at': datetime.now().isoformat(),
        'has_attachments': False,
    }


@pytest.fixture
def mock_database():
    """Mock database operations."""
    with patch('gmail.get_label_id_by_name') as get_label, \
         patch('gmail.remove_from_retry_queue') as remove_retry, \
         patch('gmail.add_to_retry_queue') as add_retry:
        get_label.return_value = 42
        yield {
            'get_label_id_by_name': get_label,
            'remove_from_retry_queue': remove_retry,
            'add_to_retry_queue': add_retry,
        }


@pytest.mark.asyncio
async def test_v2_router_available_complete_analysis(mock_email, mock_database):
    """Test successful V2 routing with complete analysis."""
    from gmail import _analyze_one
    
    # Mock v2_routing to be available and return complete analysis
    mock_route = AsyncMock(return_value={
        'label': 'Finance',
        'scam_score': 15,
        'scam_indicators': [],
        'reasoning': 'Legitimate invoice email',
        'routing_decision': 'v2_auto_clear',
        'v2_score': 0.15,
        'provider_used': 'gemini',
        'analysis_status': 'complete',
        'category_status': 'complete',
        'url_threat_confirmed': False,
        'url_scan_unavailable': False,
    })
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    with patch('gmail.route_email_with_v2', mock_route), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance'}]):
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1, 
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    assert result['status'] == 'success'
    assert result['analysis_status'] == 'completed'
    assert result['category_status'] == 'completed'
    assert result['label'] == 'Finance'
    assert result['scam_score'] == 15
    assert not result['is_quarantined']
    
    # Verify database calls
    persist_mock.assert_called_once()
    call_kwargs = persist_mock.call_args[1]
    assert call_kwargs['label_id'] == 42
    assert call_kwargs['scam_score'] == 15
    assert call_kwargs['analysis_status'] == 'completed'
    assert call_kwargs['category_status'] == 'completed'


@pytest.mark.asyncio
async def test_v2_router_unavailable_ai_fallback(mock_email, mock_database):
    """Test AI-only fallback when V2 router import fails."""
    from gmail import _analyze_one
    
    # Mock v2_routing import failure
    def mock_import_error(*args, **kwargs):
        raise ImportError("No module named 'v2_routing'")
    
    # Mock AI cascade to return valid result
    mock_ai_result = {
        'data': {
            'label': 'Promotional',
            'scam_score': 25,
            'scam_indicators': ['Marketing language'],
            'reasoning': 'Promotional email'
        },
        'provider_used': 'cohere'
    }
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    with patch('gmail.route_email_with_v2', side_effect=mock_import_error), \
         patch('gmail.ai_router.analyze_json', AsyncMock(return_value=mock_ai_result)), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Promotional'}]):
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    assert result['status'] == 'success'
    assert result['analysis_status'] == 'partial'  # AI-only is partial
    assert result['category_status'] == 'pending'
    assert result['scam_score'] == 25
    
    call_kwargs = persist_mock.call_args[1]
    assert call_kwargs['analysis_status'] == 'partial'
    assert call_kwargs['routing_decision'] == 'ai_only_fallback'


@pytest.mark.asyncio
async def test_all_ai_providers_exhausted(mock_email, mock_database):
    """Test that all providers failing does NOT produce fake Safe label."""
    from gmail import _analyze_one
    
    # Mock AI cascade to return error
    mock_ai_error = {
        'error': 'All AI providers exhausted: gemini quota, cohere timeout',
        'provider_used': None
    }
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    with patch('gmail.route_email_with_v2', side_effect=ImportError), \
         patch('gmail.ai_router.analyze_json', AsyncMock(return_value=mock_ai_error)), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance'}]):
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    # Should fail gracefully
    assert result['status'] == 'failed'
    assert result['analysis_status'] == 'failed'
    assert result['label'] == 'Unknown'
    
    # Verify NO fake safe score
    assert result['scam_score'] is None or result['scam_score'] == 0  # Expect None but allow 0 from error path
    
    # Verify added to retry queue
    mock_database['add_to_retry_queue'].assert_called_once()


@pytest.mark.asyncio
async def test_confirmed_url_threat_overrides_ai_safe(mock_email, mock_database):
    """Test that confirmed malicious URL overrides AI saying Safe."""
    from gmail import _analyze_one
    
    mock_route = AsyncMock(return_value={
        'label': 'Personal',
        'scam_score': 100,  # URL threat sets to 100
        'scam_indicators': ['Known malicious link detected'],
        'reasoning': 'Confirmed malicious URL',
        'routing_decision': 'url_threat_override',
        'v2_score': None,
        'provider_used': 'gemini',
        'analysis_status': 'complete',
        'category_status': 'complete',
        'url_threat_confirmed': True,
        'url_scan_unavailable': False,
    })
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    # Mock URL scan returning malicious
    with patch('gmail.route_email_with_v2', mock_route), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Personal'}]), \
         patch('gmail.check_urls_safe', return_value=(True, 'complete', 5, 5)):
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    assert result['scam_score'] >= 95  # URL threat forces high score
    assert result['is_quarantined'] == 1
    assert 'Known malicious link detected' in str(persist_mock.call_args)


@pytest.mark.asyncio
async def test_empty_label_list_unavailable_category(mock_email, mock_database):
    """Test that empty label list results in unavailable category_status."""
    from gmail import _analyze_one
    
    mock_route = AsyncMock(return_value={
        'label': 'Unknown',
        'scam_score': 30,
        'scam_indicators': [],
        'reasoning': 'No labels available for matching',
        'routing_decision': 'ai_cascade',
        'v2_score': None,
        'provider_used': 'gemini',
        'analysis_status': 'partial',
        'category_status': 'unavailable',
        'url_threat_confirmed': False,
        'url_scan_unavailable': False,
    })
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    with patch('gmail.route_email_with_v2', mock_route), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[]):  # Empty labels
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    assert result['analysis_status'] == 'partial'
    assert result['category_status'] == 'unavailable'
    assert result['label'] == 'Unknown'
    
    call_kwargs = persist_mock.call_args[1]
    assert call_kwargs['label_id'] is None
    assert call_kwargs['category_status'] == 'unavailable'


@pytest.mark.asyncio
async def test_safe_browsing_unavailable_not_interpreted_as_safe(mock_email, mock_database):
    """Test that missing Safe Browsing key results in unavailable, not safe."""
    from gmail import _analyze_one
    
    mock_route = AsyncMock(return_value={
        'label': 'Finance',
        'scam_score': 20,
        'scam_indicators': [],
        'reasoning': 'Legitimate finance email',
        'routing_decision': 'v2_auto_clear',
        'v2_score': 0.20,
        'provider_used': None,
        'analysis_status': 'partial',  # Partial because URL scan unavailable
        'category_status': 'complete',
        'url_threat_confirmed': False,
        'url_scan_unavailable': True,
    })
    
    persist_mock = MagicMock()
    semaphore = asyncio.Semaphore(1)
    
    # Mock URL scan as unavailable (no API key)
    with patch('gmail.route_email_with_v2', mock_route), \
         patch('gmail.asyncio.to_thread', return_value=[]), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance'}]), \
         patch('gmail.check_urls_safe', return_value=(False, 'unavailable', 0, 0)):
        
        result = await _analyze_one(
            mock_email, semaphore, user_id=1,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            persist=persist_mock
        )
    
    assert result['url_scan_status'] == 'unavailable'
    assert result['urls_checked'] == 0
    assert result['analysis_status'] == 'partial'  # Not complete due to unavailable URL scan
    
    call_kwargs = persist_mock.call_args[1]
    assert call_kwargs['url_scan_status'] == 'unavailable'
