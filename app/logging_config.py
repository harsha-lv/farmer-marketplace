"""Structured JSON logging with request_id/trace_id correlation and PII redaction.

Applies strict PII filtering across every log record:
- Aadhaar (12-digit Indian national identity numbers)
- Farmer phone (Indian 10-digit mobile numbers with optional country code)
- API keys & secrets (ak_live_..., Bearer tokens, private secrets)
- Bank account numbers (9-18 digits)
"""

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

# PII Redaction Regular Expressions
AADHAAR_REGEX = re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")
PHONE_REGEX = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")
API_KEY_REGEX = re.compile(
    r"\b(?:ak_live_[a-zA-Z0-9_\-]{16,}|sk_[a-zA-Z0-9_\-]{16,}|key-[a-zA-Z0-9_\-]{8,})\b"
)
BEARER_TOKEN_REGEX = re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b", re.IGNORECASE)
SECRET_ASSIGNMENT_REGEX = re.compile(
    r"(?i)\b(api[_-]?key|client[_-]?secret|secret[_-]?key|password|passwd|authorization)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
)
BANK_ACCOUNT_WITH_LABEL_REGEX = re.compile(
    r"(?i)\b(acc(?:ount)?|acct|a/c|bank)\s*[:#\-_]?\s*(\d{9,18})\b"
)
STANDALONE_BANK_ACCOUNT_REGEX = re.compile(r"\b\d{11,18}\b")

import contextvars

# Canonical context variable to hold the request_id across async request lifecycle
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_otel_trace_and_span_id() -> tuple[str, str]:
    """Retrieve trace_id and span_id from active OpenTelemetry context if available."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span_ctx = span.get_span_context() if span else None
        if span_ctx and span_ctx.is_valid:
            trace_id = format(span_ctx.trace_id, "032x")
            span_id = format(span_ctx.span_id, "016x")
            return trace_id, span_id
    except Exception:
        pass
    return "", ""


def redact_pii(text: str) -> str:
    """Scrub PII (Aadhaar, Phone, API Keys, Bank Account numbers) from text."""
    if not isinstance(text, str) or not text:
        return text

    # Redact Aadhaar first (12 digits with optional spaces/hyphens)
    text = AADHAAR_REGEX.sub("[REDACTED_AADHAAR]", text)

    # Redact Bearer tokens and API keys
    text = BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
    text = API_KEY_REGEX.sub("[REDACTED_API_KEY]", text)
    text = SECRET_ASSIGNMENT_REGEX.sub(r'\1="[REDACTED_SECRET]"', text)

    # Redact Phone numbers
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)

    # Redact Bank Accounts
    text = BANK_ACCOUNT_WITH_LABEL_REGEX.sub(r"\1 [REDACTED_BANK_ACCOUNT]", text)
    # Standalone 11-18 digit numbers that are not part of an ISO timestamp or already redacted
    def _mask_standalone_account(m: re.Match[str]) -> str:
        s = m.group(0)
        # Avoid masking common 13-digit Unix ms epochs if recent (e.g. 17... or 18...)
        if len(s) == 13 and (s.startswith("17") or s.startswith("18")):
            return s
        return "[REDACTED_BANK_ACCOUNT]"

    text = STANDALONE_BANK_ACCOUNT_REGEX.sub(_mask_standalone_account, text)
    return text


def sanitize_object(data: Any) -> Any:
    """Recursively redact PII from dictionaries, lists, tuples, and strings."""
    if isinstance(data, str):
        return redact_pii(data)
    elif isinstance(data, dict):
        return {k: sanitize_object(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_object(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(sanitize_object(item) for item in data)
    return data


class PIIRedactionFilter(logging.Filter):
    """Logging filter applied to every log record to redact PII before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_pii(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_object(record.args)
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(sanitize_object(arg) for arg in record.args)

        # Also scrub any extra attributes attached to the LogRecord
        for key in list(record.__dict__.keys()):
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            ):
                val = getattr(record, key)
                if isinstance(val, (str, dict, list, tuple)):
                    setattr(record, key, sanitize_object(val))

        return True


class JSONLogFormatter(logging.Formatter):
    """Custom logging formatter that produces structured JSON output.

    Correlates request_id and trace_id with every log entry and applies PII redaction.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = ""
        try:
            req_id = request_id_ctx.get("")
        except Exception:
            pass
        if not req_id and hasattr(record, "request_id"):
            req_id = str(record.request_id)

        trace_id, span_id = get_otel_trace_and_span_id()
        if not trace_id and hasattr(record, "trace_id"):
            trace_id = str(record.trace_id)
        if not span_id and hasattr(record, "span_id"):
            span_id = str(record.span_id)

        raw_message = record.getMessage()
        sanitized_message = redact_pii(raw_message)

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_message,
            "request_id": req_id,
        }

        if trace_id:
            log_entry["trace_id"] = trace_id
        if span_id:
            log_entry["span_id"] = span_id

        # Carry forward any custom extra fields on record
        standard_keys = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "request_id",
            "trace_id",
            "span_id",
        }
        for k, v in record.__dict__.items():
            if k not in standard_keys and not k.startswith("_"):
                log_entry[k] = sanitize_object(v)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(default_level: str | None = None) -> None:
    """Configure Python's root logger with JSON formatting, PII redaction, and trace correlation.

    - Emits structured JSON logs containing timestamp, level, logger, message, request_id, and trace_id.
    - Reads log level from LOG_LEVEL or APP_LOG_LEVEL environment variable (default: INFO).
    - Attaches PIIRedactionFilter to every stream handler.
    """
    level_name = os.getenv("LOG_LEVEL", os.getenv("APP_LOG_LEVEL", default_level or "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clean existing handlers to prevent duplicate output
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.addFilter(PIIRedactionFilter())
    stream_handler.setFormatter(JSONLogFormatter())

    root_logger.addHandler(stream_handler)
