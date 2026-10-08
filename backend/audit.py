"""
audit.py — Phase 6: Audit Logging Module
Comprehensive audit logging for security events, compliance (GDPR Article 30), and incident investigation.

Logs all security-sensitive actions with IP address, user agent, timestamp, and metadata.
90-day retention policy (configurable).
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request

logger = logging.getLogger(__name__)

# Audit log severity levels
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

# Action types for filtering
ACTION_LOGIN = "auth.login"
ACTION_LOGOUT = "auth.logout"
ACTION_LOGIN_FAILED = "auth.login_failed"
ACTION_EMAIL_DELETE = "email.delete"
ACTION_EMAIL_TRASH = "email.trash"
ACTION_EMAIL_MARK_SAFE = "email.mark_safe"
ACTION_EMAIL_QUARANTINE = "email.quarantine"
ACTION_LABEL_APPLY = "label.apply"
ACTION_LABEL_REMOVE = "label.remove"
ACTION_BULK_DELETE = "bulk.delete"
ACTION_BULK_MARK_SAFE = "bulk.mark_safe"
ACTION_BULK_QUARANTINE = "bulk.quarantine"
ACTION_BULK_LABEL = "bulk.label"
ACTION_DATABASE_RESET = "database.reset"
ACTION_AI_REWRITE = "ai.rewrite"

ALLOWED_AUDIT_FILTERS = {"action", "severity", "timestamp", "user_id"}


def _build_audit_filter_clause(filters: Dict[str, Any]) -> tuple[str, list[Any]]:
    """Build a fixed-column audit filter clause with parameterized values."""
    unknown = set(filters) - ALLOWED_AUDIT_FILTERS
    if unknown:
        raise ValueError(f"Unsupported audit filter: {sorted(unknown)[0]}")

    clauses = []
    params = []
    for field in ("user_id", "action", "severity", "timestamp"):
        value = filters.get(field)
        if value is None:
            continue
        if field == "timestamp" and isinstance(value, dict):
            for operator, key in ((">=", "gte"), ("<=", "lte")):
                if value.get(key) is not None:
                    clauses.append(f"timestamp {operator} %s")
                    params.append(value[key])
            continue
        clauses.append(f"{field} = %s")
        params.append(value)
    return " AND ".join(clauses) or "1 = 1", params


def _get_db():
    """Get database connection from database module."""
    from database import _get_connection
    return _get_connection()


def _execute(cursor, query, params=None):
    """Execute a query with the active database's placeholder syntax."""
    from database import _execute as execute
    execute(cursor, query, params)


def _release_db(db):
    """Release a connection using the active database backend."""
    from database import _release_connection
    _release_connection(db)


def log_event(
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    severity: str = SEVERITY_INFO,
    request: Optional[Request] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Log an audit event to the audit_log table.
    
    Args:
        user_id: User who performed the action (None for unauthenticated events)
        action: Action identifier (e.g., 'auth.login', 'email.delete')
        resource_type: Type of resource affected (e.g., 'email', 'label')
        resource_id: ID of the affected resource
        metadata: Additional context as JSON-serializable dict
        severity: 'info', 'warning', or 'critical'
        request: FastAPI Request object (extracts IP and User-Agent automatically)
        ip_address: Manual IP override (if request not available)
        user_agent: Manual User-Agent override
    
    Examples:
        log_event(user_id=1, action="auth.login", severity="info", request=request)
        log_event(user_id=1, action="email.delete", resource_type="email", 
                  resource_id="abc123", metadata={"subject": "Test"}, request=request)
        log_event(user_id=1, action="bulk.delete", metadata={"count": 15}, request=request)
    """
    db = None
    try:
        # Extract IP and User-Agent from request if available
        if request:
            if not ip_address:
                ip_address = request.client.host if request.client else None
            if not user_agent:
                user_agent = request.headers.get("user-agent")
        
        # Serialize metadata to JSON
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Insert audit log entry
        db = _get_db()
        cursor = db.cursor()
        _execute(cursor, """
            INSERT INTO audit_log (
                user_id, action, resource_type, resource_id, 
                ip_address, user_agent, metadata, severity, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            action,
            resource_type,
            resource_id,
            ip_address,
            user_agent,
            metadata_json,
            severity,
            datetime.utcnow().isoformat(),
        ))
        db.commit()
        
        # Log to application logs for critical events
        if severity == SEVERITY_CRITICAL:
            logger.warning(
                f"[AUDIT CRITICAL] user_id={user_id} action={action} "
                f"resource={resource_type}/{resource_id} ip={ip_address}"
            )
    
    except Exception as e:
        # Audit logging failures should not break the application
        logger.error(f"[AUDIT] Failed to log event {action}: {type(e).__name__}: {e}")
    finally:
        if db is not None:
            _release_db(db)


def get_user_audit_logs(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    action_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve audit logs for a specific user.
    
    Args:
        user_id: User ID to fetch logs for
        limit: Maximum number of logs to return (default 50, max 200)
        offset: Pagination offset
        action_filter: Filter by action type (e.g., 'auth.login')
        severity_filter: Filter by severity ('info', 'warning', 'critical')
        start_date: Filter logs after this date (ISO format)
        end_date: Filter logs before this date (ISO format)
    
    Returns:
        List of audit log entries with all fields
    """
    db = None
    try:
        db = _get_db()
        cursor = db.cursor()
        
        # Build a fixed-column, parameterized WHERE clause
        filters = {
            "user_id": user_id,
            "action": action_filter,
            "severity": severity_filter,
            "timestamp": {"gte": start_date, "lte": end_date},
        }
        where_sql, params = _build_audit_filter_clause(filters)
        
        # Cap limit at 200 to prevent abuse
        limit = min(limit, 200)
        
        # Fetch logs with pagination
        _execute(cursor, f"""
            SELECT 
                log_id, user_id, timestamp, action, resource_type, 
                resource_id, ip_address, user_agent, metadata, severity
            FROM audit_log
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """, (*params, limit, offset))
        
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        logs = []
        for row in rows:
            logs.append({
                "log_id": row["log_id"],
                "user_id": row["user_id"],
                "timestamp": row["timestamp"],
                "action": row["action"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                "severity": row["severity"],
            })
        
        return logs
    
    except Exception as e:
        logger.error(f"[AUDIT] Failed to fetch logs for user {user_id}: {type(e).__name__}: {e}")
        return []
    finally:
        if db is not None:
            _release_db(db)


def get_audit_log_count(
    user_id: int,
    action_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """
    Count total audit logs matching filters (for pagination).
    
    Args:
        user_id: User ID to count logs for
        action_filter: Filter by action type
        severity_filter: Filter by severity
        start_date: Filter logs after this date
        end_date: Filter logs before this date
    
    Returns:
        Total count of matching logs
    """
    db = None
    try:
        db = _get_db()
        cursor = db.cursor()
        
        # Build the same fixed-column, parameterized WHERE clause
        filters = {
            "user_id": user_id,
            "action": action_filter,
            "severity": severity_filter,
            "timestamp": {"gte": start_date, "lte": end_date},
        }
        where_sql, params = _build_audit_filter_clause(filters)
        
        _execute(cursor, f"""
            SELECT COUNT(*) AS count FROM audit_log
            WHERE {where_sql}
        """, params)
        
        return cursor.fetchone()["count"]
    
    except Exception as e:
        logger.error(f"[AUDIT] Failed to count logs for user {user_id}: {type(e).__name__}: {e}")
        return 0
    finally:
        if db is not None:
            _release_db(db)


def cleanup_old_logs(retention_days: int = 90) -> int:
    """
    Delete audit logs older than retention period.
    
    Args:
        retention_days: Number of days to retain logs (default 90 for GDPR compliance)
    
    Returns:
        Number of logs deleted
    """
    db = None
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
        
        db = _get_db()
        cursor = db.cursor()
        _execute(cursor, "DELETE FROM audit_log WHERE timestamp < %s", (cutoff_date,))
        deleted_count = cursor.rowcount
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"[AUDIT] Cleaned up {deleted_count} logs older than {retention_days} days")
        
        return deleted_count
    
    except Exception as e:
        logger.error(f"[AUDIT] Cleanup failed: {type(e).__name__}: {e}")
        return 0
    finally:
        if db is not None:
            _release_db(db)
