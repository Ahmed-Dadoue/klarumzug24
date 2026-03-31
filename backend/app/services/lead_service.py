import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.ai.logging_utils import log_chat_event
from app.api import success_response
from app.core.config import DEDUP_HOURS
from app.core.database import SessionLocal
from app.models import ChatSubmissionDB, LeadDB, LeadEventDB
from app.schemas import LeadIn
from app.services.emailer import send_lead_notification
from app.services.lead_assignment_service import assign_lead_to_company
from app.utils import (
    compact_json,
    normalize_phone,
    normalize_text,
    validate_non_negative_float,
    validate_non_negative_int,
)

LOGGER = logging.getLogger("klarumzug24")


def _append_lead_event(
    db,
    *,
    lead_id: int,
    event_type: str,
    actor: str = "system",
    payload: dict[str, Any] | None = None,
) -> None:
    event = LeadEventDB(
        lead_id=int(lead_id),
        event_type=event_type,
        actor=actor,
        payload_json=compact_json(payload),
    )
    db.add(event)


def _is_chat_conversation_submitted(conversation_id: str | None) -> bool:
    conversation_id = normalize_text(conversation_id)
    if not conversation_id:
        return False
    db = SessionLocal()
    try:
        existing = (
            db.query(ChatSubmissionDB)
            .filter(ChatSubmissionDB.conversation_id == conversation_id)
            .first()
        )
        return bool(existing)
    finally:
        db.close()


def _mark_chat_conversation_submitted(conversation_id: str | None, lead_id: int) -> bool:
    conversation_id = normalize_text(conversation_id)
    if not conversation_id or not lead_id:
        return False
    db = SessionLocal()
    try:
        existing = (
            db.query(ChatSubmissionDB)
            .filter(ChatSubmissionDB.conversation_id == conversation_id)
            .first()
        )
        if existing:
            return False
        db.add(
            ChatSubmissionDB(
                conversation_id=conversation_id,
                lead_id=int(lead_id),
            )
        )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    finally:
        db.close()


def _log_chat_submit_event(
    *,
    conversation_id: str | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    conversation_id = normalize_text(conversation_id)
    if not conversation_id:
        return
    db = SessionLocal()
    try:
        submission = (
            db.query(ChatSubmissionDB)
            .filter(ChatSubmissionDB.conversation_id == conversation_id)
            .first()
        )
        if not submission:
            return
        _append_lead_event(
            db,
            lead_id=submission.lead_id,
            event_type=event_type,
            actor="chat",
            payload=payload,
        )
        db.commit()
    finally:
        db.close()


def _log_lead_event_by_id(
    *,
    lead_id: int | None,
    event_type: str,
    actor: str = "system",
    payload: dict[str, Any] | None = None,
) -> None:
    if not lead_id:
        return
    db = SessionLocal()
    try:
        _append_lead_event(
            db,
            lead_id=int(lead_id),
            event_type=event_type,
            actor=actor,
            payload=payload,
        )
        db.commit()
    finally:
        db.close()


def _create_lead(
    payload: LeadIn,
    *,
    serialize_lead,
    photo_attachment: dict[str, Any] | None = None,
    source: str = "lead_form",
):
    db = SessionLocal()
    try:
        name = (payload.name or "").strip()
        phone = normalize_phone(payload.phone or "")
        email = str(payload.email).strip().lower()
        from_city = normalize_text(payload.from_city)
        to_city = normalize_text(payload.to_city)
        rooms = payload.rooms
        distance_km = payload.distance_km
        express = bool(payload.express)
        conversation_id = normalize_text(payload.conversation_id)
        message = normalize_text(payload.message)
        photo_name = normalize_text(payload.photo_name)
        accepted_agb = bool(payload.accepted_agb)
        accepted_privacy = bool(payload.accepted_privacy)

        if not name:
            raise HTTPException(status_code=422, detail="name is required")
        if not accepted_agb or not accepted_privacy:
            raise HTTPException(
                status_code=422,
                detail="Bitte AGB und Datenschutzerklärung akzeptieren.",
            )
        validate_non_negative_int("rooms", rooms)
        validate_non_negative_float("distance_km", distance_km)

        dedup_from = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)
        duplicate = (
            db.query(LeadDB)
            .filter(LeadDB.phone == phone, LeadDB.created_at >= dedup_from)
            .order_by(LeadDB.created_at.desc())
            .first()
        )

        if duplicate:
            duplicate.name = name
            duplicate.email = email
            if from_city:
                duplicate.from_city = from_city
            if to_city:
                duplicate.to_city = to_city
            if rooms is not None:
                duplicate.rooms = rooms
            if distance_km is not None:
                duplicate.distance_km = distance_km
            if express:
                duplicate.express = True
            if message:
                duplicate.message = message
            if photo_name:
                duplicate.photo_name = photo_name
            duplicate.accepted_agb = accepted_agb
            duplicate.accepted_privacy = accepted_privacy

            if duplicate.company_id is None:
                assign_lead_to_company(db, duplicate, _append_lead_event)

            _append_lead_event(
                db,
                lead_id=duplicate.id,
                event_type="lead_deduped",
                actor="system",
                payload={"source": source, "conversation_id": conversation_id},
            )

            db.commit()
            db.refresh(duplicate)
            try:
                send_lead_notification(
                    serialize_lead(duplicate, include_pii=True),
                    photo_attachment=photo_attachment,
                )
            except Exception:
                LOGGER.exception(
                    "Email notify failed (lead saved anyway): lead_id=%s",
                    duplicate.id,
                )
            lead_result = {
                "deduplicated": True,
                "lead_id": duplicate.id,
                "company_id": duplicate.company_id,
                "status": duplicate.status,
                "assigned_price_eur": duplicate.assigned_price_eur,
            }
            log_chat_event(
                LOGGER,
                "chat_conversion",
                conversation_id=conversation_id,
                lead_id=duplicate.id,
                source=source,
                conversion_step="lead_created",
                success=True,
            )
            return success_response(
                "Lead updated (deduplicated)",
                data=lead_result,
                legacy=lead_result,
            )

        lead = LeadDB(
            name=name,
            phone=phone,
            email=email,
            from_city=from_city,
            to_city=to_city,
            rooms=rooms,
            distance_km=distance_km,
            express=express,
            message=message,
            photo_name=photo_name,
            accepted_agb=accepted_agb,
            accepted_privacy=accepted_privacy,
            status="new",
        )

        db.add(lead)
        db.flush()
        _append_lead_event(
            db,
            lead_id=lead.id,
            event_type="lead_created",
            actor="system",
            payload={"source": source, "conversation_id": conversation_id},
        )
        assign_lead_to_company(db, lead, _append_lead_event)

        db.commit()
        db.refresh(lead)
        try:
            send_lead_notification(
                serialize_lead(lead, include_pii=True),
                photo_attachment=photo_attachment,
            )
        except Exception:
            LOGGER.exception(
                "Email notify failed (lead saved anyway): lead_id=%s",
                lead.id,
            )
        lead_result = {
            "deduplicated": False,
            "lead_id": lead.id,
            "company_id": lead.company_id,
            "status": lead.status,
            "assigned_price_eur": lead.assigned_price_eur,
        }
        log_chat_event(
            LOGGER,
            "chat_conversion",
            conversation_id=conversation_id,
            lead_id=lead.id,
            source=source,
            conversion_step="lead_created",
            success=True,
        )
        return success_response(
            "Lead created",
            data=lead_result,
            legacy=lead_result,
        )
    finally:
        db.close()
