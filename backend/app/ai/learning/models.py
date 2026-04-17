"""SQLAlchemy models for the Dode Learning Cycle."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class ConversationDB(Base):
    """Stores complete chat conversations for later analysis."""

    __tablename__ = "learning_conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(80), nullable=False, unique=True, index=True)
    conversation_type = Column(String(30), nullable=False, default="real_user")
    source_label = Column(String(80), nullable=True)
    test_run_id = Column(String(80), nullable=True)
    messages_json = Column(Text, nullable=False)
    service_type = Column(String(40), nullable=True)
    intent_type = Column(String(40), nullable=True)
    source_used = Column(String(60), nullable=True)
    helper_path = Column(String(100), nullable=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    telemetry_json = Column(Text, nullable=True)
    outcome = Column(String(40), nullable=False, default="unknown")
    language = Column(String(5), nullable=False, default="de")
    message_count = Column(Integer, nullable=False, default=0)
    analyzed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Reward Scoring fields
    reward_score = Column(Float, nullable=True)  # -1.0 to +1.0
    conversion_achieved = Column(Boolean, nullable=True)  # Lead created?
    user_satisfied = Column(Boolean, nullable=True)  # No frustration detected?
    response_quality = Column(Float, nullable=True)  # 0.0 to 1.0
    scored_at = Column(DateTime(timezone=True), nullable=True)


class InsightDB(Base):
    """Stores knowledge extracted from conversation analysis."""

    __tablename__ = "learning_insights"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(60), nullable=False, index=True)
    content = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)
    initial_confidence = Column(Float, nullable=True)  # Original confidence for decay calc
    active = Column(Boolean, nullable=False, default=True)
    used_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)  # Times insight led to good outcome
    failure_count = Column(Integer, nullable=False, default=0)  # Times insight led to bad outcome
    source_conversation_ids = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_validated_at = Column(DateTime(timezone=True), nullable=True)  # Last time effectiveness checked
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
