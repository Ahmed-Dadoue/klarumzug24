from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import require_admin_api_key, success_response
from app.core.database import SessionLocal
from app.core.security import generate_api_key
from app.core.serialization import serialize_company, serialize_rule
from app.models import CompanyDB, PricingRuleDB
from app.schemas import CompanyIn, CompanyTopUpIn, PricingRuleIn
from app.utils import normalize_text, validate_non_negative_float, validate_non_negative_int

router = APIRouter()


@router.post("/api/companies")
def create_company(
    payload: CompanyIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="company name is required")

        validate_non_negative_float("daily_budget_eur", payload.daily_budget_eur)
        validate_non_negative_int("max_leads_per_day", payload.max_leads_per_day)
        validate_non_negative_float("balance_eur", payload.balance_eur)

        company = CompanyDB(
            name=name,
            region=normalize_text(payload.region),
            services=normalize_text(payload.services),
            daily_budget_eur=payload.daily_budget_eur,
            max_leads_per_day=payload.max_leads_per_day,
            is_active=bool(payload.is_active),
            balance_eur=float(payload.balance_eur),
            api_key=generate_api_key(),
        )

        db.add(company)
        db.commit()
        db.refresh(company)

        serialized_company = serialize_company(company, include_api_key=True)
        return success_response(
            "Company created",
            data={"company": serialized_company},
            legacy={"company": serialized_company},
        )
    finally:
        db.close()


@router.get("/api/companies")
def list_companies(_admin: None = Depends(require_admin_api_key)):
    db = SessionLocal()
    try:
        rows = db.query(CompanyDB).order_by(CompanyDB.id.desc()).all()
        companies = [serialize_company(r, include_api_key=True) for r in rows]
        return success_response(
            "Companies loaded",
            data={"companies": companies},
            legacy={"companies": companies},
        )
    finally:
        db.close()


@router.post("/api/companies/{company_id}/topup")
def topup_company_balance(
    company_id: int,
    payload: CompanyTopUpIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        validate_non_negative_float("amount_eur", payload.amount_eur)
        if payload.amount_eur <= 0:
            raise HTTPException(status_code=422, detail="amount_eur must be > 0")

        company = db.query(CompanyDB).filter(CompanyDB.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")

        company.balance_eur = float(company.balance_eur or 0) + float(payload.amount_eur)
        db.commit()
        db.refresh(company)

        topup_data = {
            "company_id": company.id,
            "balance_eur": float(company.balance_eur),
        }
        return success_response(
            "Company balance updated",
            data=topup_data,
            legacy=topup_data,
        )
    finally:
        db.close()


@router.post("/api/pricing-rules")
def create_pricing_rule(
    payload: PricingRuleIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        if payload.company_id is not None:
            company = db.query(CompanyDB).filter(CompanyDB.id == payload.company_id).first()
            if not company:
                raise HTTPException(status_code=404, detail="company not found")

        validate_non_negative_float("base_price_eur", payload.base_price_eur)
        validate_non_negative_float("price_per_room_eur", payload.price_per_room_eur)
        validate_non_negative_float("price_per_km_eur", payload.price_per_km_eur)
        validate_non_negative_float("min_price_eur", payload.min_price_eur)
        validate_non_negative_float("max_price_eur", payload.max_price_eur)

        if payload.express_multiplier <= 0:
            raise HTTPException(status_code=422, detail="express_multiplier must be > 0")
        if payload.max_price_eur < payload.min_price_eur:
            raise HTTPException(status_code=422, detail="max_price_eur must be >= min_price_eur")

        rule = PricingRuleDB(
            company_id=payload.company_id,
            base_price_eur=payload.base_price_eur,
            price_per_room_eur=payload.price_per_room_eur,
            price_per_km_eur=payload.price_per_km_eur,
            min_price_eur=payload.min_price_eur,
            max_price_eur=payload.max_price_eur,
            express_multiplier=payload.express_multiplier,
            active=bool(payload.active),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

        pricing_rule = serialize_rule(rule)
        return success_response(
            "Pricing rule created",
            data={"pricing_rule": pricing_rule},
            legacy={"pricing_rule": pricing_rule},
        )
    finally:
        db.close()


@router.get("/api/pricing-rules")
def list_pricing_rules(
    company_id: int | None = Query(default=None),
    active: bool | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(PricingRuleDB)
        if company_id is not None:
            query = query.filter(PricingRuleDB.company_id == company_id)
        if active is not None:
            query = query.filter(PricingRuleDB.active.is_(active))

        rows = query.order_by(PricingRuleDB.id.desc()).all()
        pricing_rules = [serialize_rule(r) for r in rows]
        return success_response(
            "Pricing rules loaded",
            data={"pricing_rules": pricing_rules},
            legacy={"pricing_rules": pricing_rules},
        )
    finally:
        db.close()
