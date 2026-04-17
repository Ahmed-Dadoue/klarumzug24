"""Reward Scoring System for Dode Learning Cycle.

Calculates reward scores for conversations based on outcomes,
user satisfaction signals, and conversion success.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import ConversationDB

logger = logging.getLogger("klarumzug24")

# Reward weights
WEIGHTS = {
    "conversion": 0.5,      # Lead created = highest reward
    "satisfaction": 0.3,    # No frustration signals
    "engagement": 0.2,      # User continued conversation
}

# Frustration signals (negative sentiment)
FRUSTRATION_PATTERNS_DE = [
    r"\b(nein|falsch|versteh.?\s*nicht|macht\s*keinen\s*sinn)\b",
    r"\b(warum\s*fragst|das\s*passt\s*nicht|hilft\s*mir\s*nicht)\b",
    r"\b(schlecht|unbrauchbar|nervt|aergerlich|frustriert)\b",
    r"\b(egal|vergiss\s*es|lassen\s*wir)\b",
]

FRUSTRATION_PATTERNS_EN = [
    r"\b(no|wrong|don'?t\s*understand|doesn'?t\s*make\s*sense)\b",
    r"\b(why\s*asking|doesn'?t\s*fit|not\s*helpful)\b",
    r"\b(bad|useless|annoying|frustrated)\b",
    r"\b(whatever|forget\s*it|never\s*mind)\b",
]

# Positive engagement signals
POSITIVE_PATTERNS_DE = [
    r"\b(danke|super|perfekt|gut|toll|klasse|prima)\b",
    r"\b(ja\s*bitte|genau|richtig|stimmt)\b",
    r"\b(interesse|angebot|termin|buchen)\b",
]

POSITIVE_PATTERNS_EN = [
    r"\b(thanks|great|perfect|good|nice|excellent)\b",
    r"\b(yes\s*please|exactly|right|correct)\b",
    r"\b(interested|quote|appointment|book)\b",
]

# Compile patterns
_FRUSTRATION_RE_DE = [re.compile(p, re.IGNORECASE) for p in FRUSTRATION_PATTERNS_DE]
_FRUSTRATION_RE_EN = [re.compile(p, re.IGNORECASE) for p in FRUSTRATION_PATTERNS_EN]
_POSITIVE_RE_DE = [re.compile(p, re.IGNORECASE) for p in POSITIVE_PATTERNS_DE]
_POSITIVE_RE_EN = [re.compile(p, re.IGNORECASE) for p in POSITIVE_PATTERNS_EN]


def calculate_reward_score(
    messages: list[dict[str, str]],
    outcome: str,
    language: str = "de",
) -> dict[str, Any]:
    """Calculate a reward score for a conversation.
    
    Returns:
        {
            "reward_score": float (-1.0 to +1.0),
            "conversion_achieved": bool,
            "user_satisfied": bool,
            "response_quality": float (0.0 to 1.0),
            "details": {...}
        }
    """
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    all_user_text = " ".join(user_messages).lower()
    
    # 1. Conversion score
    conversion_achieved = outcome in ("lead_created", "booking_confirmed", "contact_requested")
    conversion_score = 1.0 if conversion_achieved else 0.0
    
    # 2. Satisfaction score (inverse of frustration)
    frustration_patterns = _FRUSTRATION_RE_DE if language == "de" else _FRUSTRATION_RE_EN
    positive_patterns = _POSITIVE_RE_DE if language == "de" else _POSITIVE_RE_EN
    
    frustration_count = sum(1 for p in frustration_patterns if p.search(all_user_text))
    positive_count = sum(1 for p in positive_patterns if p.search(all_user_text))
    
    # Net sentiment: positive - negative, normalized
    sentiment_raw = positive_count - frustration_count
    sentiment_score = max(-1.0, min(1.0, sentiment_raw / 3))  # Normalize to [-1, 1]
    satisfaction_score = (sentiment_score + 1) / 2  # Convert to [0, 1]
    
    user_satisfied = frustration_count == 0
    
    # 3. Engagement score (based on message count and conversation depth)
    message_count = len(messages)
    if message_count >= 6:
        engagement_score = 1.0
    elif message_count >= 4:
        engagement_score = 0.7
    elif message_count >= 2:
        engagement_score = 0.4
    else:
        engagement_score = 0.1
    
    # Penalize very short conversations without outcome
    if message_count <= 2 and not conversion_achieved:
        engagement_score *= 0.5
    
    # 4. Response quality (based on assistant response patterns)
    assistant_messages = [m["content"] for m in messages if m.get("role") == "assistant"]
    response_quality = _evaluate_response_quality(assistant_messages, language)
    
    # Calculate weighted reward
    raw_reward = (
        WEIGHTS["conversion"] * conversion_score +
        WEIGHTS["satisfaction"] * satisfaction_score +
        WEIGHTS["engagement"] * engagement_score
    )
    
    # Scale to [-1, +1] range
    # 0.5 is neutral (no conversion, moderate engagement)
    reward_score = (raw_reward - 0.5) * 2
    reward_score = max(-1.0, min(1.0, reward_score))
    
    return {
        "reward_score": round(reward_score, 3),
        "conversion_achieved": conversion_achieved,
        "user_satisfied": user_satisfied,
        "response_quality": round(response_quality, 3),
        "details": {
            "conversion_score": conversion_score,
            "satisfaction_score": round(satisfaction_score, 3),
            "engagement_score": round(engagement_score, 3),
            "frustration_count": frustration_count,
            "positive_count": positive_count,
            "message_count": message_count,
        }
    }


def _evaluate_response_quality(assistant_messages: list[str], language: str) -> float:
    """Evaluate quality of assistant responses."""
    if not assistant_messages:
        return 0.0
    
    quality_score = 0.5  # Start neutral
    
    for msg in assistant_messages:
        msg_lower = msg.lower()
        
        # Positive: Contains price information
        if "€" in msg or "euro" in msg_lower or "eur" in msg_lower:
            quality_score += 0.1
        
        # Positive: Asks focused follow-up question
        if "?" in msg:
            quality_score += 0.05
        
        # Negative: Too short responses
        if len(msg) < 50:
            quality_score -= 0.05
        
        # Negative: Repetitive/stuck responses
        if "ich benoetige" in msg_lower or "ich brauche" in msg_lower:
            quality_score -= 0.02
    
    return max(0.0, min(1.0, quality_score))


def score_conversation(db: Session, conversation_id: str) -> dict[str, Any] | None:
    """Score a specific conversation and update the database."""
    conv = (
        db.query(ConversationDB)
        .filter(ConversationDB.conversation_id == conversation_id)
        .first()
    )
    if not conv:
        return None
    
    try:
        messages = json.loads(conv.messages_json)
    except (json.JSONDecodeError, TypeError):
        return None
    
    result = calculate_reward_score(messages, conv.outcome, conv.language)
    
    # Update database
    conv.reward_score = result["reward_score"]
    conv.conversion_achieved = result["conversion_achieved"]
    conv.user_satisfied = result["user_satisfied"]
    conv.response_quality = result["response_quality"]
    conv.scored_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(conv)
    
    return result


def score_unscored_conversations(db: Session, limit: int = 100) -> dict[str, Any]:
    """Score all conversations that haven't been scored yet."""
    unscored = (
        db.query(ConversationDB)
        .filter(ConversationDB.reward_score == None)  # noqa: E711
        .filter(ConversationDB.message_count >= 2)
        .order_by(ConversationDB.created_at.asc())
        .limit(limit)
        .all()
    )
    
    scored = 0
    total_reward = 0.0
    conversions = 0
    satisfied = 0
    
    for conv in unscored:
        result = score_conversation(db, conv.conversation_id)
        if result:
            scored += 1
            total_reward += result["reward_score"]
            if result["conversion_achieved"]:
                conversions += 1
            if result["user_satisfied"]:
                satisfied += 1
    
    return {
        "scored": scored,
        "avg_reward": round(total_reward / scored, 3) if scored > 0 else 0,
        "conversions": conversions,
        "satisfied": satisfied,
        "conversion_rate": round(conversions / scored, 3) if scored > 0 else 0,
        "satisfaction_rate": round(satisfied / scored, 3) if scored > 0 else 0,
    }


def get_reward_stats(db: Session) -> dict[str, Any]:
    """Get aggregate reward statistics."""
    scored = (
        db.query(ConversationDB)
        .filter(ConversationDB.reward_score != None)  # noqa: E711
        .all()
    )
    
    if not scored:
        return {
            "total_scored": 0,
            "avg_reward": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "conversion_rate": 0,
            "satisfaction_rate": 0,
        }
    
    total = len(scored)
    total_reward = sum(c.reward_score or 0 for c in scored)
    conversions = sum(1 for c in scored if c.conversion_achieved)
    satisfied = sum(1 for c in scored if c.user_satisfied)
    positive = sum(1 for c in scored if (c.reward_score or 0) > 0.2)
    negative = sum(1 for c in scored if (c.reward_score or 0) < -0.2)
    neutral = total - positive - negative
    
    return {
        "total_scored": total,
        "avg_reward": round(total_reward / total, 3),
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "conversion_rate": round(conversions / total, 3),
        "satisfaction_rate": round(satisfied / total, 3),
    }
