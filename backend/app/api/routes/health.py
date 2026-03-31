from fastapi import APIRouter

from app.api import success_response

router = APIRouter()


@router.get("/health")
def health():
    return success_response(
        "Service is healthy",
        data={"status": "ok"},
        legacy={"status": "ok"},
    )
