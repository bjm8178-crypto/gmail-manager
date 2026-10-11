"""
Comprehensive input validation tests for request schemas.

Tests ensure all Pydantic request models enforce constraints correctly,
reject invalid inputs with clear error messages, and preserve backward
compatibility with existing frontend clients.
"""

import pytest
from pydantic import ValidationError

from schemas import (
    UpdateEmailLabelRequest,
    EmailLabelChange,
    BatchLabelUpdateRequest,
    BulkLabelRequest,
    CreateLabelRequest,
    UpdateDeleteModeRequest,
    BatchDeleteRequest,
    BulkDeleteRequest,
    BulkMarkSafeRequest,
    BulkQuarantineRequest,
    AIRewriteRequest,
    ReanalyzeRequest,
)


# ============================================================================
# UpdateEmailLabelRequest Tests
# ============================================================================

class TestUpdateEmailLabelRequest:
    """Tests for single email label update validation."""

    def test_valid_label_name(self):
        """Accept a non-empty label name."""
        req = UpdateEmailLabelRequest(label_name="Important")
        assert req.label_name == "Important"

    def test_reject_empty_label_name(self):
        """Reject an empty label name."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateEmailLabelRequest(label_name="")
        assert "label_name" in str(exc_info.value).lower()

    def test_reject_missing_label_name(self):
        """Reject request without label_name."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateEmailLabelRequest()
        assert "label_name" in str(exc_info.value).lower()

    def test_reject_label_id_only_payload(self):
        """Reject the obsolete label_id-only payload."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateEmailLabelRequest(label_id=42)
        assert "label_name" in str(exc_info.value).lower()


# ============================================================================
# BatchLabelUpdateRequest Tests
# ============================================================================

class TestBatchLabelUpdateRequest:
    """Tests for structured batch label operations."""

    def test_valid_single_change(self):
        """Accept single email-label change."""
        req = BatchLabelUpdateRequest(
            changes=[{"email_id": "msg123", "label_name": "Important"}]
        )
        assert len(req.changes) == 1
        assert req.changes[0].email_id == "msg123"

    def test_valid_multiple_changes(self):
        """Accept 100 changes (upper boundary)."""
        changes = [
            {"email_id": f"msg{i}", "label_name": "Bulk"}
            for i in range(100)
        ]
        req = BatchLabelUpdateRequest(changes=changes)
        assert len(req.changes) == 100

    def test_reject_empty_changes_array(self):
        """Reject empty changes array."""
        with pytest.raises(ValidationError) as exc_info:
            BatchLabelUpdateRequest(changes=[])
        assert "changes" in str(exc_info.value).lower()

    def test_reject_oversized_changes_array(self):
        """Reject more than 100 changes."""
        changes = [
            {"email_id": f"msg{i}", "label_name": "Bulk"}
            for i in range(101)
        ]
        with pytest.raises(ValidationError) as exc_info:
            BatchLabelUpdateRequest(changes=changes)
        assert "changes" in str(exc_info.value).lower()

    def test_reject_empty_email_id(self):
        """Reject change with empty email_id."""
        with pytest.raises(ValidationError) as exc_info:
            BatchLabelUpdateRequest(
                changes=[{"email_id": "", "label_name": "Important"}]
            )
        assert "email_id" in str(exc_info.value).lower()

    def test_reject_empty_label_name(self):
        """Reject change with empty label_name."""
        with pytest.raises(ValidationError) as exc_info:
            BatchLabelUpdateRequest(
                changes=[{"email_id": "msg123", "label_name": ""}]
            )
        assert "label_name" in str(exc_info.value).lower()

    def test_reject_oversized_label_name(self):
        """Reject label_name exceeding 100 characters."""
        with pytest.raises(ValidationError) as exc_info:
            BatchLabelUpdateRequest(
                changes=[{"email_id": "msg123", "label_name": "X" * 101}]
            )
        assert "label_name" in str(exc_info.value).lower()


# ============================================================================
# BulkLabelRequest Tests
# ============================================================================

class TestBulkLabelRequest:
    """Tests for bulk label assignment (integer label_id)."""

    def test_valid_bulk_label(self):
        """Accept valid email_ids and label_id."""
        req = BulkLabelRequest(
            email_ids=["msg1", "msg2", "msg3"],
            label_id=7
        )
        assert len(req.email_ids) == 3
        assert req.label_id == 7

    def test_reject_empty_email_ids(self):
        """Reject empty email_ids array."""
        with pytest.raises(ValidationError) as exc_info:
            BulkLabelRequest(email_ids=[], label_id=5)
        assert "email_ids" in str(exc_info.value).lower()

    def test_reject_oversized_email_ids(self):
        """Reject more than 100 email_ids."""
        with pytest.raises(ValidationError) as exc_info:
            BulkLabelRequest(
                email_ids=[f"msg{i}" for i in range(101)],
                label_id=5
            )
        assert "email_ids" in str(exc_info.value).lower()

    def test_reject_empty_string_in_email_ids(self):
        """Reject email_ids containing empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            BulkLabelRequest(email_ids=["msg1", "", "msg3"], label_id=5)
        assert "email_ids" in str(exc_info.value).lower()

    def test_reject_zero_label_id(self):
        """Reject label_id of zero."""
        with pytest.raises(ValidationError) as exc_info:
            BulkLabelRequest(email_ids=["msg1"], label_id=0)
        assert "label_id" in str(exc_info.value).lower()


# ============================================================================
# CreateLabelRequest Tests
# ============================================================================

class TestCreateLabelRequest:
    """Tests for label creation with dual-field compatibility."""

    def test_valid_with_name_field(self):
        """Accept 'name' field."""
        req = CreateLabelRequest(name="Work")
        assert req.name == "Work"

    def test_valid_with_label_name_field(self):
        """Accept 'label_name' field for backward compatibility."""
        req = CreateLabelRequest(label_name="Personal")
        assert req.name == "Personal"  # Normalized to 'name'

    def test_valid_with_both_fields(self):
        """Accept both fields, prefer 'name'."""
        req = CreateLabelRequest(name="Primary", label_name="Secondary")
        assert req.name == "Primary"

    def test_reject_neither_field(self):
        """Reject request with neither name field."""
        with pytest.raises(ValidationError) as exc_info:
            CreateLabelRequest()
        assert "name" in str(exc_info.value).lower()

    def test_valid_hex_color(self):
        """Accept valid hex color codes."""
        req = CreateLabelRequest(name="Red", color="#FF0000")
        assert req.color == "#FF0000"

    def test_accept_lowercase_hex(self):
        """Accept lowercase hex color."""
        req = CreateLabelRequest(name="Blue", color="#0000ff")
        assert req.color == "#0000ff"

    def test_reject_invalid_hex_color(self):
        """Reject invalid hex color formats."""
        with pytest.raises(ValidationError) as exc_info:
            CreateLabelRequest(name="Bad", color="red")
        assert "color" in str(exc_info.value).lower()

    def test_reject_short_hex_color(self):
        """Reject 3-digit hex codes (require 6 digits)."""
        with pytest.raises(ValidationError) as exc_info:
            CreateLabelRequest(name="Short", color="#F00")
        assert "color" in str(exc_info.value).lower()

    def test_reject_oversized_label_name(self):
        """Reject label name exceeding 100 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CreateLabelRequest(name="X" * 101)
        assert "name" in str(exc_info.value).lower()


# ============================================================================
# UpdateDeleteModeRequest Tests
# ============================================================================

class TestUpdateDeleteModeRequest:
    """Tests for delete mode preference validation."""

    def test_valid_trash_mode(self):
        """Accept 'trash' mode."""
        req = UpdateDeleteModeRequest(mode="trash")
        assert req.mode == "trash"

    def test_valid_permanent_mode(self):
        """Accept 'permanent' mode."""
        req = UpdateDeleteModeRequest(mode="permanent")
        assert req.mode == "permanent"

    def test_reject_invalid_mode(self):
        """Reject mode values outside allowed literals."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateDeleteModeRequest(mode="archive")
        assert "mode" in str(exc_info.value).lower()

    def test_reject_missing_mode(self):
        """Reject request without mode field."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateDeleteModeRequest()
        assert "mode" in str(exc_info.value).lower()


# ============================================================================
# BatchDeleteRequest Tests
# ============================================================================

class TestBatchDeleteRequest:
    """Tests for filter-based batch deletion."""

    def test_valid_label_mode(self):
        """Accept 'label' mode with value."""
        req = BatchDeleteRequest(mode="label", value="Spam")
        assert req.mode == "label"
        assert req.value == "Spam"

    def test_valid_sender_mode(self):
        """Accept 'sender' mode with value."""
        req = BatchDeleteRequest(mode="sender", value="scammer@example.com")
        assert req.mode == "sender"
        assert req.value == "scammer@example.com"

    def test_reject_invalid_mode(self):
        """Reject mode values outside allowed literals."""
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteRequest(mode="invalid", value="test")
        assert "mode" in str(exc_info.value)

    def test_reject_empty_value(self):
        """Reject empty value string."""
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteRequest(mode="label", value="")
        assert "value" in str(exc_info.value)

    def test_reject_missing_mode(self):
        """Reject request without mode field."""
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteRequest(value="test")
        assert "mode" in str(exc_info.value)

    def test_reject_missing_value(self):
        """Reject request without value field."""
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteRequest(mode="label")
        assert "value" in str(exc_info.value)


# ============================================================================
# Bulk Operations (Delete/Safe/Quarantine) Tests
# ============================================================================

class TestBulkOperations:
    """Tests for bulk delete, mark-safe, and quarantine operations."""

    def test_valid_bulk_delete(self):
        """Accept valid bulk delete request."""
        req = BulkDeleteRequest(email_ids=["msg1", "msg2"])
        assert len(req.email_ids) == 2

    def test_valid_bulk_mark_safe(self):
        """Accept valid bulk mark-safe request."""
        req = BulkMarkSafeRequest(email_ids=["msg1", "msg2"])
        assert len(req.email_ids) == 2

    def test_valid_bulk_quarantine(self):
        """Accept valid bulk quarantine request."""
        req = BulkQuarantineRequest(email_ids=["msg1", "msg2"])
        assert len(req.email_ids) == 2

    def test_reject_empty_bulk_delete(self):
        """Reject bulk delete with empty array."""
        with pytest.raises(ValidationError) as exc_info:
            BulkDeleteRequest(email_ids=[])
        assert "email_ids" in str(exc_info.value).lower()

    def test_reject_oversized_bulk_operations(self):
        """Reject bulk operations exceeding 100 items."""
        large_ids = [f"msg{i}" for i in range(101)]
        
        with pytest.raises(ValidationError):
            BulkDeleteRequest(email_ids=large_ids)
        
        with pytest.raises(ValidationError):
            BulkMarkSafeRequest(email_ids=large_ids)
        
        with pytest.raises(ValidationError):
            BulkQuarantineRequest(email_ids=large_ids)

    def test_reject_empty_strings_in_bulk_operations(self):
        """Reject bulk operations with empty string IDs."""
        with pytest.raises(ValidationError):
            BulkDeleteRequest(email_ids=["msg1", "", "msg3"])
        
        with pytest.raises(ValidationError):
            BulkMarkSafeRequest(email_ids=["msg1", "", "msg3"])
        
        with pytest.raises(ValidationError):
            BulkQuarantineRequest(email_ids=["", "msg2"])


# ============================================================================
# AIRewriteRequest Tests
# ============================================================================

class TestAIRewriteRequest:
    """Tests for AI rewrite validation."""

    def test_valid_rewrite_request(self):
        """Accept valid text and instruction."""
        req = AIRewriteRequest(
            text="Hello, this is the email body text.",
            instruction="Make it more formal"
        )
        assert req.text == "Hello, this is the email body text."
        assert req.instruction == "Make it more formal"

    def test_reject_empty_text(self):
        """Reject empty text."""
        with pytest.raises(ValidationError) as exc_info:
            AIRewriteRequest(text="", instruction="Rewrite")
        assert "text" in str(exc_info.value).lower()

    def test_reject_oversized_text(self):
        """Reject text exceeding 50000 characters."""
        with pytest.raises(ValidationError) as exc_info:
            AIRewriteRequest(
                text="X" * 50001,
                instruction="Rewrite"
            )
        assert "text" in str(exc_info.value).lower()

    def test_reject_oversized_instruction(self):
        """Reject instruction exceeding 2000 characters."""
        with pytest.raises(ValidationError) as exc_info:
            AIRewriteRequest(
                text="Email body",
                instruction="X" * 2001
            )
        assert "instruction" in str(exc_info.value).lower()

    def test_accept_max_length_instruction(self):
        """Accept instruction at exactly 2000 characters."""
        req = AIRewriteRequest(
            text="Email body",
            instruction="X" * 2000
        )
        assert len(req.instruction) == 2000


# ============================================================================
# ReanalyzeRequest Tests
# ============================================================================

class TestReanalyzeRequest:
    """Tests for email reanalysis validation."""

    def test_valid_without_force(self):
        """Accept request without force flag (defaults to False)."""
        req = ReanalyzeRequest()
        assert req.force is False

    def test_valid_with_force_true(self):
        """Accept request with force=True."""
        req = ReanalyzeRequest(force=True)
        assert req.force is True

    def test_valid_with_force_false(self):
        """Accept request with explicit force=False."""
        req = ReanalyzeRequest(force=False)
        assert req.force is False

    def test_reject_non_boolean_force(self):
        """Reject invalid force values that can't be coerced to boolean."""
        with pytest.raises(ValidationError) as exc_info:
            ReanalyzeRequest(force={"invalid": "object"})
        assert "force" in str(exc_info.value).lower()
