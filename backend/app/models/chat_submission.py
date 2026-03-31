from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class ChatSubmissionDB(Base):
    __tablename__ = "chat_submissions"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(80), nullable=False, unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
