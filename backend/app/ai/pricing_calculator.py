"""Rule-based local estimators for non-move service prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PriceEstimate:
    """Result of a non-binding local price estimate."""

    service_type: str
    min_price_eur: int
    max_price_eur: int
    currency: str = "EUR"
    note: str = "unverbindliche Schaetzung"
    explanation: str = ""


def calculate_umzug_price(
    from_city: str,
    to_city: str,
    rooms: Optional[int] = None,
    floor_from: Optional[int] = None,
    floor_to: Optional[int] = None,
    has_elevator_from: Optional[bool] = None,
    has_elevator_to: Optional[bool] = None,
) -> PriceEstimate:
    base_price = 200
    room_factor = (rooms or 0) * 80

    floor_factor = 0
    if floor_from and floor_from > 0 and not has_elevator_from:
        floor_factor += floor_from * 50
    if floor_to and floor_to > 0 and not has_elevator_to:
        floor_factor += floor_to * 50

    distance_factor = 0 if from_city.lower() == to_city.lower() else 200
    min_price = base_price + room_factor + floor_factor + distance_factor
    max_price = int(min_price * 1.3)

    explanation = f"Umzug von {from_city} nach {to_city}"
    if rooms:
        explanation += f", {rooms} Zimmer"

    return PriceEstimate(
        service_type="umzug",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation,
    )


def calculate_entsorgung_price(
    item_type: str,
    location: str,
    quantity: Optional[int] = None,
    size_description: Optional[str] = None,
) -> PriceEstimate:
    _ = location
    _ = size_description
    item_lower = item_type.lower()
    base_prices = {
        "sofa": (70, 100),
        "sofas": (130, 180),
        "schrank": (50, 85),
        "kuehlschrank": (80, 120),
        "kühlschrank": (80, 120),
        "waschmaschine": (80, 120),
        "bett": (50, 85),
        "tisch": (40, 65),
        "stuhl": (20, 35),
        "stickmaschine": (150, 220),
        "klavier": (200, 320),
        "safe": (150, 240),
    }

    min_price = 100
    max_price = 160
    for item_key, (min_p, max_p) in sorted(base_prices.items(), key=lambda item: len(item[0]), reverse=True):
        if item_key in item_lower:
            min_price, max_price = min_p, max_p
            break

    if quantity and quantity > 1:
        min_price *= quantity
        max_price *= quantity

    explanation = f"Entsorgung: {item_type}"
    if quantity and quantity > 1:
        explanation += f" (Menge: {quantity})"

    return PriceEstimate(
        service_type="entsorgung",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation,
    )


def calculate_laminat_price(
    area_m2: float,
    location: str,
    abbau_only: bool = False,
    entsorgung_included: bool = True,
) -> PriceEstimate:
    _ = abbau_only
    price_per_m2_min = 10 if entsorgung_included else 8
    price_per_m2_max = 13 if entsorgung_included else 10

    min_price = int(area_m2 * price_per_m2_min)
    max_price = int(area_m2 * price_per_m2_max)
    service_desc = "Abbau und Entsorgung" if entsorgung_included else "Abbau ohne Entsorgung"
    explanation = f"{service_desc} von {area_m2} m2 Laminat in {location}"

    return PriceEstimate(
        service_type="laminat",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation,
    )


def calculate_moebelmontage_price(
    furniture_type: str,
    location: str,
    quantity: Optional[int] = None,
    aufbau_or_abbau: Optional[str] = None,
) -> PriceEstimate:
    _ = location
    furniture_lower = furniture_type.lower()
    quantity = quantity or 1
    base_prices = {
        "regal": (100, 150),
        "schrank": (120, 180),
        "kueche": (200, 400),
        "küche": (200, 400),
        "bett": (80, 120),
        "tisch": (60, 100),
        "ikea": (100, 200),
    }

    min_price = 100
    max_price = 150
    for item_key, (min_p, max_p) in sorted(base_prices.items(), key=lambda item: len(item[0]), reverse=True):
        if item_key in furniture_lower:
            min_price, max_price = min_p, max_p
            break

    if quantity > 1:
        extra_min = int(min_price * 0.7)
        extra_max = int(max_price * 0.8)
        min_price += extra_min * (quantity - 1)
        max_price += extra_max * (quantity - 1)

    action = aufbau_or_abbau or "Montage"
    explanation = f"{action} von {furniture_type}"
    if quantity > 1:
        explanation += f" ({quantity}x)"

    return PriceEstimate(
        service_type="moebelmontage",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation,
    )


def calculate_einzeltransport_price(
    item_description: str,
    location: str,
    destination: Optional[str] = None,
    weight_estimate: Optional[int] = None,
) -> PriceEstimate:
    _ = location
    item_lower = item_description.lower()
    base_prices = {
        "waschmaschine": (80, 150),
        "kuehlschrank": (80, 150),
        "kühlschrank": (80, 150),
        "sofa": (100, 180),
        "bett": (80, 120),
        "klavier": (200, 400),
        "safe": (150, 300),
    }

    min_price = 50
    max_price = 120
    if weight_estimate:
        if weight_estimate > 500:
            min_price = 150
            max_price = 250
        elif weight_estimate > 200:
            min_price = 100
            max_price = 180

    for item_key, (min_p, max_p) in sorted(base_prices.items(), key=lambda item: len(item[0]), reverse=True):
        if item_key in item_lower:
            min_price, max_price = min_p, max_p
            break

    explanation = f"Transport: {item_description}"
    if destination:
        explanation += f" nach {destination}"

    return PriceEstimate(
        service_type="einzeltransport",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation,
    )


def calculate_price(service_type: str, details: dict) -> PriceEstimate | None:
    if service_type == "umzug":
        return calculate_umzug_price(**details)
    if service_type == "entsorgung":
        return calculate_entsorgung_price(**details)
    if service_type == "laminat":
        return calculate_laminat_price(**details)
    if service_type == "moebelmontage":
        return calculate_moebelmontage_price(**details)
    if service_type == "einzeltransport":
        return calculate_einzeltransport_price(**details)
    return None
