from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer

from app.core.database import Base


class PricingRuleDB(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    base_price_eur = Column(Float, nullable=False, default=20)
    price_per_room_eur = Column(Float, nullable=False, default=3)
    price_per_km_eur = Column(Float, nullable=False, default=0.5)
    min_price_eur = Column(Float, nullable=False, default=25)
    max_price_eur = Column(Float, nullable=False, default=120)
    express_multiplier = Column(Float, nullable=False, default=1.25)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
