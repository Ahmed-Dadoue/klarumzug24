"""Confidence Decay System for Dode Learning Insights.

Implements time-based and feedback-based confidence decay.
Older, unused, or unsuccessful insights gradually lose confidence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import InsightDB

logger = logging.getLogger("klarumzug24")

# Decay configuration
DECAY_CONFIG = {
    "time_decay_days": 30,       # Start decay after 30 days without validation
    "time_decay_rate": 0.05,     # Lose 5% confidence per period after threshold
    "min_confidence": 0.1,       # Never drop below 10%
    "success_boost": 0.05,       # Boost confidence by 5% per success
    "failure_penalty": 0.1,      # Reduce confidence by 10% per failure
    "auto_deactivate_threshold": 0.15,  # Auto-deactivate below 15%
    "validation_period_days": 7,  # Validate insights weekly
}


def calculate_time_decay(
    created_at: datetime,
    last_validated_at: datetime | None,
    current_confidence: float,
) -> float:
    """Calculate confidence decay based on time since last validation."""
    now = datetime.now(timezone.utc)
    reference_date = last_validated_at or created_at
    
    # Ensure timezone-aware comparison
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    
    days_since = (now - reference_date).days
    decay_threshold = DECAY_CONFIG["time_decay_days"]
    
    if days_since <= decay_threshold:
        return current_confidence
    
    # Calculate number of decay periods
    decay_periods = (days_since - decay_threshold) // DECAY_CONFIG["validation_period_days"]
    decay_amount = decay_periods * DECAY_CONFIG["time_decay_rate"]
    
    new_confidence = max(DECAY_CONFIG["min_confidence"], current_confidence - decay_amount)
    return round(new_confidence, 3)


def calculate_feedback_adjustment(
    current_confidence: float,
    success_count: int,
    failure_count: int,
    initial_confidence: float | None = None
) -> float:
    """Adjust confidence based on success/failure feedback."""
    base = initial_confidence or current_confidence
    
    success_boost = success_count * DECAY_CONFIG["success_boost"]
    failure_penalty = failure_count * DECAY_CONFIG["failure_penalty"]
    
    adjusted = base + success_boost - failure_penalty
    adjusted = max(DECAY_CONFIG["min_confidence"], min(1.0, adjusted))
    
    return round(adjusted, 3)


def update_insight_confidence(
    db: Session,
    insight_id: int,
    *,
    was_successful: bool | None = None,
) -> dict[str, Any] | None:
    """Update an insight's confidence based on time decay and optional feedback.
    
    Args:
        db: Database session
        insight_id: Insight to update
        was_successful: If provided, record success/failure feedback
    
    Returns:
        Updated insight info or None if not found
    """
    insight = db.query(InsightDB).filter(InsightDB.id == insight_id).first()
    if not insight:
        return None
    
    old_confidence = insight.confidence
    
    # Record initial confidence if not set
    if insight.initial_confidence is None:
        insight.initial_confidence = insight.confidence
    
    # Record feedback if provided
    if was_successful is not None:
        if was_successful:
            insight.success_count = (insight.success_count or 0) + 1
        else:
            insight.failure_count = (insight.failure_count or 0) + 1
        insight.last_validated_at = datetime.now(timezone.utc)
    
    # Apply time decay
    decayed = calculate_time_decay(
        insight.created_at,
        insight.last_validated_at,
        insight.confidence
    )
    
    # Apply feedback adjustment
    final_confidence = calculate_feedback_adjustment(
        decayed,
        insight.success_count or 0,
        insight.failure_count or 0,
        insight.initial_confidence
    )
    
    insight.confidence = final_confidence
    
    # Auto-deactivate if confidence too low
    auto_deactivated = False
    if final_confidence < DECAY_CONFIG["auto_deactivate_threshold"] and insight.active:
        insight.active = False
        insight.deactivated_at = datetime.now(timezone.utc)
        auto_deactivated = True
        logger.info(f"Auto-deactivated insight {insight_id} (confidence: {final_confidence})")
    
    db.commit()
    db.refresh(insight)
    
    return {
        "id": insight.id,
        "old_confidence": old_confidence,
        "new_confidence": final_confidence,
        "change": round(final_confidence - old_confidence, 3),
        "success_count": insight.success_count,
        "failure_count": insight.failure_count,
        "auto_deactivated": auto_deactivated,
        "active": insight.active,
    }


def apply_decay_to_all(db: Session) -> dict[str, Any]:
    """Apply time decay to all active insights. Run periodically (e.g., daily)."""
    active_insights = db.query(InsightDB).filter(InsightDB.active == True).all()  # noqa: E712
    
    updated = 0
    deactivated = 0
    total_decay = 0.0
    
    for insight in active_insights:
        result = update_insight_confidence(db, insight.id)
        if result:
            updated += 1
            total_decay += abs(result["change"])
            if result["auto_deactivated"]:
                deactivated += 1
    
    return {
        "processed": updated,
        "deactivated": deactivated,
        "total_decay": round(total_decay, 3),
        "avg_decay": round(total_decay / updated, 3) if updated > 0 else 0,
    }


def record_insight_feedback(
    db: Session,
    insight_id: int,
    was_successful: bool,
) -> dict[str, Any] | None:
    """Record success/failure feedback for an insight."""
    return update_insight_confidence(db, insight_id, was_successful=was_successful)


def get_decay_status(db: Session) -> dict[str, Any]:
    """Get overview of insight decay status."""
    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=DECAY_CONFIG["time_decay_days"])
    
    active_insights = db.query(InsightDB).filter(InsightDB.active == True).all()  # noqa: E712
    
    stale_count = 0
    healthy_count = 0
    critical_count = 0
    
    for insight in active_insights:
        ref_date = insight.last_validated_at or insight.created_at
        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)
        
        if ref_date < threshold_date:
            stale_count += 1
        
        if insight.confidence >= 0.5:
            healthy_count += 1
        elif insight.confidence < DECAY_CONFIG["auto_deactivate_threshold"] + 0.1:
            critical_count += 1
    
    avg_confidence = 0.0
    if active_insights:
        avg_confidence = sum(i.confidence for i in active_insights) / len(active_insights)
    
    return {
        "active_insights": len(active_insights),
        "stale_count": stale_count,
        "healthy_count": healthy_count,
        "critical_count": critical_count,
        "avg_confidence": round(avg_confidence, 3),
        "decay_threshold_days": DECAY_CONFIG["time_decay_days"],
        "auto_deactivate_threshold": DECAY_CONFIG["auto_deactivate_threshold"],
    }


def boost_insight(db: Session, insight_id: int) -> dict[str, Any] | None:
    """Manually boost an insight's confidence (admin action)."""
    insight = db.query(InsightDB).filter(InsightDB.id == insight_id).first()
    if not insight:
        return None
    
    old_confidence = insight.confidence
    insight.confidence = min(1.0, insight.confidence + 0.2)
    insight.last_validated_at = datetime.now(timezone.utc)
    
    # Reactivate if was deactivated
    if not insight.active:
        insight.active = True
        insight.deactivated_at = None
    
    db.commit()
    db.refresh(insight)
    
    return {
        "id": insight.id,
        "old_confidence": old_confidence,
        "new_confidence": insight.confidence,
        "active": insight.active,
    }
