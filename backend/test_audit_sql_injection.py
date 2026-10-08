"""Regression tests for audit filter validation and SQL injection safety."""

import pytest

import audit


def test_audit_filter_allowlist_is_explicit():
    assert audit.ALLOWED_AUDIT_FILTERS == {
        "action",
        "severity",
        "timestamp",
        "user_id",
    }


def test_unknown_audit_filter_key_is_rejected():
    with pytest.raises(ValueError, match="Unsupported audit filter"):
        audit._build_audit_filter_clause({"action": "auth.login", "order_by": "user_id"})


def test_filter_values_are_parameters_not_sql():
    where_sql, params = audit._build_audit_filter_clause({
        "user_id": 7,
        "action": "' OR '1'='1",
    })

    assert "' OR '1'='1" not in where_sql
    assert where_sql == "user_id = %s AND action = %s"
    assert params == [7, "' OR '1'='1"]
