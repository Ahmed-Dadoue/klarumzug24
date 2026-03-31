from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class LeadDB(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False)
    email = Column(String(200), nullable=False)
    from_city = Column(String(120), nullable=True)
    to_city = Column(String(120), nullable=True)
    rooms = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    express = Column(Boolean, nullable=False, default=False)
    message = Column(String(5000), nullable=True)
    photo_name = Column(String(255), nullable=True)
    accepted_agb = Column(Boolean, nullable=False, default=False)
    accepted_privacy = Column(Boolean, nullable=False, default=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="new")
    assigned_price_eur = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
