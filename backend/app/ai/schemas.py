from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class MoveDetails(BaseModel):
    from_city: str | None = Field(default=None, max_length=120)
    to_city: str | None = Field(default=None, max_length=120)
    rooms: int | None = Field(default=None, ge=0, le=50)
    area_m2: int | None = Field(default=None, ge=0, le=10000)
    distance_km: float | None = Field(default=None, ge=0, le=200000)
    floor_from: int | None = Field(default=None, ge=0, le=200)
    floor_to: int | None = Field(default=None, ge=0, le=200)
    elevator_from: bool | None = None
    elevator_to: bool | None = None
    move_date: str | None = Field(default=None, max_length=40)


class PriceEstimateResult(BaseModel):
    price_min: int = Field(ge=0)
    price_max: int = Field(ge=0)
    explanation: str = Field(min_length=1, max_length=500)
    confidence: Literal["low", "medium", "high"] = "low"
