from collections.abc import Callable
from typing import Any

from .schemas import MoveDetails, PriceEstimateResult


def calculate_move_price(
    move_details: MoveDetails,
    *,
    session_factory: Callable[[], Any],
    assigned_price_calculator: Callable[..., int],
) -> PriceEstimateResult:
    if not move_details.from_city or not move_details.to_city:
        raise ValueError("from_city and to_city are required")
    if move_details.rooms is None:
        raise ValueError("rooms is required")
    if move_details.distance_km is None:
        raise ValueError("distance_km is required")

    db = session_factory()
    try:
        baseline_price = int(
            assigned_price_calculator(
                db,
                company_id=None,
                from_city=move_details.from_city,
                to_city=move_details.to_city,
                rooms=move_details.rooms,
                distance_km=move_details.distance_km,
                express=False,
            )
        )
    finally:
        db.close()

    return PriceEstimateResult(
        price_min=baseline_price,
        price_max=baseline_price,
        explanation=(
            "Die unverbindliche Schaetzung wurde mit der bestehenden Backend-Preislogik "
            "auf Basis von Strecke, Zimmerzahl und den bisher vorliegenden Umzugsdaten erstellt."
        ),
        confidence="medium",
    )
