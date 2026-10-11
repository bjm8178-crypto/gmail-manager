"""
H5: Tests for AI Response Schema Validation
"""
import pytest
from pydantic import ValidationError
from ai_response_schema import (
    AIClassificationResponse,
    AIScamAnalysisResponse,
    validate_classification_response,
    validate_scam_analysis_response,
    safe_extract_classification
)


class TestAIClassificationResponseSchema:
    """Test AIClassificationResponse Pydantic model."""
    
    def test_valid_classification_response(self):
        """Valid classification response should pass."""
        data = {
            'label': 'Phishing',
            'confidence': 85.5,
            'reasoning': 'Suspicious sender and urgency language',
            'scam_indicators': ['urgent language', 'unknown sender'],
            'scam_score': 90.0
        }
        response = AIClassificationResponse(**data)
        assert response.label == 'Phishing'
        assert response.confidence == 85.5
        assert len(response.scam_indicators) == 2
    
    def test_reject_invalid_category(self):
        """Invalid category label should be rejected."""
        data = {
            'label': 'InvalidCategory',  # Not in ValidCategory
            'confidence': 50.0,
            'reasoning': 'Test'
        }
        with pytest.raises(ValidationError) as exc_info:
            AIClassificationResponse(**data)
        assert 'label' in str(exc_info.value)
    
    def test_reject_out_of_range_confidence(self):
        """Confidence outside 0-100 range should be rejected."""
        data = {
            'label': 'Spam',
            'confidence': 150.0,  # > 100
            'reasoning': 'Test'
        }
        with pytest.raises(ValidationError) as exc_info:
            AIClassificationResponse(**data)
        assert 'confidence' in str(exc_info.value)
    
    def test_reject_negative_confidence(self):
        """Negative confidence should be rejected."""
        data = {
            'label': 'Personal',
            'confidence': -10.0,
            'reasoning': 'Test'
        }
        with pytest.raises(ValidationError) as exc_info:
            AIClassificationResponse(**data)
        assert 'confidence' in str(exc_info.value)
    
    def test_reject_empty_reasoning(self):
        """Empty or whitespace-only reasoning should be rejected."""
        data = {
            'label': 'Work',
            'confidence': 70.0,
            'reasoning': '   '  # Whitespace only
        }
        with pytest.raises(ValidationError) as exc_info:
            AIClassificationResponse(**data)
        assert 'reasoning' in str(exc_info.value)
    
    def test_reject_missing_required_fields(self):
        """Missing required fields should be rejected."""
        data = {
            'label': 'Shopping',
            # Missing confidence and reasoning
        }
        with pytest.raises(ValidationError):
            AIClassificationResponse(**data)
    
    def test_reject_oversized_indicator_list(self):
        """Indicator list exceeding 50 items should be rejected."""
        data = {
            'label': 'Spam',
            'confidence': 80.0,
            'reasoning': 'Test',
            'scam_indicators': ['indicator'] * 51  # > 50
        }
        with pytest.raises(ValidationError) as exc_info:
            AIClassificationResponse(**data)
        assert 'too long' in str(exc_info.value).lower()
    
    def test_reject_non_string_indicators(self):
        """Non-string values in scam_indicators should be rejected."""
        data = {
            'label': 'Phishing',
            'confidence': 90.0,
            'reasoning': 'Test',
            'scam_indicators': ['valid', 123, 'another']  # Mixed types
        }
        with pytest.raises(ValidationError):
            AIClassificationResponse(**data)
    
    def test_scam_score_optional(self):
        """scam_score should be optional."""
        data = {
            'label': 'Personal',
            'confidence': 95.0,
            'reasoning': 'Trusted sender'
        }
        response = AIClassificationResponse(**data)
        assert response.scam_score is None


class TestAIScamAnalysisResponseSchema:
    """Test AIScamAnalysisResponse Pydantic model."""
    
    def test_valid_scam_analysis(self):
        """Valid scam analysis should pass."""
        data = {
            'is_scam': True,
            'scam_score': 95.0,
            'scam_indicators': ['phishing link', 'spoofed sender'],
            'reasoning': 'Multiple red flags detected'
        }
        response = AIScamAnalysisResponse(**data)
        assert response.is_scam is True
        assert response.scam_score == 95.0
    
    def test_reject_out_of_range_scam_score(self):
        """scam_score outside 0-100 should be rejected."""
        data = {
            'is_scam': False,
            'scam_score': 110.0,  # > 100
            'scam_indicators': [],
            'reasoning': 'Clean email'
        }
        with pytest.raises(ValidationError):
            AIScamAnalysisResponse(**data)


class TestValidationHelpers:
    """Test validation helper functions."""
    
    def test_validate_classification_response_success(self):
        """validate_classification_response should return validated instance."""
        data = {
            'label': 'Finance',
            'confidence': 88.0,
            'reasoning': 'Bank transaction notification',
            'scam_indicators': []
        }
        result = validate_classification_response(data)
        assert isinstance(result, AIClassificationResponse)
        assert result.label == 'Finance'
    
    def test_validate_classification_response_failure(self):
        """validate_classification_response should raise on invalid data."""
        data = {'label': 'BadCategory', 'confidence': 50.0}
        with pytest.raises(ValidationError):
            validate_classification_response(data)
    
    def test_safe_extract_with_valid_data(self):
        """safe_extract_classification should return validated dict."""
        data = {
            'label': 'Promotions',
            'confidence': 75.0,
            'reasoning': 'Marketing email',
            'scam_indicators': [],
            'scam_score': 10.0
        }
        result = safe_extract_classification(data)
        assert result['validation_passed'] is True
        assert result['label'] == 'Promotions'
        assert result['confidence'] == 75.0
    
    def test_safe_extract_with_invalid_data(self):
        """safe_extract_classification should return safe defaults on failure."""
        data = {
            'label': 'InvalidCategory',
            'confidence': 999.0,  # Invalid
            'reasoning': ''
        }
        result = safe_extract_classification(data)
        assert result['validation_passed'] is False
        assert result['label'] == 'Unknown'
        assert result['confidence'] == 0.0
        assert 'validation_error' in result
    
    def test_safe_extract_prevents_injection(self):
        """safe_extract_classification should prevent malicious payloads."""
        data = {
            'label': 'Personal',
            'confidence': 50.0,
            'reasoning': 'x' * 3000,  # Exceeds max_length
            'scam_indicators': ['a'] * 100  # Exceeds max items
        }
        result = safe_extract_classification(data)
        # Should fail validation and return safe defaults
        assert result['validation_passed'] is False
        assert result['label'] == 'Unknown'
