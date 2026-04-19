from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

from app.models import PricingRuleDB

if TYPE_CHECKING:
    from app.schemas.pricing import PredictIn

# Legacy move-pricing entry points remain for existing calculator/API compatibility.
# New Dode/company pricing should use app.ai.company_pricing instead.
HOURLY_RATE_PER_WORKER_EUR = 45.0
MIN_ORDER_PRICE_EUR = 150.0
LOCAL_DISTANCE_RATE_EUR = 0.60
LONG_DISTANCE_RATE_EUR = 1.20
LONG_DISTANCE_THRESHOLD_KM = 50.0
DISPOSAL_PRICE_PER_M3_EUR = 50.0


@dataclass
class CustomerMovePricingInput:
    qm: int | None = None
    rooms: int | None = None
    haustyp: str | None = None
    stockwerk: int | None = None
    floor_from: int | None = None
    floor_to: int | None = None
    fahrstuhl: bool | None = None
    elevator_from: bool | None = None
    elevator_to: bool | None = None
    walking_distance_m: int | None = None
    distance_km: float | None = None
    kartons: int | None = None
    schraenke: int | None = None
    betten: int | None = None
    sofas: int | None = None
    tische: int | None = None
    stuehle: int | None = None
    waschmaschine: int | None = None
    kuehlschrank: int | None = None
    fernseher: int | None = None
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


@dataclass
class CustomerMoveEstimate:
    price_min_eur: int
    price_max_eur: int
    recommended_workers: int
    estimated_hours_min: float
    estimated_hours_max: float
    distance_km: float
    km_rate_eur: float
    explanation: str


def _safe_int(value: int | float | None) -> int:
    if value is None:
        return 0
    return max(0, int(value))


def _safe_float(value: int | float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, float(value))


def _round_up_to_10(value: float) -> int:
    return int(ceil(max(MIN_ORDER_PRICE_EUR, value) / 10.0) * 10)


def _distance_rate(distance_km: float) -> float:
    if distance_km >= LONG_DISTANCE_THRESHOLD_KM:
        return LONG_DISTANCE_RATE_EUR
    return LOCAL_DISTANCE_RATE_EUR


def _has_elevator(value: bool | None, fallback: bool | None = None) -> bool:
    if value is not None:
        return bool(value)
    return bool(fallback)


def _recommended_workers(data: CustomerMovePricingInput) -> int:
    rooms = _safe_int(data.rooms)
    qm = _safe_int(data.qm)
    heavy_items = (
        _safe_int(data.schraenke)
        + _safe_int(data.sofas)
        + _safe_int(data.betten)
        + _safe_int(data.waschmaschine)
        + _safe_int(data.kuehlschrank)
        + int(bool(data.klavier))
        + int(bool(data.tresor))
    )
    if rooms >= 5 or qm >= 120 or heavy_items >= 8 or data.kueche_ab or data.kueche_auf:
        return 3
    if rooms >= 2 or qm >= 45 or heavy_items >= 3 or _safe_int(data.kartons) >= 20:
        return 2
    return 1


def _move_hours_estimate(data: CustomerMovePricingInput) -> float:
    rooms = _safe_int(data.rooms)
    qm = _safe_int(data.qm)
    kartons = _safe_int(data.kartons)
    schraenke = _safe_int(data.schraenke)
    betten = _safe_int(data.betten)
    sofas = _safe_int(data.sofas)
    tische = _safe_int(data.tische)
    stuehle = _safe_int(data.stuehle)
    waschmaschine = _safe_int(data.waschmaschine)
    kuehlschrank = _safe_int(data.kuehlschrank)
    fernseher = _safe_int(data.fernseher)
    distance_km = _safe_float(data.distance_km)

    hours = 0.75
    if rooms:
        hours += rooms * 0.90
    if qm:
        hours += qm * 0.015
    if not rooms and not qm:
        hours += 1.00

    if data.haustyp == "haus":
        hours += 0.60
    elif data.haustyp == "reihenhaus":
        hours += 0.35

    floor_from = _safe_int(data.floor_from if data.floor_from is not None else data.stockwerk)
    floor_to = _safe_int(data.floor_to)
    if floor_from:
        hours += floor_from * (0.15 if _has_elevator(data.elevator_from, data.fahrstuhl) else 0.35)
    if floor_to:
        hours += floor_to * (0.15 if _has_elevator(data.elevator_to, data.fahrstuhl) else 0.35)

    hours += _safe_int(data.keller) * 0.40
    hours += _safe_int(data.dachboden) * 0.40
    hours += _safe_int(data.balkon) * 0.20
    hours += _safe_int(data.garage) * 0.20
    hours += _safe_float(data.walking_distance_m) / 100.0 * 0.05

    if not bool(data.parken):
        hours += 0.35
    if data.halteverbot:
        hours += 0.20

    hours += kartons * 0.03
    hours += schraenke * 0.18
    hours += betten * 0.18
    hours += sofas * 0.22
    hours += tische * 0.10
    hours += stuehle * 0.03
    hours += waschmaschine * 0.25
    hours += kuehlschrank * 0.25
    hours += fernseher * 0.08

    if data.aquarium:
        hours += 0.35
    if data.klavier:
        hours += 1.50
    if data.tresor:
        hours += 1.25

    if data.montage:
        hours += 1.00
    if data.kueche_ab:
        hours += 1.50
    if data.kueche_auf:
        hours += 2.00
    if data.einpack:
        hours += max(0.60, kartons * 0.04)
    if data.auspack:
        hours += max(0.40, kartons * 0.03)
    if data.entsorgung:
        hours += 0.75

    # Fahrer- und Teamzeit waehrend der Strecke bleibt Teil der Arbeitszeit.
    hours += distance_km / 55.0
    return max(1.0, hours)


def estimate_customer_move_price(data: CustomerMovePricingInput) -> CustomerMoveEstimate:
    distance_km = _safe_float(data.distance_km)
    km_rate = _distance_rate(distance_km)
    workers = _recommended_workers(data)
    base_hours = _move_hours_estimate(data)

    hours_min = max(1.0, round(base_hours * 0.90, 2))
    hours_max = max(hours_min, round(base_hours * 1.15, 2))

    labor_rate = workers * HOURLY_RATE_PER_WORKER_EUR
    distance_cost = distance_km * km_rate

    price_min = _round_up_to_10(labor_rate * hours_min + distance_cost)
    price_max = _round_up_to_10(labor_rate * hours_max + distance_cost)

    explanation = (
        f"Berechnet mit {workers} Arbeiter(n), ca. {hours_min:.1f} bis {hours_max:.1f} Stunden "
        f"und {distance_km:.0f} km zu {km_rate:.2f} EUR/km. "
        f"Grundlage sind Ihre Stundenpreise von 45 EUR pro Arbeiter, die Kilometerregel "
        f"und der Mindestpreis von {int(MIN_ORDER_PRICE_EUR)} EUR."
    )
    if data.express:
        explanation += " Ein moeglicher Express-Zuschlag wird aktuell separat geprueft."
    if data.entsorgung:
        explanation += (
            " Entsorgung ist markiert; volumenabhaengige Entsorgungsgebuehren "
            f"von {DISPOSAL_PRICE_PER_M3_EUR:.0f} EUR pro m3 muessen separat bestaetigt werden."
        )

    return CustomerMoveEstimate(
        price_min_eur=price_min,
        price_max_eur=price_max,
        recommended_workers=workers,
        estimated_hours_min=hours_min,
        estimated_hours_max=hours_max,
        distance_km=distance_km,
        km_rate_eur=km_rate,
        explanation=explanation,
    )


def calculate_estimated_price(payload: "PredictIn") -> float:
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
