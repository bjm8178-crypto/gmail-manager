"""
Integration tests for the complete email analysis pipeline.
Tests _analyze_one() with realistic mocking of external dependencies.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_email():
    """Standard test email fixture matching Gmail API format."""
    return {
        'id': 'test_email_123',
        'threadId': 'thread_456',
        'internalDate': '1696896000000',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Test Invoice'},
                {'name': 'From', 'value': 'sender@example.com'},
            ],
            'body': {'data': 'UGxlYXNlIHJldmlldyB0aGUgYXR0YWNoZWQgaW52b2ljZSBhdCBodHRwczovL2V4YW1wbGUuY29tL2ludm9pY2U='}  # base64: "Please review the attached invoice at https://example.com/invoice"
        },
        'snippet': 'Please review...',
    }


@pytest.mark.asyncio
async def test_v2_router_complete_analysis(mock_email):
    """Test successful V2 routing with complete analysis."""
    from gmail import _analyze_one
    
    # Mock v2_routing to return complete analysis
    mock_routed = {
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
    }
    
    # Mock dependencies at their actual import locations
    with patch('v2_routing.route_email_with_v2', new_callable=AsyncMock) as mock_v2, \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance', 'label_id': 42}]), \
         patch('gmail.get_label_id_by_name', return_value=42), \
         patch('gmail.is_already_analyzed', return_value=False), \
         patch('gmail.save_analyzed_email') as mock_save, \
         patch('gmail.remove_from_retry_queue'), \
         patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Email body text'), \
         patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': 1, 'threat_type': None}), \
         patch('gmail.get_gmail_service', return_value=MagicMock()):
        
        mock_v2.return_value = mock_routed
        
        # Create mock dependencies matching actual signature
        mock_ai_router = MagicMock()
        mock_semaphore = asyncio.Semaphore(1)
        mock_url_semaphore = asyncio.Semaphore(5)
        mock_url_client = MagicMock()
        
        result = await _analyze_one(
            email=mock_email,
            semaphore=mock_semaphore,
            ai_router=mock_ai_router,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            user_id=1,
            user_email='test@example.com',
            service=MagicMock(),
            url_client=mock_url_client,
            url_semaphore=mock_url_semaphore,
            available_label_names=['Finance', 'Personal', 'Spam'],
            gmail_labels_cache={},
            update_mode=False
        )
        
        # Verify result structure
        assert result['status'] == 'success'
        assert result['analysis_status'] == 'completed'  # 'complete' mapped to 'completed'
        assert result['category_status'] == 'completed'
        assert result['label'] == 'Finance'
        assert result['scam_score'] == 15
        assert result['is_quarantined'] == 0  # Low score, no URL threat
        
        # Verify database save was called
        assert mock_save.called


@pytest.mark.asyncio
async def test_v2_router_unavailable_ai_fallback(mock_email):
    """Test AI-only fallback when V2 router is unavailable."""
    import sys
    from gmail import _analyze_one
    
    # Mock AI cascade response
    mock_ai_result = {
        'data': {
            'label': 'Promotional',
            'scam_score': 25,
            'scam_indicators': ['Marketing language'],
            'reasoning': 'Promotional email'
        },
        'provider_used': 'cohere'
    }
    
    # Remove v2_routing from sys.modules to force import failure
    v2_routing_backup = sys.modules.pop('v2_routing', None)
    
    try:
        with patch.dict('sys.modules', {'v2_routing': None}), \
             patch('gmail.get_labels', return_value=[{'label_name': 'Promotional', 'label_id': 43}]), \
             patch('gmail.get_label_id_by_name', return_value=43), \
             patch('gmail.is_already_analyzed', return_value=False), \
             patch('gmail.save_analyzed_email') as mock_save, \
             patch('gmail.remove_from_retry_queue'), \
             patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Email body'), \
             patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': 1}), \
             patch('gmail.get_gmail_service', return_value=MagicMock()):
            
            mock_ai_router = MagicMock()
            mock_ai_router.analyze_json = AsyncMock(return_value=mock_ai_result)
            mock_semaphore = asyncio.Semaphore(1)
            
            result = await _analyze_one(
                email=mock_email,
                semaphore=mock_semaphore,
                ai_router=mock_ai_router,
                classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
                user_id=1,
                user_email='test@example.com',
                service=MagicMock(),
                url_client=MagicMock(),
                url_semaphore=asyncio.Semaphore(5),
                available_label_names=['Promotional', 'Spam'],
                gmail_labels_cache={},
                update_mode=False
            )
            
            assert result['status'] == 'success'
            assert result['analysis_status'] == 'partial'  # AI-only fallback is partial
            assert result['scam_score'] == 25
            
            # Verify AI fallback was used
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs['routing_decision'] == 'ai_only_fallback'
    finally:
        # Restore v2_routing module if it was present
        if v2_routing_backup is not None:
            sys.modules['v2_routing'] = v2_routing_backup


@pytest.mark.asyncio
async def test_url_threat_overrides_low_score(mock_email):
    """Test that confirmed malicious URL overrides low AI score."""
    from gmail import _analyze_one
    
    mock_routed = {
        'label': 'Personal',
        'scam_score': 20,  # Low initial score
        'scam_indicators': [],
        'reasoning': 'Normal email',
        'routing_decision': 'v2_auto_clear',
        'v2_score': 0.20,
        'provider_used': 'gemini',
        'analysis_status': 'complete',
        'category_status': 'complete',
        'url_threat_confirmed': False,
        'url_scan_unavailable': False,
    }
    
    with patch('v2_routing.route_email_with_v2', new_callable=AsyncMock, return_value=mock_routed), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Personal', 'label_id': 44}]), \
         patch('gmail.get_label_id_by_name', return_value=44), \
         patch('gmail.is_already_analyzed', return_value=False), \
         patch('gmail.save_analyzed_email') as mock_save, \
         patch('gmail.remove_from_retry_queue'), \
         patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Please review the invoice at https://malicious-site.example.com/phishing'), \
         patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': 0, 'threat_type': 'MALWARE'}), \
         patch('gmail.get_gmail_service', return_value=MagicMock()):
        
        mock_ai_router = MagicMock()
        
        result = await _analyze_one(
            email=mock_email,
            semaphore=asyncio.Semaphore(1),
            ai_router=mock_ai_router,
            classification_prompt="Test {subject} {sender} {body} {url_threat_confirmed} {url_scan_unavailable} {available_labels}",
            user_id=1,
            user_email='test@example.com',
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=asyncio.Semaphore(5),
            available_label_names=['Personal'],
            gmail_labels_cache={},
            update_mode=False
        )
        
        # URL threat should boost score to at least 95
        assert result['scam_score'] >= 95
        assert result['is_quarantined'] == 1  # URL threat → quarantine
        
        # Verify malicious indicator was added
        call_kwargs = mock_save.call_args[1]
        indicators = call_kwargs['scam_indicators']
        assert 'Known malicious link detected' in indicators


@pytest.mark.asyncio
async def test_empty_label_list_unavailable_category(mock_email):
    """Test that empty label list results in unavailable category_status."""
    from gmail import _analyze_one
    
    mock_routed = {
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
    }
    
    with patch('v2_routing.route_email_with_v2', new_callable=AsyncMock, return_value=mock_routed), \
         patch('gmail.get_labels', return_value=[]), \
         patch('gmail.get_label_id_by_name', return_value=None), \
         patch('gmail.is_already_analyzed', return_value=False), \
         patch('gmail.save_analyzed_email') as mock_save, \
         patch('gmail.remove_from_retry_queue'), \
         patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Email body'), \
         patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': 1}), \
         patch('gmail.get_gmail_service', return_value=MagicMock()):
        
        result = await _analyze_one(
            email=mock_email,
            semaphore=asyncio.Semaphore(1),
            ai_router=MagicMock(),
            classification_prompt="Test {subject}",
            user_id=1,
            user_email='test@example.com',
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=asyncio.Semaphore(5),
            available_label_names=[],  # No labels
            gmail_labels_cache={},
            update_mode=False
        )
        
        assert result['analysis_status'] == 'partial'
        assert result['category_status'] == 'unavailable'
        assert result['label'] == 'Unknown'
        
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs['label_id'] is None


@pytest.mark.asyncio
async def test_safe_browsing_unavailable_reported_correctly(mock_email):
    """Test that missing Safe Browsing reports unavailable, not safe."""
    from gmail import _analyze_one
    
    mock_routed = {
        'label': 'Finance',
        'scam_score': 20,
        'scam_indicators': [],
        'reasoning': 'Legitimate email',
        'routing_decision': 'v2_auto_clear',
        'v2_score': 0.20,
        'provider_used': 'gemini',
        'analysis_status': 'complete',
        'category_status': 'complete',
        'url_threat_confirmed': False,
        'url_scan_unavailable': False,
    }
    
    with patch('v2_routing.route_email_with_v2', new_callable=AsyncMock, return_value=mock_routed), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance', 'label_id': 42}]), \
         patch('gmail.get_label_id_by_name', return_value=42), \
         patch('gmail.is_already_analyzed', return_value=False), \
         patch('gmail.save_analyzed_email') as mock_save, \
         patch('gmail.remove_from_retry_queue'), \
         patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Check this link: https://example.com/invoice'), \
         patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': None, 'scan_failed': True}), \
         patch('gmail.get_gmail_service', return_value=MagicMock()):
        
        result = await _analyze_one(
            email=mock_email,
            semaphore=asyncio.Semaphore(1),
            ai_router=MagicMock(),
            classification_prompt="Test {subject}",
            user_id=1,
            user_email='test@example.com',
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=asyncio.Semaphore(5),
            available_label_names=['Finance'],
            gmail_labels_cache={},
            update_mode=False
        )
        
        # URL scan failure → unavailable, analysis becomes partial
        assert result['url_scan_status'] == 'unavailable'
        assert result['urls_checked'] == 0
        assert result['analysis_status'] == 'partial'  # Not complete due to unavailable URL scan
        
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs['url_scan_status'] == 'unavailable'


@pytest.mark.asyncio
async def test_analysis_failure_preserves_url_threat(mock_email):
    """Test that analysis failure preserves URL threat evidence."""
    from gmail import _analyze_one
    
    with patch('v2_routing.route_email_with_v2', side_effect=ValueError("AI analysis failed")), \
         patch('gmail.get_labels', return_value=[{'label_name': 'Finance'}]), \
         patch('gmail.is_already_analyzed', return_value=False), \
         patch('gmail.save_analyzed_email') as mock_save, \
         patch('gmail.add_to_retry_queue'), \
         patch('gmail.asyncio.to_thread', new_callable=AsyncMock, return_value='Click here to claim your prize: https://phishing-site.example.com/steal'), \
         patch('security.scan_url', new_callable=AsyncMock, return_value={'is_safe': 0, 'threat_type': 'PHISHING'}), \
         patch('gmail.get_gmail_service', return_value=MagicMock()):
        
        result = await _analyze_one(
            email=mock_email,
            semaphore=asyncio.Semaphore(1),
            ai_router=MagicMock(),
            classification_prompt="Test {subject}",
            user_id=1,
            user_email='test@example.com',
            service=MagicMock(),
            url_client=MagicMock(),
            url_semaphore=asyncio.Semaphore(5),
            available_label_names=['Finance'],
            gmail_labels_cache={},
            update_mode=False
        )
        
        # Should fail but preserve URL threat
        assert result['status'] == 'failed'
        assert result['scam_score'] == 95  # URL threat preserved
        assert result['is_quarantined'] == 1
        
        # Verify error path saved URL evidence
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs['scam_score'] == 95
        assert call_kwargs['is_quarantined'] == 1
        indicators = call_kwargs['scam_indicators']
        assert 'Known malicious link detected' in indicators
