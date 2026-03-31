from datetime import datetime, timezone

from app.models import CompanyDB, LeadDB
from app.services.pricing_service import calculate_assigned_price


def pick_company_for_lead(
    db,
    from_city: str | None,
    to_city: str | None,
    rooms: int | None,
    distance_km: float | None,
    express: bool,
    excluded_company_ids: set[int] | None = None,
) -> tuple[CompanyDB | None, int | None]:
    excluded_company_ids = excluded_company_ids or set()

    query = db.query(CompanyDB).filter(CompanyDB.is_active.is_(True))
    if excluded_company_ids:
        query = query.filter(~CompanyDB.id.in_(excluded_company_ids))

    companies = (
        query.order_by(
            CompanyDB.last_assigned_at.is_(None).desc(),
            CompanyDB.last_assigned_at.asc(),
            CompanyDB.id.asc(),
        ).all()
    )

    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for company in companies:
        max_daily = company.max_leads_per_day or 0
        if max_daily > 0:
            lead_count_today = (
                db.query(LeadDB)
                .filter(LeadDB.company_id == company.id, LeadDB.created_at >= day_start)
                .count()
            )
            if lead_count_today >= max_daily:
                continue

        quoted_price = calculate_assigned_price(
            db,
            company_id=company.id,
            from_city=from_city,
            to_city=to_city,
            rooms=rooms,
            distance_km=distance_km,
            express=express,
        )

        if float(company.balance_eur or 0) < quoted_price:
            continue

        return company, quoted_price

    return None, None


def assign_lead_to_company(
    db,
    lead: LeadDB,
    append_lead_event,
    excluded_company_ids: set[int] | None = None,
) -> bool:
    previous_company_id = lead.company_id
    company, quoted_price = pick_company_for_lead(
        db,
        from_city=lead.from_city,
        to_city=lead.to_city,
        rooms=lead.rooms,
        distance_km=lead.distance_km,
        express=bool(lead.express),
        excluded_company_ids=excluded_company_ids,
    )

    if not company:
        lead.company_id = None
        lead.status = "new"
        lead.assigned_price_eur = None
        if lead.id:
            append_lead_event(
                db,
                lead_id=lead.id,
                event_type="lead_unassigned",
                actor="system",
                payload={"reason": "no_matching_company"},
            )
        return False

    lead.company_id = company.id
    lead.status = "assigned"
    lead.assigned_price_eur = int(quoted_price or 0)
    company.last_assigned_at = datetime.now(timezone.utc)
    if lead.id:
        event_type = (
            "lead_reassigned"
            if previous_company_id and previous_company_id != company.id
            else "lead_assigned"
        )
        append_lead_event(
            db,
            lead_id=lead.id,
            event_type=event_type,
            actor="system",
            payload={"company_id": company.id, "quoted_price_eur": int(quoted_price or 0)},
        )
    return True
