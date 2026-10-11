import logging

from logger_setup import SecretRedactionFilter, redact_secrets


def test_redact_secrets_masks_api_keys_tokens_and_emails():
    raw = "key=AIzaSyABC1234567890 token=sk-secret-value Bearer abc.def.ghi email=user@example.com"
    redacted = redact_secrets(raw)
    assert "AIzaSy" not in redacted
    assert "sk-secret-value" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "user@example.com" not in redacted
    assert "[REDACTED]" in redacted


def test_logging_filter_rewrites_formatted_message():
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "email=%s", ("user@example.com",), None)
    assert SecretRedactionFilter().filter(record)
    assert "user@example.com" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
