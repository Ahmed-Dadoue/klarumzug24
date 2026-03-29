from collections.abc import Callable
import logging
from typing import Any

from .logging_utils import log_chat_event, log_chat_exception
from .schemas import ChatLanguage, MoveDetails, PriceEstimateResult


def calculate_move_price(
    move_details: MoveDetails,
    *,
    session_factory: Callable[[], Any],
    assigned_price_calculator: Callable[..., int],
    logger: logging.Logger | None = None,
    request_id: str | None = None,
    conversation_id: str | None = None,
    lang: ChatLanguage = "de",
) -> PriceEstimateResult:
    if not move_details.from_city or not move_details.to_city:
        raise ValueError("from_city and to_city are required")
    if move_details.rooms is None:
        raise ValueError("rooms is required")
    if move_details.distance_km is None:
        raise ValueError("distance_km is required")

    db = session_factory()
    try:
        log_chat_event(
            logger,
            "chat_tool_started",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            tool="calculate_move_price",
            success=None,
        )
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
    except Exception as exc:
        log_chat_exception(
            logger,
            "chat_tool_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            tool="calculate_move_price",
            error_type=type(exc).__name__,
            success=False,
        )
        raise
    finally:
        db.close()

    log_chat_event(
        logger,
        "chat_tool_completed",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=lang,
        tool="calculate_move_price",
        price_min=baseline_price,
        price_max=baseline_price,
        success=True,
    )
    return PriceEstimateResult(
        price_min=baseline_price,
        price_max=baseline_price,
        explanation=(
            "Die unverbindliche Schaetzung wurde mit der bestehenden Backend-Preislogik "
            "auf Basis von Strecke, Zimmerzahl und den bisher vorliegenden Umzugsdaten erstellt."
        ),
        confidence="medium",
    )
