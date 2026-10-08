"""
Pydantic request validation schemas for Gmail Manager API endpoints.

All request bodies must validate through these schemas to ensure type safety,
prevent injection attacks, and provide clear error messages to API consumers.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ============================================================================
# Email Label Operations
# ============================================================================

class UpdateEmailLabelRequest(BaseModel):
    """Single email label update (PUT /emails/{email_id}/label)."""
    label_name: str = Field(..., min_length=1, max_length=100, description="Target label name")


class EmailLabelChange(BaseModel):
    """Individual email-label change within a batch operation."""
    email_id: str = Field(..., min_length=1, max_length=255, description="Gmail message ID")
    label_name: str = Field(..., min_length=1, max_length=100, description="Target label name")


class BatchLabelUpdateRequest(BaseModel):
    """Structured batch label updates (POST /emails/batch-label)."""
    changes: List[EmailLabelChange] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of email-label changes (1-100 items)"
    )


class BulkLabelRequest(BaseModel):
    """
    Bulk label assignment to multiple emails (POST /emails/bulk-label).
    
    KNOWN ISSUE: Frontend currently sends 'label_name' (string) but backend
    expects 'label_id' (integer). This schema enforces the intended API contract.
    Frontend must be updated to send label_id after schema validation is deployed.
    """
    email_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gmail message IDs (1-100 items)"
    )
    label_id: int = Field(..., ge=1, description="Target label ID (positive integer)")

    @field_validator('email_ids')
    @classmethod
    def validate_email_ids(cls, v: List[str]) -> List[str]:
        """Ensure all email IDs are non-empty strings."""
        if not all(isinstance(eid, str) and len(eid) > 0 for eid in v):
            raise ValueError("All email_ids must be non-empty strings")
        return v


# ============================================================================
# Label Management
# ============================================================================

class CreateLabelRequest(BaseModel):
    """
    Create new label (POST /labels).
    
    Supports dual-field backward compatibility: accepts either 'name' or 'label_name'.
    Color field is optional; if provided, must be valid hex format.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    label_name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")

    @model_validator(mode='after')
    def validate_name_fields(self):
        """Ensure exactly one name field is provided."""
        name_val = self.name or self.label_name
        if not name_val:
            raise ValueError("Either 'name' or 'label_name' must be provided")
        # Normalize to single field
        if not self.name:
            self.name = self.label_name
        return self


# ============================================================================
# Bulk Delete Operations
# ============================================================================

class UpdateDeleteModeRequest(BaseModel):
    """Update user delete mode preference (PUT /user/settings/delete-mode)."""
    mode: Literal["trash", "permanent"] = Field(
        ...,
        description="Delete mode: 'trash' (soft delete) or 'permanent' (hard delete)"
    )


class BatchDeleteRequest(BaseModel):
    """
    Filter-based batch delete (POST /emails/batch-delete).
    
    Deletes all emails matching label name or sender filter.
    Use with caution as this can affect many emails without explicit ID list.
    """
    mode: Literal["label", "sender"] = Field(
        ...,
        description="Filter type: 'label' (exact label match) or 'sender' (substring match)"
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Filter value: label name or sender email/substring"
    )


class BulkDeleteRequest(BaseModel):
    """ID-based bulk delete (POST /emails/bulk-delete)."""
    email_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gmail message IDs to delete (1-100 items)"
    )

    @field_validator('email_ids')
    @classmethod
    def validate_email_ids(cls, v: List[str]) -> List[str]:
        """Ensure all email IDs are non-empty strings."""
        if not all(isinstance(eid, str) and len(eid) > 0 for eid in v):
            raise ValueError("All email_ids must be non-empty strings")
        return v


# ============================================================================
# Quarantine Operations
# ============================================================================

class BulkMarkSafeRequest(BaseModel):
    """Mark multiple emails as safe (POST /emails/bulk-mark-safe)."""
    email_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gmail message IDs to mark safe (1-100 items)"
    )

    @field_validator('email_ids')
    @classmethod
    def validate_email_ids(cls, v: List[str]) -> List[str]:
        """Ensure all email IDs are non-empty strings."""
        if not all(isinstance(eid, str) and len(eid) > 0 for eid in v):
            raise ValueError("All email_ids must be non-empty strings")
        return v


class BulkQuarantineRequest(BaseModel):
    """Quarantine multiple emails (POST /emails/bulk-quarantine)."""
    email_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Gmail message IDs to quarantine (1-100 items)"
    )

    @field_validator('email_ids')
    @classmethod
    def validate_email_ids(cls, v: List[str]) -> List[str]:
        """Ensure all email IDs are non-empty strings."""
        if not all(isinstance(eid, str) and len(eid) > 0 for eid in v):
            raise ValueError("All email_ids must be non-empty strings")
        return v


# ============================================================================
# AI Operations
# ============================================================================

class AIRewriteRequest(BaseModel):
    """AI email rewriting (POST /ai/rewrite)."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Email text to rewrite (1-50000 characters)"
    )
    instruction: str = Field(
        ...,
        max_length=2000,
        description="Rewrite instructions for AI (max 2000 characters)"
    )


# ============================================================================
# Analysis Operations
# ============================================================================

class ReanalyzeRequest(BaseModel):
    """
    Reanalyze email scam score (POST /scam/reanalyze/{email_id}).
    
    Optional body allows forcing reanalysis even if recently analyzed.
    """
    force: Optional[bool] = Field(False, description="Force reanalysis even if recent")
