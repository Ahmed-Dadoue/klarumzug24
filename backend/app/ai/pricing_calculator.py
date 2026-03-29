"""
Pricing calculation functions for each service type.
Each function calculates a price range based on service-specific details.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class PriceEstimate:
    """Result of price calculation."""
    service_type: str
    min_price_eur: int
    max_price_eur: int
    currency: str = "EUR"
    note: str = "unverbindliche Schätzung"
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
    """
    Calculate estimated price for moving services.
    Base: 200€ + room factor + floor factor + distance factor
    """
    # Base price
    base_price = 200
    
    # Room factor (roughly 80€ per room)
    room_factor = 0
    if rooms:
        room_factor = rooms * 80
    
    # Floor/access factor
    floor_factor = 0
    total_floors = 0
    
    if floor_from and floor_from > 0:
        total_floors += floor_from
    if floor_to and floor_to > 0:
        total_floors += floor_to
    
    # If no elevator, add 50€ per floor
    if not has_elevator_from and floor_from and floor_from > 0:
        floor_factor += floor_from * 50
    if not has_elevator_to and floor_to and floor_to > 0:
        floor_factor += floor_to * 50
    
    # Distance factor (simplified: assume same region = 0, different = +200)
    distance_factor = 200 if from_city.lower() != to_city.lower() else 0
    
    min_price = base_price + room_factor + floor_factor + distance_factor
    # Add 30% for max (accounting for various complexities)
    max_price = int(min_price * 1.3)
    
    explanation = f"Umzug von {from_city} nach {to_city}"
    if rooms:
        explanation += f", {rooms} Zimmer"
    
    return PriceEstimate(
        service_type="umzug",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation
    )


def calculate_entsorgung_price(
    item_type: str,
    location: str,
    quantity: Optional[int] = None,
    size_description: Optional[str] = None,
) -> PriceEstimate:
    """
    Calculate estimated price for disposal/junk removal.
    Base prices vary by item type.
    """
    item_lower = item_type.lower()
    
    # Item-specific base prices
    base_prices = {
        "sofa": (70, 100),
        "sofas": (130, 180),  # Adjusted for tighter ratio
        "schrank": (50, 85),
        "kühlschrank": (80, 120),
        "waschmaschine": (80, 120),
        "bett": (50, 85),
        "tisch": (40, 65),
        "stuhl": (20, 35),
        "stickmaschine": (150, 220),
        "klavier": (200, 320),
        "safe": (150, 240),
    }
    
    # Find matching item
    min_price = 100
    max_price = 160
    
    for item_key, (min_p, max_p) in base_prices.items():
        if item_key in item_lower:
            min_price, max_price = min_p, max_p
            break
    
    # Adjust for quantity if specified
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
        explanation=explanation
    )


def calculate_laminat_price(
    area_m2: float,
    location: str,
    abbau_only: bool = False,
    entsorgung_included: bool = True,
) -> PriceEstimate:
    """
    Calculate estimated price for laminate/flooring removal and disposal.
    Price per m² varies by region and complexity.
    """
    # Price per m² (8-13€ depending on region and disposal)
    price_per_m2_min = 8
    price_per_m2_max = 13
    
    # If disposal included (standard), use higher range
    if entsorgung_included:
        price_per_m2_min = 10
        price_per_m2_max = 13
    else:
        price_per_m2_min = 8
        price_per_m2_max = 10
    
    min_price = int(area_m2 * price_per_m2_min)
    max_price = int(area_m2 * price_per_m2_max)
    
    service_desc = "Abbau und Entsorgung" if entsorgung_included else "Abbau (ohne Entsorgung)"
    explanation = f"{service_desc} von {area_m2}m² Laminat in {location}"
    
    return PriceEstimate(
        service_type="laminat",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation
    )


def calculate_moebelmontage_price(
    furniture_type: str,
    location: str,
    quantity: Optional[int] = None,
    aufbau_or_abbau: Optional[str] = None,
) -> PriceEstimate:
    """
    Calculate estimated price for furniture assembly/disassembly.
    """
    furniture_lower = furniture_type.lower()
    quantity = quantity or 1
    
    # Base prices per item
    base_prices = {
        "regal": (100, 150),
        "schrank": (120, 180),
        "küche": (200, 400),
        "bett": (80, 120),
        "tisch": (60, 100),
        "ikea": (100, 200),
    }
    
    min_price = 100
    max_price = 150
    
    for item_key, (min_p, max_p) in base_prices.items():
        if item_key in furniture_lower:
            min_price, max_price = min_p, max_p
            break
    
    # Adjust for quantity
    if quantity > 1:
        # Bulk discount: 80% for each additional item
        for i in range(1, quantity):
            min_price += int((max_price - min_price) * 0.5 * 0.8)
            max_price += int((max_price - min_price) * 0.8)
    
    action = aufbau_or_abbau or "Montage"
    explanation = f"{action} von {furniture_type}"
    if quantity > 1:
        explanation += f" ({quantity}x)"
    
    return PriceEstimate(
        service_type="moebelmontage",
        min_price_eur=min_price,
        max_price_eur=max_price,
        explanation=explanation
    )


def calculate_einzeltransport_price(
    item_description: str,
    location: str,
    destination: Optional[str] = None,
    weight_estimate: Optional[int] = None,
) -> PriceEstimate:
    """
    Calculate estimated price for single item transport.
    """
    item_lower = item_description.lower()
    
    # Base prices for common items
    base_prices = {
        "waschmaschine": (80, 150),
        "kühlschrank": (80, 150),
        "sofa": (100, 180),
        "bett": (80, 120),
        "klavier": (200, 400),
        "safe": (150, 300),
    }
    
    min_price = 50
    max_price = 120
    
    # Heavy items (e.g., by weight)
    if weight_estimate:
        if weight_estimate > 500:
            min_price = 150
            max_price = 250
        elif weight_estimate > 200:
            min_price = 100
            max_price = 180
    
    # Known items override
    for item_key, (min_p, max_p) in base_prices.items():
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
        explanation=explanation
    )


def calculate_price(
    service_type: str,
    details: dict,
) -> PriceEstimate | None:
    """
    Main entry point for price calculation.
    Routes to appropriate calculator based on service type.
    """
    if service_type == "umzug":
        return calculate_umzug_price(**details)
    elif service_type == "entsorgung":
        return calculate_entsorgung_price(**details)
    elif service_type == "laminat":
        return calculate_laminat_price(**details)
    elif service_type == "moebelmontage":
        return calculate_moebelmontage_price(**details)
    elif service_type == "einzeltransport":
        return calculate_einzeltransport_price(**details)
    else:
        return None
