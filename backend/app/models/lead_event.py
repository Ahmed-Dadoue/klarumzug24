from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


class LeadEventDB(Base):
    __tablename__ = "lead_events"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor = Column(String(32), nullable=False, default="system")
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
