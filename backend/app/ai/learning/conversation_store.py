"""Save and retrieve complete conversations for the learning cycle."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import ConversationDB

logger = logging.getLogger("klarumzug24")


def save_conversation(
    db: Session,
    *,
    conversation_id: str,
    messages: list[dict[str, str]],
    conversation_type: str = "real_user",
    source_label: str | None = None,
    test_run_id: str | None = None,
    service_type: str | None = None,
    intent_type: str | None = None,
    source_used: str | None = None,
    helper_path: str | None = None,
    fallback_used: bool = False,
    telemetry: dict[str, Any] | None = None,
    outcome: str = "unknown",
    language: str = "de",
) -> ConversationDB | None:
    """Save or update a conversation snapshot. Returns the record or None on error."""
    if not conversation_id or not messages:
        return None

    try:
        existing = (
            db.query(ConversationDB)
            .filter(ConversationDB.conversation_id == conversation_id)
            .first()
        )
        messages_json = json.dumps(messages, ensure_ascii=False)
        telemetry_json = json.dumps(telemetry or {}, ensure_ascii=False)

        if existing:
            existing.messages_json = messages_json
            existing.message_count = len(messages)
            existing.conversation_type = conversation_type or existing.conversation_type
            existing.source_label = source_label or existing.source_label
            existing.test_run_id = test_run_id or existing.test_run_id
            existing.service_type = service_type or existing.service_type
            existing.intent_type = intent_type or existing.intent_type
            existing.source_used = source_used or existing.source_used
            existing.helper_path = helper_path or existing.helper_path
            existing.fallback_used = bool(fallback_used)
            existing.telemetry_json = telemetry_json
            existing.outcome = outcome if outcome != "unknown" else existing.outcome
            existing.language = language
            db.commit()
            db.refresh(existing)
            return existing

        record = ConversationDB(
            conversation_id=conversation_id,
            conversation_type=conversation_type or "real_user",
            source_label=source_label,
            test_run_id=test_run_id,
            messages_json=messages_json,
            service_type=service_type,
            intent_type=intent_type,
            source_used=source_used,
            helper_path=helper_path,
            fallback_used=bool(fallback_used),
            telemetry_json=telemetry_json,
            outcome=outcome,
            language=language,
            message_count=len(messages),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        logger.exception("Failed to save conversation %s", conversation_id)
        return None


def get_unanalyzed_conversations(db: Session, *, limit: int = 50) -> list[ConversationDB]:
    """Return conversations that haven't been analyzed yet."""
    return (
        db.query(ConversationDB)
        .filter(ConversationDB.analyzed == False)  # noqa: E712
        .filter(ConversationDB.message_count >= 2)
        .order_by(ConversationDB.created_at.asc())
        .limit(limit)
        .all()
    )


def mark_analyzed(db: Session, conversation_ids: list[str]) -> int:
    """Mark conversations as analyzed. Returns count of updated rows."""
    if not conversation_ids:
        return 0
    count = (
        db.query(ConversationDB)
        .filter(ConversationDB.conversation_id.in_(conversation_ids))
        .update(
            {
                ConversationDB.analyzed: True,
                ConversationDB.analyzed_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return count


def get_conversation_stats(db: Session) -> dict[str, Any]:
    """Return summary statistics for the learning system."""
    total = db.query(ConversationDB).count()
    analyzed = db.query(ConversationDB).filter(ConversationDB.analyzed == True).count()  # noqa: E712
    pending = total - analyzed
    by_type_rows = (
        db.query(ConversationDB.conversation_type)
        .all()
    )
    by_type: dict[str, int] = {}
    for row in by_type_rows:
        conversation_type = row[0] or "unknown"
        by_type[conversation_type] = by_type.get(conversation_type, 0) + 1
    return {
        "total_conversations": total,
        "analyzed": analyzed,
        "pending_analysis": pending,
        "by_conversation_type": by_type,
    }
