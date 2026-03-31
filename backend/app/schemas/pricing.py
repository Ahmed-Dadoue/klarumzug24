from pydantic import BaseModel, Field


class PricingRuleIn(BaseModel):
    company_id: int | None = None
    base_price_eur: float = 20
    price_per_room_eur: float = 3
    price_per_km_eur: float = 0.5
    min_price_eur: float = 25
    max_price_eur: float = 120
    express_multiplier: float = 1.25
    active: bool = True


class PredictIn(BaseModel):
    qm: int = Field(ge=0, le=10000)
    kartons: int = Field(ge=0, le=5000)
    fahrstuhl: int = Field(ge=0, le=1)
    stockwerk: int = Field(ge=0, le=200)
    distanz_meter: int = Field(ge=0, le=200000)
    schraenke: int = Field(ge=0, le=500)
    waschmaschine: int = Field(ge=0, le=100)
    fernseher: int = Field(ge=0, le=100)
    montage: int = Field(ge=0, le=1)
