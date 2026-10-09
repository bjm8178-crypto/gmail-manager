"""
Tests for consolidated quarantine policy.
Verifies consistent behavior between bulk analysis and single-email reanalysis.
"""
import pytest
from quarantine_policy import should_quarantine


class TestQuarantinePolicy:
    """Test the consolidated quarantine decision logic."""
    
    def test_url_threat_always_quarantines_regardless_of_score(self):
        """Confirmed URL threat → quarantine, even with low score."""
        assert should_quarantine(scam_score=0, url_threat_confirmed=True, label="Finance")
        assert should_quarantine(scam_score=30, url_threat_confirmed=True, label="Personal")
        assert should_quarantine(scam_score=69, url_threat_confirmed=True, label="Safe")
    
    def test_high_score_quarantines_without_url_threat(self):
        """Score >= 70 → quarantine, even without URL threat."""
        assert should_quarantine(scam_score=70, url_threat_confirmed=False, label="Finance")
        assert should_quarantine(scam_score=85, url_threat_confirmed=False, label="Personal")
        assert should_quarantine(scam_score=100, url_threat_confirmed=False, label="Spam")
    
    def test_low_score_without_url_threat_does_not_quarantine(self):
        """Score < 70 and no URL threat → no quarantine."""
        assert not should_quarantine(scam_score=0, url_threat_confirmed=False, label="Finance")
        assert not should_quarantine(scam_score=35, url_threat_confirmed=False, label="Personal")
        assert not should_quarantine(scam_score=69, url_threat_confirmed=False, label="Promotional")
    
    def test_label_does_not_affect_quarantine_decision(self):
        """Label is currently unused in policy - test with various labels."""
        # High score quarantines regardless of label
        assert should_quarantine(scam_score=75, url_threat_confirmed=False, label="Finance")
        assert should_quarantine(scam_score=75, url_threat_confirmed=False, label="Spam")
        assert should_quarantine(scam_score=75, url_threat_confirmed=False, label="Personal")
        
        # Low score + no URL threat never quarantines
        assert not should_quarantine(scam_score=50, url_threat_confirmed=False, label="Spam")
        assert not should_quarantine(scam_score=50, url_threat_confirmed=False, label="Scam Alert")
    
    def test_invalid_scam_score_defaults_to_url_threat_only(self):
        """Invalid scam_score falls back to URL threat check only."""
        assert should_quarantine(scam_score=None, url_threat_confirmed=True, label="Finance")
        assert not should_quarantine(scam_score=None, url_threat_confirmed=False, label="Finance")
        assert not should_quarantine(scam_score="invalid", url_threat_confirmed=False, label="Finance")
    
    def test_boundary_conditions(self):
        """Test exact threshold boundaries."""
        # 69 is below threshold
        assert not should_quarantine(scam_score=69, url_threat_confirmed=False, label="Finance")
        # 70 is at threshold
        assert should_quarantine(scam_score=70, url_threat_confirmed=False, label="Finance")
        # 71 is above threshold
        assert should_quarantine(scam_score=71, url_threat_confirmed=False, label="Finance")
    
    def test_both_conditions_true(self):
        """URL threat + high score → quarantine (double condition)."""
        assert should_quarantine(scam_score=95, url_threat_confirmed=True, label="Spam")
        assert should_quarantine(scam_score=100, url_threat_confirmed=True, label="Phishing")
