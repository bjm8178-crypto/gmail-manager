"""Independent category classification and confidence-band phishing routing.

A phishing model is not a category classifier. AI is therefore consulted for
categories even when the local model supplies a high-confidence risk score.

H5: AI responses are validated against strict Pydantic schemas before use.
"""
import asyncio
import os
import math
from numbers import Real
from typing import Any, Dict
from logger_setup import get_logger
from decision_policy import determine_security_verdict
from ai_response_schema import safe_extract_classification

logger = get_logger(__name__)
AUTO_CLEAR_THRESHOLD = float(os.getenv('V2_AUTO_CLEAR_THRESHOLD', '0.40'))
AUTO_FLAG_THRESHOLD = float(os.getenv('V2_AUTO_FLAG_THRESHOLD', '0.85'))

try:
    from predict import predict_email
    V2_AVAILABLE = True
except Exception:
    V2_AVAILABLE = False
    logger.warning('[V2_ROUTER] Local model unavailable')


class AnalysisUnavailableError(RuntimeError):
    """No risk verdict is available; ``result`` retains any partial category/evidence."""

    def __init__(self, result):
        super().__init__('Security analysis unavailable: no valid model or AI risk verdict')
        self.result = result


def _valid_number(value, maximum):
    return (isinstance(value, Real) and not isinstance(value, bool)
            and 0 <= value <= maximum and math.isfinite(value))


async def route_email_with_v2(
    email_id: str, subject: str, sender: str, body: str, snippet: str,
    ai_cascade_func, classification_prompt: str,
    url_threat_confirmed: bool = False, url_scan_unavailable: bool = False,
    available_label_names: list = None,
) -> Dict[str, Any]:
    """The caller supplies an async zero-argument AI closure (prompt included)."""
    response = {
        'label': 'Unknown', 'scam_score': None, 'scam_indicators': [],
        'reasoning': '', 'routing_decision': 'unavailable', 'v2_score': None,
        'provider_used': None, 'analysis_status': 'unavailable',
        'category_status': 'unavailable',
        'url_threat_confirmed': bool(url_threat_confirmed),
        'url_scan_unavailable': bool(url_scan_unavailable),
    }
    score = None
    if V2_AVAILABLE:
        try:
            prediction = await asyncio.to_thread(predict_email, subject, body, sender)
            candidate = prediction['probabilities']['phishing']
            if not _valid_number(candidate, 1):
                raise ValueError('Invalid phishing probability')
            score = float(candidate)
            response['v2_score'] = score
        except Exception:
            logger.warning('[V2_ROUTER] Local prediction failed')

    try:
        ai_result = await ai_cascade_func()
    except Exception:
        logger.warning('[V2_ROUTER] AI classification unavailable')
        ai_result = {}
    if not isinstance(ai_result, dict):
        ai_result = {}
    data = ai_result.get('data')
    if not isinstance(data, dict):
        data = {}
    indicators = data.get('scam_indicators', [])
    reasoning = data.get('reasoning', '')
    if (not isinstance(indicators, list) or not all(isinstance(item, str) for item in indicators)
            or not isinstance(reasoning, str)):
        data = {}
    provider = ai_result.get('provider_used')
    provider = provider if isinstance(provider, str) and provider.strip() else None
    label = data.get('label')
    label_match = next((name for name in (available_label_names or [])
                        if isinstance(name, str) and isinstance(label, str)
                        and name.strip() and name.casefold() == label.strip().casefold()), None)
    if label_match is not None:
        response['label'] = label_match
        response['category_status'] = 'complete'
        response['provider_used'] = provider

    if url_threat_confirmed:
        response.update(scam_score=100, scam_indicators=['Confirmed malicious URL'],
                        reasoning='Confirmed malicious URL overrides model and AI risk scores.',
                        routing_decision='url_threat_override')
    elif score is not None and (score < AUTO_CLEAR_THRESHOLD or score > AUTO_FLAG_THRESHOLD):
        response.update(scam_score=int(score * 100),
                        routing_decision='v2_auto_clear' if score < AUTO_CLEAR_THRESHOLD else 'v2_auto_flag',
                        reasoning='Local phishing model risk estimate.')
    elif _valid_number(data.get('scam_score'), 100):
        response.update(scam_score=int(data['scam_score']),
                        scam_indicators=data.get('scam_indicators', []),
                        reasoning=data.get('reasoning', ''), routing_decision='ai_cascade',
                        provider_used=provider)
    elif score is not None:
        response.update(scam_score=int(score * 100),
                        routing_decision='ai_cascade_failed_v2_fallback',
                        reasoning='AI unavailable; local phishing model risk estimate.')

    if response['scam_score'] is not None:
        response['analysis_status'] = ('complete' if response['category_status'] == 'complete'
                                       and not url_scan_unavailable else 'partial')
    if response['scam_score'] is None:
        raise AnalysisUnavailableError(response)
    
    # Apply centralized verdict policy (H1: Decision Policy Centralization)
    verdict_result = determine_security_verdict(
        user_decision=None,  # Will be set by database if user has marked-safe/quarantine
        url_threat_confirmed=response['url_threat_confirmed'],
        analysis_status=response['analysis_status'],
        risk_score=response['scam_score'],
        url_scan_status='complete' if not url_scan_unavailable else 'unavailable',
        reasoning=response.get('reasoning')
    )
    response['verdict'] = verdict_result['verdict']
    response['verdict_priority'] = verdict_result['priority']
    response['verdict_display'] = verdict_result['display_badge']
    
    return response


def get_routing_stats() -> Dict[str, Any]:
    return {
        'v2_available': V2_AVAILABLE,
        'auto_clear_threshold': AUTO_CLEAR_THRESHOLD,
        'auto_flag_threshold': AUTO_FLAG_THRESHOLD,
        'cascade_band': f'{AUTO_CLEAR_THRESHOLD}-{AUTO_FLAG_THRESHOLD}',
    }
