"""
H5: AI Response Schema Validation with Pydantic

Enforces strict validation on AI provider responses to prevent:
- Invalid category labels
- Out-of-range confidence scores
- Missing required fields
- Type confusion attacks

All AI responses MUST validate against these schemas before being used.
"""

from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Literal, Optional
from logger_setup import get_logger

logger = get_logger(__name__)

# Valid email categories (must match frontend expectations)
ValidCategory = Literal[
    "Personal",
    "Work", 
    "Shopping",
    "Promotions",
    "Finance",
    "Social",
    "Travel",
    "Receipts",
    "Updates",
    "Forums",
    "Spam",
    "Phishing",
    "Unknown"
]


class AIClassificationResponse(BaseModel):
    """
    Schema for AI category classification responses.
    
    Used by v2_routing.py when calling AI for email categorization.
    """
    label: ValidCategory = Field(
        description="Email category label from predefined set"
    )
    confidence: float = Field(
        ge=0.0, le=100.0,
        description="Classification confidence score (0-100)"
    )
    reasoning: str = Field(
        min_length=1, max_length=2000,
        description="Explanation for classification decision"
    )
    scam_indicators: List[str] = Field(
        default_factory=list,
        description="List of phishing/scam indicators found"
    )
    scam_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Phishing/scam risk score (0-100)"
    )
    
    @field_validator('scam_indicators')
    @classmethod
    def validate_indicators(cls, v):
        """Ensure all indicators are non-empty strings."""
        if not isinstance(v, list):
            raise ValueError("scam_indicators must be a list")
        if len(v) > 50:  # Prevent DoS via massive lists
            raise ValueError("scam_indicators list too long (max 50)")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All scam_indicators must be strings")
            if len(item) > 500:
                raise ValueError("Individual scam_indicator too long (max 500 chars)")
        return v
    
    @field_validator('reasoning')
    @classmethod
    def validate_reasoning(cls, v):
        """Ensure reasoning is meaningful."""
        if not v or not v.strip():
            raise ValueError("reasoning cannot be empty")
        return v.strip()


class AIScamAnalysisResponse(BaseModel):
    """
    Schema for AI scam/phishing analysis responses.
    
    Used by main.py /analyze-email endpoint for focused risk assessment.
    """
    is_scam: bool = Field(
        description="Binary scam/phishing verdict"
    )
    scam_score: float = Field(
        ge=0.0, le=100.0,
        description="Risk score (0-100)"
    )
    scam_indicators: List[str] = Field(
        description="List of specific indicators found"
    )
    reasoning: str = Field(
        min_length=1, max_length=2000,
        description="Explanation for verdict"
    )
    
    @field_validator('scam_indicators')
    @classmethod
    def validate_indicators(cls, v):
        """Ensure all indicators are valid."""
        if not isinstance(v, list):
            raise ValueError("scam_indicators must be a list")
        if len(v) > 50:
            raise ValueError("scam_indicators list too long (max 50)")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All scam_indicators must be strings")
            if len(item) > 500:
                raise ValueError("Individual scam_indicator too long (max 500 chars)")
        return v


def validate_classification_response(raw_data: dict) -> AIClassificationResponse:
    """
    Validate and parse AI classification response.
    
    Args:
        raw_data: Raw dict from AI provider
        
    Returns:
        Validated AIClassificationResponse instance
        
    Raises:
        ValidationError: If response doesn't match schema
    """
    try:
        return AIClassificationResponse(**raw_data)
    except ValidationError as e:
        logger.error(f"[H5 VALIDATION] Classification response failed schema validation: {e}")
        raise


def validate_scam_analysis_response(raw_data: dict) -> AIScamAnalysisResponse:
    """
    Validate and parse AI scam analysis response.
    
    Args:
        raw_data: Raw dict from AI provider
        
    Returns:
        Validated AIScamAnalysisResponse instance
        
    Raises:
        ValidationError: If response doesn't match schema
    """
    try:
        return AIScamAnalysisResponse(**raw_data)
    except ValidationError as e:
        logger.error(f"[H5 VALIDATION] Scam analysis response failed schema validation: {e}")
        raise


def safe_extract_classification(raw_data: dict) -> dict:
    """
    Safely extract classification data with validation.
    
    Returns a dict suitable for use in v2_routing.py response structure.
    If validation fails, returns safe defaults with error logged.
    
    Args:
        raw_data: Raw dict from AI provider (may be untrusted)
        
    Returns:
        Dict with validated fields or safe defaults
    """
    try:
        validated = validate_classification_response(raw_data)
        return {
            'label': validated.label,
            'confidence': validated.confidence,
            'reasoning': validated.reasoning,
            'scam_indicators': validated.scam_indicators,
            'scam_score': validated.scam_score,
            'validation_passed': True
        }
    except ValidationError as e:
        logger.warning(f"[H5] AI response validation failed: {e}")
        # Return safe defaults when validation fails
        return {
            'label': 'Unknown',
            'confidence': 0.0,
            'reasoning': 'AI response failed schema validation',
            'scam_indicators': [],
            'scam_score': None,
            'validation_passed': False,
            'validation_error': str(e)
        }
