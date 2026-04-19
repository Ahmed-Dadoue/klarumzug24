from fastapi import APIRouter

from app.api import success_response
from app.ai.company_pricing import PricingV2Input, estimate_company_price_v2
from app.schemas import CompanyPricingV2EstimateIn, CustomerMoveEstimateIn, PredictIn
from app.services.pricing_service import (
    CustomerMovePricingInput,
    calculate_estimated_price,
    estimate_customer_move_price,
)

router = APIRouter()


@router.post("/predict")
@router.post("/api/predict")
def predict_price(payload: PredictIn):
    estimated_price = calculate_estimated_price(payload)
    result = {"estimated_price_eur": estimated_price}
    return success_response(
        "Price estimate calculated",
        data=result,
        legacy=result,
    )


@router.post("/api/move-estimate")
def estimate_move(payload: CustomerMoveEstimateIn):
    estimate = estimate_customer_move_price(
        CustomerMovePricingInput(
            qm=payload.qm,
            rooms=payload.rooms,
            haustyp=payload.haustyp,
            stockwerk=payload.stockwerk,
            fahrstuhl=payload.fahrstuhl,
            walking_distance_m=payload.walking_distance_m,
            distance_km=payload.distance_km,
            kartons=payload.kartons,
            schraenke=payload.schraenke,
            betten=payload.betten,
            sofas=payload.sofas,
            tische=payload.tische,
            stuehle=payload.stuehle,
            waschmaschine=payload.waschmaschine,
            kuehlschrank=payload.kuehlschrank,
            fernseher=payload.fernseher,
            aquarium=payload.aquarium,
            klavier=payload.klavier,
            tresor=payload.tresor,
            keller=payload.keller,
            dachboden=payload.dachboden,
            balkon=payload.balkon,
            garage=payload.garage,
            halteverbot=payload.halteverbot,
            parken=payload.parken,
            montage=payload.montage,
            kueche_ab=payload.kueche_ab,
            kueche_auf=payload.kueche_auf,
            einpack=payload.einpack,
            auspack=payload.auspack,
            entsorgung=payload.entsorgung,
            express=payload.express,
        )
    )
    result = {
        "price_min_eur": estimate.price_min_eur,
        "price_max_eur": estimate.price_max_eur,
        "recommended_workers": estimate.recommended_workers,
        "estimated_hours_min": estimate.estimated_hours_min,
        "estimated_hours_max": estimate.estimated_hours_max,
        "distance_km": estimate.distance_km,
        "km_rate_eur": estimate.km_rate_eur,
        "explanation": estimate.explanation,
    }
    return success_response(
        "Customer move estimate calculated",
        data=result,
        legacy=result,
    )


@router.post("/api/pricing/v2/estimate")
def estimate_company_pricing_v2(payload: CompanyPricingV2EstimateIn):
    estimate = estimate_company_price_v2(
        PricingV2Input(
            service_type=payload.service_type,
            distance_km=payload.distance_km,
            estimated_hours_min=payload.estimated_hours_min,
            estimated_hours_max=payload.estimated_hours_max,
            workers_total=payload.workers_total,
            needs_transporter=payload.needs_transporter,
            kitchen_meters=payload.kitchen_meters,
            sink_cutout=payload.sink_cutout,
            cooktop_cutout=payload.cooktop_cutout,
            difficulty=payload.difficulty,
            rooms=payload.rooms,
            cartons=payload.cartons,
            heavy_items=payload.heavy_items,
            floor_from=payload.floor_from,
            floor_to=payload.floor_to,
            elevator_from=payload.elevator_from,
            elevator_to=payload.elevator_to,
            description=payload.description,
        )
    )
    result = {
        "service_type": estimate.service_type,
        "pricing_model": estimate.pricing_model,
        "price_min_eur": estimate.price_min_eur,
        "price_max_eur": estimate.price_max_eur,
        "workers_total": estimate.workers_total,
        "helpers_count": estimate.helpers_count,
        "needs_transporter": estimate.needs_transporter,
        "estimated_hours_min": estimate.estimated_hours_min,
        "estimated_hours_max": estimate.estimated_hours_max,
        "distance_km": estimate.distance_km,
        "missing_fields": list(estimate.missing_fields),
        "explanation": estimate.explanation_de,
        "internal_notes": list(estimate.internal_notes),
    }
    return success_response(
        "Company pricing v2 estimate calculated",
        data=result,
        legacy=result,
    )
