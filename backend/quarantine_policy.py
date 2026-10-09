"""
Consolidated quarantine policy for Gmail Manager.

Defines when emails should be flagged for user review (quarantine).
This is a local review queue flag, not Gmail-level isolation.
"""
from logger_setup import get_logger

logger = get_logger(__name__)


def should_quarantine(
    scam_score: int,
    url_threat_confirmed: bool,
    label: str = None
) -> bool:
    """
    Determine if an email should be quarantined (flagged for review).
    
    Quarantine policy:
    - URL threat confirmed (malicious link detected) → always quarantine
    - OR scam_score >= 70 (high risk threshold) → quarantine
    
    Args:
        scam_score: Risk score 0-100
        url_threat_confirmed: True if confirmed malicious URL detected
        label: Optional label name (currently not used in policy)
        
    Returns:
        True if email should be quarantined, False otherwise
    """
    if not isinstance(scam_score, int):
        logger.warning(
            "[QUARANTINE] Invalid scam_score type %s, defaulting to not quarantined",
            type(scam_score).__name__
        )
        return url_threat_confirmed if isinstance(url_threat_confirmed, bool) else False
    
    # Policy: URL threat OR high scam score
    result = url_threat_confirmed or scam_score >= 70
    
    if result:
        reason = []
        if url_threat_confirmed:
            reason.append("confirmed_url_threat")
        if scam_score >= 70:
            reason.append(f"high_score_{scam_score}")
        logger.debug("[QUARANTINE] Flagged: %s", ", ".join(reason))
    
    return result
