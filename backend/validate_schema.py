"""Validate that the deployment schema contains database.py's core tables."""

from pathlib import Path
import re
import sys


EXPECTED = {
    "users": {"user_id", "gmail_address", "token", "token_key_version", "token_encrypted_at"},
    "custom_labels": {"label_id", "user_id", "label_name"},
    "scan_cursor": {"cursor_id", "user_id", "last_page_token"},
    "analyzed_emails": {
        "email_id", "user_id", "label_id", "scam_score", "status", "applied_to_gmail",
        "last_applied_label_id", "source", "ml_confidence", "provider_used", "reasoning",
        "routing_decision", "v2_score", "analysis_status", "category_status", "url_scan_status",
        "urls_total", "urls_checked", "received_at", "user_decision", "gmail_sync_state",
        "gmail_sync_error", "gmail_sync_attempts", "last_synced_at", "attachment_risk",
        "attachment_details",
    },
    "url_cache": {"url_id", "email_id", "url", "is_safe"},
    "retry_queue": {"retry_id", "email_id", "retry_count", "last_attempted", "error_reason"},
    "dead_letter_queue": {"id", "email_id", "user_id", "error_message", "final_retry_count", "moved_at"},
    "ml_models": {"model_id", "version", "trained_at", "training_row_count", "model_blob"},
    "ml_disagreements": {"disagreement_id", "email_id", "ml_prediction", "logged_at"},
    "audit_log": {"log_id", "user_id", "timestamp", "action", "metadata", "severity"},
}


def validate(schema_path: Path) -> list[str]:
    text = schema_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for table, columns in EXPECTED.items():
        match = re.search(
            rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\);",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            errors.append(f"missing table: {table}")
            continue
        actual = {
            line.strip().split()[0]
            for line in match.group(1).splitlines()
            if line.strip() and not line.strip().startswith(("--", "PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE"))
        }
        missing = columns - actual
        if missing:
            errors.append(f"{table} missing columns: {', '.join(sorted(missing))}")
    return errors


if __name__ == "__main__":
    schema = Path(__file__).with_name("postgres_schema.sql")
    problems = validate(schema)
    if problems:
        print("Schema drift detected:")
        print("\n".join(f"- {problem}" for problem in problems))
        sys.exit(1)
    print(f"Schema validation passed: {len(EXPECTED)} tables checked")
