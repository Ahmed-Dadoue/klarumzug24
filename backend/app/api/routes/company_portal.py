from fastapi import APIRouter, Depends, HTTPException

from app.api import require_company_auth, success_response
from app.core.database import SessionLocal
from app.core.serialization import serialize_company, serialize_lead
from app.models import CompanyDB, LeadDB, TransactionDB
from app.services.lead_assignment_service import assign_lead_to_company
from app.services.lead_service import _append_lead_event
from app.services.pricing_service import calculate_assigned_price

router = APIRouter()


@router.get("/api/company/me")
def company_me(company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        company = db.query(CompanyDB).filter(CompanyDB.id == company_auth["id"]).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")
        serialized_company = serialize_company(company, include_api_key=False)
        return success_response(
            "Company profile loaded",
            data={"company": serialized_company},
            legacy={"company": serialized_company},
        )
    finally:
        db.close()


@router.get("/api/company/leads")
def list_company_leads(company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        rows = (
            db.query(LeadDB)
            .filter(LeadDB.company_id == company_auth["id"])
            .order_by(LeadDB.id.desc())
            .all()
        )

        result = []
        for row in rows:
            include_pii = row.status == "accepted"
            result.append(serialize_lead(row, include_pii=include_pii))

        return success_response(
            "Company leads loaded",
            data={"leads": result},
            legacy={"leads": result},
        )
    finally:
        db.close()


@router.post("/api/leads/{lead_id}/accept")
def accept_lead(lead_id: int, company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        lead = db.query(LeadDB).filter(LeadDB.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="lead not found")

        if lead.company_id != company_auth["id"]:
            raise HTTPException(status_code=403, detail="lead does not belong to this company")

        if lead.status == "accepted":
            accept_data = {
                "already_accepted": True,
                "lead": serialize_lead(lead, include_pii=True),
            }
            return success_response(
                "Lead already accepted",
                data=accept_data,
                legacy=accept_data,
            )

        company = db.query(CompanyDB).filter(CompanyDB.id == company_auth["id"]).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")

        amount = int(lead.assigned_price_eur or 0)
        if amount <= 0:
            amount = calculate_assigned_price(
                db,
                company_id=company.id,
                from_city=lead.from_city,
                to_city=lead.to_city,
                rooms=lead.rooms,
                distance_km=lead.distance_km,
                express=bool(lead.express),
            )
            lead.assigned_price_eur = amount

        if float(company.balance_eur or 0) < amount:
            raise HTTPException(
                status_code=402,
                detail="insufficient company balance, top-up required",
            )

        existing_charge = (
            db.query(TransactionDB)
            .filter(
                TransactionDB.lead_id == lead.id,
                TransactionDB.company_id == company.id,
                TransactionDB.status == "charged",
            )
            .first()
        )
        if not existing_charge:
            txn = TransactionDB(
                lead_id=lead.id,
                company_id=company.id,
                amount_eur=amount,
                status="charged",
            )
            db.add(txn)
            company.balance_eur = float(company.balance_eur or 0) - amount

        lead.status = "accepted"
        _append_lead_event(
            db,
            lead_id=lead.id,
            event_type="lead_accepted",
            actor="company",
            payload={"company_id": company.id, "amount_eur": amount},
        )
        db.commit()
        db.refresh(lead)

        accept_data = {
            "already_accepted": False,
            "lead": serialize_lead(lead, include_pii=True),
            "company_balance_eur": float(company.balance_eur or 0),
        }
        return success_response(
            "Lead accepted",
            data=accept_data,
            legacy=accept_data,
        )
    finally:
        db.close()


@router.post("/api/leads/{lead_id}/reject")
def reject_lead(lead_id: int, company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        lead = db.query(LeadDB).filter(LeadDB.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="lead not found")

        if lead.company_id != company_auth["id"]:
            raise HTTPException(status_code=403, detail="lead does not belong to this company")

        previous_company_id = lead.company_id
        lead.status = "rejected"
        _append_lead_event(
            db,
            lead_id=lead.id,
            event_type="lead_rejected",
            actor="company",
            payload={"company_id": company_auth["id"]},
        )
        reassigned = assign_lead_to_company(
            db,
            lead,
            _append_lead_event,
            excluded_company_ids={company_auth["id"]},
        )

        db.commit()
        db.refresh(lead)

        reject_data = {
            "previous_company_id": previous_company_id,
            "reassigned": reassigned,
            "lead": serialize_lead(lead, include_pii=False),
        }
        return success_response(
            "Lead rejected",
            data=reject_data,
            legacy=reject_data,
        )
    finally:
        db.close()
