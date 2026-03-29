from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


CHAT_LOG_SCHEMA_DEFAULTS = {
    "request_id": None,
    "conversation_id": None,
    "lang": None,
    "page": None,
    "route": None,
    "tool": None,
    "faq_file": None,
    "faq_id": None,
    "faq_score": None,
    "price_min": None,
    "price_max": None,
    "conversion_step": None,
    "lead_id": None,
    "source": None,
    "duration_ms": None,
    "response_length": None,
    "success": None,
    "error_type": None,
    "last_user_message": None,
}


def _serialize_chat_log(event: str, context: dict[str, Any]) -> str:
    normalized_context = dict(context)
    if "path" in normalized_context and "route" not in normalized_context:
        normalized_context["route"] = normalized_context.pop("path")

    payload = {
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **CHAT_LOG_SCHEMA_DEFAULTS,
        **normalized_context,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def log_chat_event(logger: logging.Logger | None, event: str, **context: Any) -> None:
    if not logger:
        return
    logger.info(_serialize_chat_log(event, context))


def log_chat_exception(logger: logging.Logger | None, event: str, **context: Any) -> None:
    if not logger:
        return
    logger.exception(_serialize_chat_log(event, context))
