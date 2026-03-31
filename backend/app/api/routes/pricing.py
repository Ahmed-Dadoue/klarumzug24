from fastapi import APIRouter

from app.api import success_response
from app.schemas import PredictIn
from app.services.pricing_service import calculate_estimated_price

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
