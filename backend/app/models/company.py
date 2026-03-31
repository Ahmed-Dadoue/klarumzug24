from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.core.database import Base


class CompanyDB(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    region = Column(String(120), nullable=True)
    services = Column(String(300), nullable=True)
    daily_budget_eur = Column(Float, nullable=True)
    max_leads_per_day = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_assigned_at = Column(DateTime(timezone=True), nullable=True)
    balance_eur = Column(Float, nullable=False, default=0)
    api_key = Column(String(120), nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
