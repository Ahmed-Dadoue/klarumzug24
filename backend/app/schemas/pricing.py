from typing import Literal

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


class CustomerMoveEstimateIn(BaseModel):
    qm: int | None = Field(default=None, ge=0, le=10000)
    rooms: int | None = Field(default=None, ge=0, le=50)
    haustyp: Literal["wohnung", "haus", "reihenhaus"] = "wohnung"
    stockwerk: int = Field(default=0, ge=0, le=200)
    fahrstuhl: bool = True
    walking_distance_m: int = Field(default=0, ge=0, le=5000)
    distance_km: float = Field(default=0, ge=0, le=200000)
    kartons: int = Field(default=0, ge=0, le=5000)
    schraenke: int = Field(default=0, ge=0, le=500)
    betten: int = Field(default=0, ge=0, le=200)
    sofas: int = Field(default=0, ge=0, le=200)
    tische: int = Field(default=0, ge=0, le=500)
    stuehle: int = Field(default=0, ge=0, le=1000)
    waschmaschine: int = Field(default=0, ge=0, le=100)
    kuehlschrank: int = Field(default=0, ge=0, le=100)
    fernseher: int = Field(default=0, ge=0, le=100)
    aquarium: bool = False
    klavier: bool = False
    tresor: bool = False
    keller: bool = False
    dachboden: bool = False
    balkon: bool = False
    garage: bool = False
    halteverbot: bool = False
    parken: bool = True
    montage: bool = False
    kueche_ab: bool = False
    kueche_auf: bool = False
    einpack: bool = False
    auspack: bool = False
    entsorgung: bool = False
    express: bool = False


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
