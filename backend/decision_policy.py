"""
decision_policy.py — Centralized Security Decision Policy

Single source of truth for email security verdict precedence.
All security decisions flow through this module to ensure consistent
precedence across backend (v2_routing, gmail) and frontend display.

Precedence (highest to lowest):
1. User override (mark-safe, manual quarantine)
2. Confirmed malicious URL (Google Safe Browsing threat detected)
3. Analysis unavailable/failed states
4. Risk-based verdict from AI/ML analysis
"""

from typing import Optional, Literal, TypedDict
from logger_setup import get_logger

logger = get_logger(__name__)


class SecurityVerdict(TypedDict):
    """Final security verdict with precedence applied."""
    verdict: Literal[
        "user_safe",           # User marked safe
        "user_quarantined",    # User manually quarantined
        "malicious_url",       # Google Safe Browsing threat confirmed
        "analysis_unavailable", # Analysis failed/unavailable
        "high_risk",           # AI/ML detected high risk (score >= 70)
        "medium_risk",         # AI/ML detected medium risk (50-69)
        "low_risk",            # AI/ML detected low risk (< 50)
        "unknown",             # No analysis yet
    ]
    risk_score: Optional[int]  # 0-100 or None if unavailable
    priority: int              # Sorting priority (lower = higher priority)
    display_badge: str         # Badge text for UI
    badge_color: str           # Badge color class
    reasoning: Optional[str]   # Explanation for verdict
    is_actionable: bool        # Whether user can take action


def determine_security_verdict(
    user_decision: Optional[str],
    url_threat_confirmed: bool,
    analysis_status: Optional[str],
    risk_score: Optional[int],
    url_scan_status: Optional[str],
    reasoning: Optional[str] = None,
) -> SecurityVerdict:
    """
    Apply security decision precedence to determine final verdict.
    
    Args:
        user_decision: User's manual override ("safe" | "quarantine" | None)
        url_threat_confirmed: True if Google Safe Browsing detected threat
        analysis_status: "completed" | "failed" | "unavailable" | "pending" | None
        risk_score: AI/ML risk score (0-100) or None
        url_scan_status: "checked" | "unavailable" | "not_scanned" | None
        reasoning: Optional explanation text
    
    Returns:
        SecurityVerdict with final verdict and display properties
    """
    
    # Precedence Level 1: User Override (highest)
    if user_decision == "safe":
        return SecurityVerdict(
            verdict="user_safe",
            risk_score=risk_score,  # Preserve original score
            priority=1,
            display_badge="Marked Safe",
            badge_color="success",
            reasoning="User manually marked as safe",
            is_actionable=True,
        )
    
    if user_decision == "quarantine":
        return SecurityVerdict(
            verdict="user_quarantined",
            risk_score=risk_score,
            priority=2,
            display_badge="Quarantined",
            badge_color="danger",
            reasoning="User manually quarantined",
            is_actionable=True,
        )
    
    # Precedence Level 2: Confirmed Malicious URL
    if url_threat_confirmed:
        return SecurityVerdict(
            verdict="malicious_url",
            risk_score=100,  # Override any lower score
            priority=3,
            display_badge="Malicious URL",
            badge_color="danger",
            reasoning="Google Safe Browsing confirmed threat in email links",
            is_actionable=True,
        )
    
    # Precedence Level 3: Analysis Unavailable/Failed
    if analysis_status in ("failed", "unavailable"):
        return SecurityVerdict(
            verdict="analysis_unavailable",
            risk_score=None,
            priority=4,
            display_badge="Analysis Unavailable",
            badge_color="warning",
            reasoning=f"Analysis {analysis_status}: {reasoning or 'Unable to analyze'}",
            is_actionable=False,
        )
    
    if analysis_status in ("pending", None) or risk_score is None:
        return SecurityVerdict(
            verdict="unknown",
            risk_score=None,
            priority=8,
            display_badge="Not Analyzed",
            badge_color="neutral",
            reasoning="Email has not been analyzed yet",
            is_actionable=True,
        )
    
    # Precedence Level 4: Risk-Based Verdict
    # Note: URL scan unavailable is reflected in risk_score, not a separate verdict
    if risk_score >= 70:
        return SecurityVerdict(
            verdict="high_risk",
            risk_score=risk_score,
            priority=5,
            display_badge="High Risk",
            badge_color="danger",
            reasoning=reasoning or "AI analysis detected high phishing risk",
            is_actionable=True,
        )
    
    if risk_score >= 50:
        return SecurityVerdict(
            verdict="medium_risk",
            risk_score=risk_score,
            priority=6,
            display_badge="Medium Risk",
            badge_color="warning",
            reasoning=reasoning or "AI analysis detected medium phishing risk",
            is_actionable=True,
        )
    
    # Low risk (score < 50)
    return SecurityVerdict(
        verdict="low_risk",
        risk_score=risk_score,
        priority=7,
        display_badge="Low Risk",
        badge_color="success",
        reasoning=reasoning or "AI analysis detected low phishing risk",
        is_actionable=True,
    )


def should_auto_quarantine(verdict: SecurityVerdict) -> bool:
    """
    Determine if email should be automatically quarantined.
    
    Only malicious_url and high_risk trigger auto-quarantine.
    User overrides are already quarantined or safe.
    Medium/low risk and unavailable states do NOT auto-quarantine.
    
    Args:
        verdict: SecurityVerdict from determine_security_verdict()
    
    Returns:
        True if email should be auto-quarantined
    """
    return verdict["verdict"] in ("malicious_url", "high_risk")


def should_apply_to_gmail(verdict: SecurityVerdict, sync_enabled: bool = True) -> bool:
    """
    Determine if verdict should be synced to Gmail labels.
    
    Do NOT sync:
    - analysis_unavailable (no valid result to apply)
    - unknown (not yet analyzed)
    
    Args:
        verdict: SecurityVerdict from determine_security_verdict()
        sync_enabled: Global sync setting (default True)
    
    Returns:
        True if verdict should be applied to Gmail
    """
    if not sync_enabled:
        return False
    
    # Don't sync unavailable or unknown states
    return verdict["verdict"] not in ("analysis_unavailable", "unknown")


def get_verdict_priority(verdict: SecurityVerdict) -> int:
    """
    Get sorting priority for verdict.
    
    Lower number = higher priority (shown first in UI).
    
    Priority order:
    1. User marked safe
    2. User quarantined
    3. Malicious URL
    4. Analysis unavailable
    5. High risk
    6. Medium risk
    7. Low risk
    8. Unknown/not analyzed
    
    Args:
        verdict: SecurityVerdict from determine_security_verdict()
    
    Returns:
        Priority number (1-8)
    """
    return verdict["priority"]
