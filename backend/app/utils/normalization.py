import json
import re
from typing import Any

EMAIL_LOG_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_LOG_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)")


def normalize_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def sanitize_chat_log_text(value: str | None, max_length: int = 160) -> str:
    text = " ".join((value or "").split()).strip()
    if not text:
        return ""
    text = EMAIL_LOG_PATTERN.sub("[redacted-email]", text)
    text = PHONE_LOG_PATTERN.sub("[redacted-phone]", text)
    if len(text) > max_length:
        return text[:max_length].rstrip() + "..."
    return text


def compact_json(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def normalize_form_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        return cleaned
    return value
