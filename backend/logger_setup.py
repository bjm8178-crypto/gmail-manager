import logging
import os
import re
from typing import Any
from logging.handlers import RotatingFileHandler


_REDACTION_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{10,}"), "[REDACTED]"),
    (re.compile(r"\bsk-[0-9A-Za-z_-]{8,}"), "[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED]"),
)


def redact_secrets(value: Any) -> str:
    """Return log-safe text with credentials and direct identifiers removed."""
    text = str(value)
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.getMessage())
        record.args = ()
        return True


def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setLevel(log_level)
        
        # Create logs directory if it doesn't exist
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
        
        # StreamHandler for stdout (Railway logs dashboard, local development)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        ch.addFilter(SecretRedactionFilter())
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # RotatingFileHandler for persistent disk logs
        try:
            fh = RotatingFileHandler(
                filename=os.path.join(logs_dir, 'app.log'),
                maxBytes=10 * 1024 * 1024,  # 10MB per file
                backupCount=5,  # Keep app.log, app.log.1, ..., app.log.5
                encoding='utf-8'
            )
            fh.setLevel(log_level)
            fh.addFilter(SecretRedactionFilter())
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            # If file handler fails (permissions, disk full), continue with StreamHandler only
            logger.warning(f"Failed to create RotatingFileHandler: {e}")
        
        logger.propagate = False
    return logger
