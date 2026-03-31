from fastapi import APIRouter, Depends, Query, Request

from app.api import require_admin_api_key, success_response
from app.core.config import MAX_PHOTO_BYTES
from app.core.database import SessionLocal
from app.core.serialization import serialize_lead
from app.models import LeadDB
from app.services.lead_service import _create_lead as lead_service_create_lead
from app.utils import parse_iso_datetime, parse_lead_request

router = APIRouter()


@router.post("/contact")
async def submit_contact(request: Request):
    payload, photo_attachment = await parse_lead_request(
        request,
        max_photo_bytes=MAX_PHOTO_BYTES,
    )
    return lead_service_create_lead(
        payload,
        serialize_lead=serialize_lead,
        photo_attachment=photo_attachment,
        source="contact",
    )


@router.post("/api/leads")
async def create_lead(request: Request):
    payload, photo_attachment = await parse_lead_request(
        request,
        max_photo_bytes=MAX_PHOTO_BYTES,
    )
    return lead_service_create_lead(
        payload,
        serialize_lead=serialize_lead,
        photo_attachment=photo_attachment,
        source="api_leads",
    )


@router.get("/api/leads")
def list_leads(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(LeadDB)
        if status:
            query = query.filter(LeadDB.status == status)
        if company_id is not None:
            query = query.filter(LeadDB.company_id == company_id)

        dt_from = parse_iso_datetime(created_from, "created_from")
        dt_to = parse_iso_datetime(created_to, "created_to")
        if dt_from is not None:
            query = query.filter(LeadDB.created_at >= dt_from)
        if dt_to is not None:
            query = query.filter(LeadDB.created_at <= dt_to)

        rows = query.order_by(LeadDB.id.desc()).all()
        leads = [serialize_lead(r, include_pii=True) for r in rows]
        return success_response(
            "Leads loaded",
            data={"leads": leads},
            legacy={"leads": leads},
        )
    finally:
        db.close()
