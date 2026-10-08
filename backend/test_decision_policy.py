"""
test_decision_policy.py — Regression tests for centralized decision policy (H1)
Tests precedence rules for security verdicts.
"""
import pytest
from decision_policy import (
    determine_security_verdict,
    should_auto_quarantine,
    should_apply_to_gmail,
    get_verdict_priority,
)


class TestSecurityVerdictPrecedence:
    """Test that precedence is applied correctly."""
    
    def test_user_safe_overrides_everything(self):
        """User marking safe should override malicious URL and high risk score."""
        verdict = determine_security_verdict(
            user_decision="safe",
            url_threat_confirmed=True,  # Even with malicious URL
            analysis_status="completed",
            risk_score=95,  # Even with high risk
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "user_safe"
        assert verdict["display_badge"] == "Marked Safe"
        assert verdict["risk_score"] == 95  # Preserves original score
    
    def test_user_quarantine_overrides_everything(self):
        """User quarantine should override even low risk scores."""
        verdict = determine_security_verdict(
            user_decision="quarantine",
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=10,  # Low risk
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "user_quarantined"
        assert verdict["display_badge"] == "Quarantined"
    
    def test_malicious_url_overrides_low_ai_score(self):
        """Confirmed malicious URL should override low AI risk score."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=True,
            analysis_status="completed",
            risk_score=20,  # AI says low risk, but URL is malicious
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "malicious_url"
        assert verdict["risk_score"] == 100  # Overrides to 100
        assert verdict["display_badge"] == "Malicious URL"
    
    def test_analysis_unavailable_takes_precedence_over_risk_score(self):
        """When analysis fails, should show unavailable, not risk score."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="unavailable",
            risk_score=85,  # Score present but analysis unavailable
            url_scan_status="unavailable",
        )
        assert verdict["verdict"] == "analysis_unavailable"
        assert verdict["risk_score"] is None
        assert verdict["display_badge"] == "Analysis Unavailable"
    
    def test_high_risk_verdict(self):
        """Risk score >= 70 should be high risk."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=72,
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "high_risk"
        assert verdict["display_badge"] == "High Risk"
        assert verdict["badge_color"] == "danger"
    
    def test_medium_risk_verdict(self):
        """Risk score 50-69 should be medium risk."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=55,
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "medium_risk"
        assert verdict["display_badge"] == "Medium Risk"
        assert verdict["badge_color"] == "warning"
    
    def test_low_risk_verdict(self):
        """Risk score < 50 should be low risk."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=25,
            url_scan_status="checked",
        )
        assert verdict["verdict"] == "low_risk"
        assert verdict["display_badge"] == "Low Risk"
        assert verdict["badge_color"] == "success"
    
    def test_unknown_when_not_analyzed(self):
        """No analysis or pending should show unknown."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="pending",
            risk_score=None,
            url_scan_status=None,
        )
        assert verdict["verdict"] == "unknown"
        assert verdict["display_badge"] == "Not Analyzed"
        assert verdict["risk_score"] is None


class TestAutoQuarantine:
    """Test auto-quarantine logic."""
    
    def test_malicious_url_triggers_quarantine(self):
        """Malicious URL should trigger auto-quarantine."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=True,
            analysis_status="completed",
            risk_score=100,
            url_scan_status="checked",
        )
        assert should_auto_quarantine(verdict) is True
    
    def test_high_risk_triggers_quarantine(self):
        """High risk (>= 70) should trigger auto-quarantine."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=75,
            url_scan_status="checked",
        )
        assert should_auto_quarantine(verdict) is True
    
    def test_medium_risk_no_quarantine(self):
        """Medium risk should NOT trigger auto-quarantine."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=60,
            url_scan_status="checked",
        )
        assert should_auto_quarantine(verdict) is False
    
    def test_user_safe_no_quarantine(self):
        """User marking safe should never auto-quarantine."""
        verdict = determine_security_verdict(
            user_decision="safe",
            url_threat_confirmed=True,
            analysis_status="completed",
            risk_score=100,
            url_scan_status="checked",
        )
        assert should_auto_quarantine(verdict) is False


class TestGmailSync:
    """Test Gmail sync decision logic."""
    
    def test_unavailable_not_synced(self):
        """Analysis unavailable should NOT be synced to Gmail."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="unavailable",
            risk_score=None,
            url_scan_status="unavailable",
        )
        assert should_apply_to_gmail(verdict, sync_enabled=True) is False
    
    def test_unknown_not_synced(self):
        """Unknown/not analyzed emails should NOT be synced to Gmail."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status=None,
            risk_score=None,
            url_scan_status="not_scanned",
        )
        assert should_apply_to_gmail(verdict, sync_enabled=True) is False
    
    def test_valid_verdicts_sync_when_enabled(self):
        """Valid analyzed emails should be synced when enabled."""
        verdict = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=75,
            url_scan_status="checked",
        )
        assert should_apply_to_gmail(verdict, sync_enabled=True) is True
        assert should_apply_to_gmail(verdict, sync_enabled=False) is False


class TestVerdictPriority:
    """Test verdict priority for sorting."""
    
    def test_priority_ordering(self):
        """Malicious URL should have higher priority than high risk."""
        malicious = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=True,
            analysis_status="completed",
            risk_score=50,
            url_scan_status="checked",
        )
        high_risk = determine_security_verdict(
            user_decision=None,
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=85,
            url_scan_status="checked",
        )
        assert get_verdict_priority(malicious) < get_verdict_priority(high_risk)
    
    def test_user_quarantine_high_priority(self):
        """User quarantine should be priority 2."""
        verdict = determine_security_verdict(
            user_decision="quarantine",
            url_threat_confirmed=False,
            analysis_status="completed",
            risk_score=10,
            url_scan_status="checked",
        )
        assert get_verdict_priority(verdict) == 2
