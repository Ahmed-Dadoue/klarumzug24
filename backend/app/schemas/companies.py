from pydantic import BaseModel


class CompanyIn(BaseModel):
    name: str
    region: str | None = None
    services: str | None = None
    daily_budget_eur: float | None = None
    max_leads_per_day: int | None = None
    is_active: bool = True
    balance_eur: float = 0


class CompanyTopUpIn(BaseModel):
    amount_eur: float
