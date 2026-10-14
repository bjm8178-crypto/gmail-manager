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
    import predict as _predict
    predict_email = _predict.predict_email
    _model_file = getattr(_predict, '_model_path', None)
    V2_AVAILABLE = _model_file is None or _model_file.exists()
    if not V2_AVAILABLE:
        logger.warning('[V2_ROUTER] Model file missing (%s); running AI-only', _model_file)
except Exception:
    V2_AVAILABLE = False
    logger.warning('[V2_ROUTER] Local model unavailable')


# Phase 5 Task 15: Local ML Circuit Breaker
# If local ML fails on N calls, open breaker so broken model costs 0ms per email
ML_MAX_FAILURES = int(os.getenv("ML_MAX_FAILURES", "3"))
_ml_failure_count = 0
_ml_breaker_open = False
_ml_traceback_logged = False


def reset_ml_circuit_breaker():
    """Reset ML circuit breaker state (useful for tests or after model reload)."""
    global _ml_failure_count, _ml_breaker_open, _ml_traceback_logged
    _ml_failure_count = 0
    _ml_breaker_open = False
    _ml_traceback_logged = False


def is_ml_breaker_open() -> bool:
    """Return whether the ML circuit breaker is open."""
    return _ml_breaker_open


def _record_ml_failure(exc: Exception):
    global _ml_failure_count, _ml_breaker_open, _ml_traceback_logged
    _ml_failure_count += 1
    if not _ml_traceback_logged:
        import traceback
        logger.error(
            "[V2_ROUTER] Local ML prediction failed (first failure, full traceback):\n%s",
            traceback.format_exc(),
        )
        _ml_traceback_logged = True
    else:
        logger.warning(
            "[V2_ROUTER] Local prediction failed (%d/%d): %s: %s",
            _ml_failure_count,
            ML_MAX_FAILURES,
            type(exc).__name__,
            str(exc)[:200],
        )

    if _ml_failure_count >= ML_MAX_FAILURES and not _ml_breaker_open:
        _ml_breaker_open = True
        logger.error(
            "[V2_ROUTER] Local ML circuit breaker OPEN after %d failures; "
            "bypassing local ML (costs 0ms per email)",
            _ml_failure_count,
        )


def _record_ml_success():
    global _ml_failure_count
    _ml_failure_count = 0


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
    t_ml = 0.0
    if V2_AVAILABLE and not _ml_breaker_open:
        t_ml_start = asyncio.get_event_loop().time()
        try:
            prediction = await asyncio.to_thread(predict_email, subject, body, sender)
            candidate = prediction['probabilities']['phishing']
            if not _valid_number(candidate, 1):
                raise ValueError('Invalid phishing probability')
            score = float(candidate)
            response['v2_score'] = score
            _record_ml_success()
        except Exception as e:
            _record_ml_failure(e)
        finally:
            t_ml = asyncio.get_event_loop().time() - t_ml_start

    t_ai_start = asyncio.get_event_loop().time()
    try:
        ai_result = await ai_cascade_func()
    except Exception as e:
        provider_info = ""
        logger.warning(
            '[V2_ROUTER] AI cascade raised %s: %s%s',
            type(e).__name__,
            str(e)[:120],
            provider_info
        )
        ai_result = {}
    finally:
        t_ai = asyncio.get_event_loop().time() - t_ai_start

    response['timings'] = {'ml': t_ml, 'ai': t_ai}
    
    if not isinstance(ai_result, dict):
        logger.warning('[V2_ROUTER] AI result not a dict: got %s', type(ai_result).__name__)
        ai_result = {}
    
    data = ai_result.get('data')
    provider = ai_result.get('provider_used')
    provider_str = f" (provider: {provider})" if isinstance(provider, str) and provider.strip() else ""
    
    if not isinstance(data, dict):
        error_msg = ai_result.get('error', '')
        if isinstance(error_msg, str) and error_msg:
            # Redact secrets: key=..., AIza..., gsk_..., Bearer ...
            import re
            error_msg = re.sub(r'key=[^&\s]+', '[REDACTED]', error_msg)
            error_msg = re.sub(r'AIza[0-9A-Za-z_-]+', '[REDACTED]', error_msg)
            error_msg = re.sub(r'gsk_[A-Za-z0-9]+', '[REDACTED]', error_msg)
            error_msg = re.sub(r'Bearer\s+\S+', 'Bearer [REDACTED]', error_msg)
            logger.warning('[V2_ROUTER] No dict under data key, error: %s%s', error_msg[:300], provider_str)
        else:
            logger.warning('[V2_ROUTER] No dict under data key%s', provider_str)
        data = {}
    
    indicators = data.get('scam_indicators', [])
    reasoning = data.get('reasoning', '')
    if (not isinstance(indicators, list) or not all(isinstance(item, str) for item in indicators)
            or not isinstance(reasoning, str)):
        logger.warning(
            '[V2_ROUTER] Data discarded: scam_indicators or reasoning validation failed%s',
            provider_str
        )
        data = {}
    
    provider = provider if isinstance(provider, str) and provider.strip() else None
    label = data.get('label')
    
    if not label or not isinstance(label, str):
        if data:  # Only log if we had valid data but missing/invalid label
            logger.warning('[V2_ROUTER] Label missing or not a string%s', provider_str)
    
    label_match = next((name for name in (available_label_names or [])
                        if isinstance(name, str) and isinstance(label, str)
                        and name.strip() and name.casefold() == label.strip().casefold()), None)
    
    if not available_label_names:
        logger.warning('[V2_ROUTER] No available labels — category_status will be unavailable')
    
    if label_match is not None:
        response['label'] = label_match
        response['category_status'] = 'complete'
        response['provider_used'] = provider
    elif isinstance(label, str) and label.strip() and available_label_names:
        logger.warning(
            '[V2_ROUTER] Label mismatch: returned "%s", available: %s%s',
            label[:40],
            available_label_names,
            provider_str
        )

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
