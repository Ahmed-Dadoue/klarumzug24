"""Auto-Feedback Loop for Dode Learning Cycle.

Automatically tracks which insights were used in a conversation
and records success/failure feedback based on conversation outcome.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import ConversationDB, InsightDB
from .confidence_decay import record_insight_feedback

logger = logging.getLogger("klarumzug24")

# Outcome classifications for auto-feedback
POSITIVE_OUTCOMES = {
    "lead_created",
    "booking_confirmed", 
    "contact_requested",
    "price_quoted",
    "faq_answered",
}

NEGATIVE_OUTCOMES = {
    "abandoned",
    "frustrated",
    "escalated",
    "no_response",
}

NEUTRAL_OUTCOMES = {
    "unknown",
    "ongoing",
    "info_provided",
}


def track_insight_usage(
    db: Session,
    conversation_id: str,
    insight_ids: list[int],
) -> None:
    """Record which insights were used in a conversation.
    
    Called when building the prompt with insights.
    Stores insight IDs in conversation for later feedback.
    """
    if not insight_ids:
        return
    
    conv = (
        db.query(ConversationDB)
        .filter(ConversationDB.conversation_id == conversation_id)
        .first()
    )
    
    # Note: For simplicity, we track this in memory/logs
    # In a fuller implementation, add a junction table
    logger.debug(
        f"Insights used in conversation {conversation_id}: {insight_ids}"
    )


def process_feedback_for_conversation(
    db: Session,
    conversation_id: str,
) -> dict[str, Any]:
    """Process automatic feedback for a completed conversation.
    
    Looks at conversation outcome and updates insight confidence
    for any insights that were used.
    """
    conv = (
        db.query(ConversationDB)
        .filter(ConversationDB.conversation_id == conversation_id)
        .first()
    )
    
    if not conv:
        return {"error": "Conversation not found"}
    
    outcome = conv.outcome
    
    # Determine if positive/negative/neutral outcome
    if outcome in POSITIVE_OUTCOMES:
        was_successful = True
    elif outcome in NEGATIVE_OUTCOMES:
        was_successful = False
    else:
        # Neutral outcomes don't affect insight confidence
        return {
            "conversation_id": conversation_id,
            "outcome": outcome,
            "feedback_applied": False,
            "reason": "neutral_outcome",
        }
    
    # Find insights that were active when this conversation occurred
    # (In a fuller implementation, track exact insights used per conversation)
    active_insights = (
        db.query(InsightDB)
        .filter(InsightDB.active == True)  # noqa: E712
        .filter(InsightDB.created_at <= conv.created_at)
        .all()
    )
    
    updated_count = 0
    for insight in active_insights:
        # Only update insights that were created before this conversation
        # and have been used at least once
        if insight.used_count > 0:
            record_insight_feedback(db, insight.id, was_successful)
            updated_count += 1
    
    return {
        "conversation_id": conversation_id,
        "outcome": outcome,
        "was_successful": was_successful,
        "insights_updated": updated_count,
        "feedback_applied": True,
    }


def batch_process_feedback(
    db: Session,
    limit: int = 50,
) -> dict[str, Any]:
    """Process feedback for conversations with known outcomes.
    
    Finds conversations that:
    1. Have a non-neutral outcome
    2. Haven't had feedback processed yet (using reward_score as indicator)
    """
    # Find conversations with positive/negative outcomes that haven't been scored
    positive_outcomes_list = list(POSITIVE_OUTCOMES)
    negative_outcomes_list = list(NEGATIVE_OUTCOMES)
    
    conversations = (
        db.query(ConversationDB)
        .filter(ConversationDB.outcome.in_(positive_outcomes_list + negative_outcomes_list))
        .filter(ConversationDB.reward_score == None)  # noqa: E711 - Not yet processed
        .order_by(ConversationDB.created_at.asc())
        .limit(limit)
        .all()
    )
    
    processed = 0
    positive = 0
    negative = 0
    
    for conv in conversations:
        result = process_feedback_for_conversation(db, conv.conversation_id)
        if result.get("feedback_applied"):
            processed += 1
            if result.get("was_successful"):
                positive += 1
            else:
                negative += 1
    
    return {
        "processed": processed,
        "positive_outcomes": positive,
        "negative_outcomes": negative,
    }


def update_conversation_outcome(
    db: Session,
    conversation_id: str,
    outcome: str,
) -> dict[str, Any] | None:
    """Update a conversation's outcome and optionally trigger feedback.
    
    Called when a conversation reaches a definitive state
    (lead created, abandoned, escalated, etc.)
    """
    conv = (
        db.query(ConversationDB)
        .filter(ConversationDB.conversation_id == conversation_id)
        .first()
    )
    
    if not conv:
        return None
    
    old_outcome = conv.outcome
    conv.outcome = outcome
    db.commit()
    
    # If moving from unknown/ongoing to definitive outcome, process feedback
    feedback_result = None
    if old_outcome in NEUTRAL_OUTCOMES and outcome not in NEUTRAL_OUTCOMES:
        feedback_result = process_feedback_for_conversation(db, conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "old_outcome": old_outcome,
        "new_outcome": outcome,
        "feedback_triggered": feedback_result is not None,
        "feedback_result": feedback_result,
    }
