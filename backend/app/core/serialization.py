from app.models import CompanyDB, LeadDB, PricingRuleDB, TransactionDB
from app.utils import mask_email, mask_phone


def serialize_company(row: CompanyDB, include_api_key: bool = False) -> dict:
    payload = {
        "id": row.id,
        "name": row.name,
        "region": row.region,
        "services": row.services,
        "daily_budget_eur": row.daily_budget_eur,
        "max_leads_per_day": row.max_leads_per_day,
        "is_active": bool(row.is_active),
        "balance_eur": float(row.balance_eur or 0),
        "last_assigned_at": row.last_assigned_at.isoformat()
        if row.last_assigned_at
        else None,
        "created_at": row.created_at.isoformat(),
    }
    if include_api_key:
        payload["api_key"] = row.api_key
    return payload


def serialize_rule(row: PricingRuleDB) -> dict:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "base_price_eur": row.base_price_eur,
        "price_per_room_eur": row.price_per_room_eur,
        "price_per_km_eur": row.price_per_km_eur,
        "min_price_eur": row.min_price_eur,
        "max_price_eur": row.max_price_eur,
        "express_multiplier": row.express_multiplier,
        "active": bool(row.active),
        "created_at": row.created_at.isoformat(),
    }


def serialize_lead(row: LeadDB, include_pii: bool = True) -> dict:
    data = {
        "id": row.id,
        "from_city": row.from_city,
        "to_city": row.to_city,
        "rooms": row.rooms,
        "distance_km": row.distance_km,
        "express": bool(row.express),
        "company_id": row.company_id,
        "status": row.status,
        "assigned_price_eur": row.assigned_price_eur,
        "created_at": row.created_at.isoformat(),
    }

    if include_pii:
        data["name"] = row.name
        data["phone"] = row.phone
        data["email"] = row.email
        data["message"] = row.message
        data["photo_name"] = row.photo_name
        data["accepted_agb"] = bool(row.accepted_agb)
        data["accepted_privacy"] = bool(row.accepted_privacy)
    else:
        data["name"] = None
        data["phone"] = mask_phone(row.phone)
        data["email"] = mask_email(row.email)
        data["message"] = None
        data["photo_name"] = None
        data["accepted_agb"] = None
        data["accepted_privacy"] = None

    return data


def serialize_transaction(row: TransactionDB) -> dict:
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "company_id": row.company_id,
        "amount_eur": row.amount_eur,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }
