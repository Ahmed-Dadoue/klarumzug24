from app.models import PricingRuleDB
from app.schemas import PredictIn


def calculate_estimated_price(payload: PredictIn) -> float:
    estimate = (
        payload.qm * 4.2
        + payload.kartons * 1.7
        + payload.stockwerk * 12
        + (0 if payload.fahrstuhl else 65)
        + payload.distanz_meter * 0.45
        + payload.schraenke * 17
        + payload.waschmaschine * 28
        + payload.fernseher * 11
        + (95 if payload.montage else 0)
    )
    return round(max(0.0, float(estimate)), 2)


def get_active_pricing_rule(db, company_id: int | None) -> PricingRuleDB | None:
    if company_id is not None:
        company_rule = (
            db.query(PricingRuleDB)
            .filter(
                PricingRuleDB.active.is_(True),
                PricingRuleDB.company_id == company_id,
            )
            .order_by(PricingRuleDB.id.desc())
            .first()
        )
        if company_rule:
            return company_rule

    return (
        db.query(PricingRuleDB)
        .filter(
            PricingRuleDB.active.is_(True),
            PricingRuleDB.company_id.is_(None),
        )
        .order_by(PricingRuleDB.id.desc())
        .first()
    )


def calculate_assigned_price(
    db,
    company_id: int,
    from_city: str | None,
    to_city: str | None,
    rooms: int | None,
    distance_km: float | None,
    express: bool,
) -> int:
    rule = get_active_pricing_rule(db, company_id)
    safe_rooms = max(0, int(rooms or 0))
    safe_km = max(0.0, float(distance_km or 0.0))

    if rule:
        price = (
            rule.base_price_eur
            + safe_rooms * rule.price_per_room_eur
            + safe_km * rule.price_per_km_eur
        )
        if express:
            price *= rule.express_multiplier

        min_price = rule.min_price_eur
        max_price = rule.max_price_eur
        if max_price < min_price:
            max_price = min_price

        price = max(min_price, min(max_price, price))
        return int(round(price))

    fallback = 35 if from_city and to_city else 25
    fallback += int(round(safe_rooms * 2 + safe_km * 0.3))
    if express:
        fallback = int(round(fallback * 1.2))
    return fallback
