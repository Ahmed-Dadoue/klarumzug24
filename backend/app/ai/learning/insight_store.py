"""Manage learned insights from conversation analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import InsightDB

logger = logging.getLogger("klarumzug24")

# Categories the analyzer can produce
INSIGHT_CATEGORIES = {
    "faq_gap",               # Question customers ask that is NOT in the FAQ
    "common_objection",      # Frequent customer objection or concern
    "pricing_feedback",      # Feedback about prices (too high, surprising, etc.)
    "correction_pattern",    # Where the bot misunderstood and the user corrected
    "conversation_tip",      # General tip for improving conversations
    "service_insight",       # Insight about a specific service type
}

MAX_INSIGHTS_IN_PROMPT = 15
MAX_INSIGHT_LENGTH = 300


def save_insights(
    db: Session,
    insights: list[dict[str, Any]],
    source_conversation_ids: list[str] | None = None,
) -> int:
    """Save a batch of insights from the analyzer. Returns count saved."""
    saved = 0
    source_ids_json = json.dumps(source_conversation_ids or [], ensure_ascii=False)

    for item in insights:
        category = item.get("category", "")
        content = (item.get("content") or "").strip()
        confidence = float(item.get("confidence", 0.5))

        if category not in INSIGHT_CATEGORIES:
            continue
        if not content or len(content) > MAX_INSIGHT_LENGTH:
            continue
        if confidence < 0.3:
            continue

        # Deduplicate: skip if very similar insight already exists
        existing = (
            db.query(InsightDB)
            .filter(InsightDB.category == category, InsightDB.content == content)
            .first()
        )
        if existing:
            continue

        record = InsightDB(
            category=category,
            content=content,
            confidence=confidence,
            source_conversation_ids=source_ids_json,
        )
        db.add(record)
        saved += 1

    if saved:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to save insights batch")
            return 0
    return saved


def get_active_insights(db: Session, *, top_n: int = MAX_INSIGHTS_IN_PROMPT) -> list[InsightDB]:
    """Return top active insights sorted by confidence then usage."""
    return (
        db.query(InsightDB)
        .filter(InsightDB.active == True)  # noqa: E712
        .order_by(InsightDB.confidence.desc(), InsightDB.used_count.asc())
        .limit(top_n)
        .all()
    )


def build_insights_prompt_block(db: Session) -> str:
    """Build a prompt block from active insights to inject into the system prompt."""
    insights = get_active_insights(db)
    if not insights:
        return ""

    lines = ["\n## Gelernte Erkenntnisse aus bisherigen Kundengespraechen:"]
    for insight in insights:
        prefix = _category_label(insight.category)
        lines.append(f"- [{prefix}] {insight.content}")

    # Increment used_count
    for insight in insights:
        insight.used_count += 1
    try:
        db.commit()
    except Exception:
        db.rollback()

    return "\n".join(lines)


def increment_used_count(db: Session, insight_ids: list[int]) -> None:
    """Increment the used_count for the given insight IDs."""
    if not insight_ids:
        return
    db.query(InsightDB).filter(InsightDB.id.in_(insight_ids)).update(
        {InsightDB.used_count: InsightDB.used_count + 1},
        synchronize_session=False,
    )
    db.commit()


def deactivate_insight(db: Session, insight_id: int) -> bool:
    """Deactivate an insight (admin action). Returns True if found."""
    insight = db.query(InsightDB).filter(InsightDB.id == insight_id).first()
    if not insight:
        return False
    insight.active = False
    insight.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def activate_insight(db: Session, insight_id: int) -> bool:
    """Re-activate an insight. Returns True if found."""
    insight = db.query(InsightDB).filter(InsightDB.id == insight_id).first()
    if not insight:
        return False
    insight.active = True
    insight.deactivated_at = None
    db.commit()
    return True


def get_insight_stats(db: Session) -> dict[str, Any]:
    """Return summary statistics for insights."""
    total = db.query(InsightDB).count()
    active = db.query(InsightDB).filter(InsightDB.active == True).count()  # noqa: E712
    by_category: dict[str, int] = {}
    for row in (
        db.query(InsightDB.category, db.query(InsightDB).filter(InsightDB.active == True).count())  # noqa: E712
    ):
        pass  # handled below

    categories = (
        db.query(InsightDB.category)
        .filter(InsightDB.active == True)  # noqa: E712
        .distinct()
        .all()
    )
    for (cat,) in categories:
        by_category[cat] = (
            db.query(InsightDB)
            .filter(InsightDB.category == cat, InsightDB.active == True)  # noqa: E712
            .count()
        )

    return {
        "total_insights": total,
        "active": active,
        "inactive": total - active,
        "by_category": by_category,
    }


def list_insights(
    db: Session,
    *,
    category: str | None = None,
    active_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return insights as dicts for the admin API."""
    query = db.query(InsightDB)
    if category:
        query = query.filter(InsightDB.category == category)
    if active_only:
        query = query.filter(InsightDB.active == True)  # noqa: E712
    query = query.order_by(InsightDB.confidence.desc()).limit(limit)

    return [
        {
            "id": i.id,
            "category": i.category,
            "content": i.content,
            "confidence": i.confidence,
            "active": i.active,
            "used_count": i.used_count,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in query.all()
    ]


def _category_label(category: str) -> str:
    labels = {
        "faq_gap": "FAQ-Luecke",
        "common_objection": "Haeufiger Einwand",
        "pricing_feedback": "Preis-Feedback",
        "correction_pattern": "Korrektur-Muster",
        "conversation_tip": "Gespraechs-Tipp",
        "service_insight": "Service-Erkenntnis",
    }
    return labels.get(category, category)
