from pydantic import BaseModel, EmailStr


class LeadIn(BaseModel):
    name: str
    phone: str
    email: EmailStr
    conversation_id: str | None = None
    from_city: str | None = None
    to_city: str | None = None
    rooms: int | None = None
    distance_km: float | None = None
    express: bool = False
    message: str | None = None
    photo_name: str | None = None
    accepted_agb: bool = False
    accepted_privacy: bool = False
