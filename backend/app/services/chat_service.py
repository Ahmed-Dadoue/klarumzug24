import time
import uuid
from typing import Any

from app.api import success_response
from app.ai.logging_utils import log_chat_event
from app.ai.schemas import ChatLanguage
from app.core.database import SessionLocal
from app.schemas import ChatRequestIn, LeadIn
from app.services import chat_booking_service
from app.services.lead_service import (
    _is_chat_conversation_submitted,
    _log_chat_submit_event,
    _log_lead_event_by_id,
    _mark_chat_conversation_submitted,
)
from app.services.pricing_service import calculate_assigned_price
from app.utils import normalize_text, sanitize_chat_log_text

CONTACT_INTENT_KEYWORDS = {
    "de": ("kontakt", "telefon", "anrufen", "email", "e-mail", "whatsapp"),
    "en": ("contact", "phone", "call", "email", "whatsapp"),
}


def is_contact_intent(text: str | None, lang: ChatLanguage) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    keywords = CONTACT_INTENT_KEYWORDS.get(lang, CONTACT_INTENT_KEYWORDS["de"])
    return any(keyword in normalized for keyword in keywords)


def dode_chat(
    payload: ChatRequestIn,
    *,
    generate_reply,
    create_lead,
    serialize_lead,
    logger,
):
    started_at = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    conversation_id = normalize_text(payload.conversation_id) or f"conv_{uuid.uuid4().hex[:12]}"
    page = normalize_text(payload.page)
    last_user_message = next(
        (
            " ".join(message.content.split())
            for message in reversed(payload.messages)
            if message.role == "user"
        ),
        "",
    )
    sanitized_last_user_message = sanitize_chat_log_text(last_user_message)
    user_message_count = sum(1 for message in payload.messages if message.role == "user")
    log_chat_event(
        logger,
        "chat_request_received",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=payload.lang,
        page=page or "-",
        last_user_message=sanitized_last_user_message,
        success=None,
    )
    if user_message_count == 1:
        log_chat_event(
            logger,
            "chat_conversion",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            conversion_step="chat_started",
            success=True,
        )
    if is_contact_intent(last_user_message, payload.lang):
        log_chat_event(
            logger,
            "chat_conversion",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            conversion_step="contact_intent",
            success=True,
        )
    try:
        reply = generate_reply(
            messages=payload.messages,
            page=page,
            lang=payload.lang,
            session_factory=SessionLocal,
            assigned_price_calculator=calculate_assigned_price,
            logger=logger,
            request_id=request_id,
            conversation_id=conversation_id,
        )
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_chat_event(
            logger,
            "chat_request_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            duration_ms=duration_ms,
            last_user_message=sanitized_last_user_message,
            success=False,
        )
        raise

    lead_data: dict[str, Any] | None = None
    last_user_message_raw = next(
        (message.content for message in reversed(payload.messages) if message.role == "user"),
        "",
    )
    conversation_submitted = _is_chat_conversation_submitted(conversation_id)
    booking_result = chat_booking_service.process(
        conversation_id=conversation_id,
        user_message=last_user_message_raw,
        current_state={
            "messages": payload.messages,
            "lang": payload.lang,
            "conversation_submitted": conversation_submitted,
        },
    )
    booking_action = booking_result.get("action")
    booking_reply_text = booking_result.get("reply_text")

    if booking_action == "ask_consent" and booking_reply_text:
        reply = f"{reply}\n\n{booking_reply_text}".strip()
    elif booking_action == "submit_lead":
        try:
            lead_payload_data = booking_result.get("lead_payload") or {}
            lead_payload = LeadIn(
                name=str(lead_payload_data.get("name", "")).strip(),
                phone=str(lead_payload_data.get("phone", "")).strip(),
                email=str(lead_payload_data.get("email", "")).strip(),
                conversation_id=conversation_id,
                message=str(lead_payload_data.get("message", "")).strip() or None,
                accepted_agb=bool(lead_payload_data.get("accepted_agb", True)),
                accepted_privacy=bool(lead_payload_data.get("accepted_privacy", True)),
            )
            created = create_lead(
                lead_payload,
                serialize_lead=serialize_lead,
                source="chat_booking",
            )
            lead_data = created.get("data") if isinstance(created, dict) else None
            lead_id = int((lead_data or {}).get("lead_id") or 0)
            if lead_id:
                marked = _mark_chat_conversation_submitted(conversation_id, lead_id)
                if marked:
                    _log_chat_submit_event(
                        conversation_id=conversation_id,
                        event_type="chat_submit_confirmed",
                        payload={"source": "chat_booking"},
                    )
                else:
                    _log_lead_event_by_id(
                        lead_id=lead_id,
                        event_type="chat_submit_confirmed_unlinked",
                        actor="chat",
                        payload={
                            "source": "chat_booking",
                            "conversation_id": conversation_id,
                            "reason": "submission_mark_not_created",
                        },
                    )
            if payload.lang == "en":
                reply = (
                    f"{reply}\n\nYour request has been successfully submitted. "
                    "We will confirm your appointment via your provided contact details."
                ).strip()
            else:
                reply = (
                    f"{reply}\n\nIhre Anfrage wurde erfolgreich uebermittelt. "
                    "Wir bestaetigen den Termin ueber Ihre angegebenen Kontaktdaten."
                ).strip()
        except Exception:
            logger.exception(
                "Chat lead submit failed: request_id=%s conversation_id=%s",
                request_id,
                conversation_id,
            )
    elif booking_action == "reply_only" and booking_reply_text:
        if conversation_submitted:
            _log_chat_submit_event(
                conversation_id=conversation_id,
                event_type="chat_submit_blocked",
                payload={"reason": "duplicate_conversation_submit"},
            )
        reply = f"{reply}\n\n{booking_reply_text}".strip()

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_chat_event(
        logger,
        "chat_request_completed",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=payload.lang,
        page=page or "-",
        duration_ms=duration_ms,
        response_length=len(reply or ""),
        success=True,
    )

    reply_data = {
        "reply": reply,
        "request_id": request_id,
        "conversation_id": conversation_id,
        "lead_submitted": bool(lead_data),
        "lead": lead_data,
    }
    return success_response(
        "Dode reply generated",
        data=reply_data,
        legacy=reply_data,
    )
