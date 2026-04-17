import time
import uuid
from typing import Any

from app.api import success_response
from app.ai.intent_classifier import classify_intent
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

try:
    from app.ai.learning.conversation_store import save_conversation as _save_learning_conversation
except Exception:
    _save_learning_conversation = None  # type: ignore[assignment]

try:
    from app.ai.learning.local_memory import capture_conversation_memory as _capture_local_memory
except Exception:
    _capture_local_memory = None  # type: ignore[assignment]

CONTACT_INTENT_KEYWORDS = {
    "de": ("kontakt", "telefon", "anrufen", "email", "e-mail", "whatsapp"),
    "en": ("contact", "phone", "call", "email", "whatsapp"),
}
KNOWN_CONVERSATION_TYPES = {"real_user", "test_script", "automated_test"}


def is_contact_intent(text: str | None, lang: ChatLanguage) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    keywords = CONTACT_INTENT_KEYWORDS.get(lang, CONTACT_INTENT_KEYWORDS["de"])
    return any(keyword in normalized for keyword in keywords)


def _normalize_conversation_type(
    conversation_type: str | None,
    conversation_id: str | None,
    source_label: str | None,
) -> str:
    normalized = normalize_text(conversation_type)
    if normalized in KNOWN_CONVERSATION_TYPES:
        return str(normalized)

    normalized_source = (source_label or "").strip().lower()
    normalized_conversation_id = (conversation_id or "").strip().lower()
    if normalized_conversation_id.startswith(("auto_", "ci_", "eval_", "harness_")) or any(
        token in normalized_source for token in ("automated", "ci", "eval", "harness")
    ):
        return "automated_test"
    if normalized_conversation_id.startswith(("test_", "script_", "local_")) or "test" in normalized_source:
        return "test_script"
    return "real_user"


def _collapse_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _detect_repetition_signals(messages: list[Any], reply: str) -> list[str]:
    signals: list[str] = []
    user_messages = [_collapse_text(message.content) for message in messages if message.role == "user"]
    assistant_messages = [_collapse_text(message.content) for message in messages if message.role == "assistant"]
    normalized_reply = _collapse_text(reply)

    if len(user_messages) >= 2 and user_messages[-1] and user_messages[-1] == user_messages[-2]:
        signals.append("user_repeated_same_question")
    if assistant_messages and normalized_reply and assistant_messages[-1] == normalized_reply:
        signals.append("assistant_repeated_previous_reply")
    return signals


def _detect_context_problems(
    *,
    source_used: str,
    fallback_used: bool,
    helper_path: str | None,
    faq_score: float | None,
    classified_intent: Any,
    booking_action: str | None,
    repetition_signals: list[str],
) -> list[str]:
    problems: list[str] = []
    if fallback_used:
        problems.append("openai_helper_fallback_used")
    if source_used == "faq" and faq_score is not None and faq_score < 0.45:
        problems.append("low_confidence_faq_match")
    if source_used == "openai" and not helper_path:
        problems.append("no_structured_helper_path")
    if source_used == "openai" and getattr(classified_intent, "intent_type", None) in {None, "general_question"}:
        problems.append("no_authoritative_source_selected")
    if booking_action == "ask_consent":
        problems.append("lead_flow_waiting_for_consent")
    if repetition_signals:
        problems.append("repetition_detected")
    return problems


def _build_candidate_knowledge(
    *,
    incoming_message: str,
    final_response: str,
    service_type: str | None,
    intent_type: str | None,
    source_used: str,
    helper_path: str | None,
    faq_id: str | None,
    context_problems: list[str],
    repetition_signals: list[str],
) -> list[dict[str, Any]]:
    question = sanitize_chat_log_text(incoming_message, max_length=320)
    answer = sanitize_chat_log_text(final_response, max_length=420)
    if not question:
        return []

    candidates: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    def append_candidate(candidate: dict[str, Any]) -> None:
        key = (
            str(candidate.get("memory_category") or ""),
            str(candidate.get("candidate_type") or ""),
        )
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(candidate)

    if source_used == "openai":
        append_candidate(
            {
                "memory_category": "faq_candidate",
                "candidate_type": "openai_answer_needs_review",
                "question": question,
                "answer": answer,
                "summary": "Neue oder unscharf abgedeckte Frage fuer FAQ-/Wissenspruefung.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.55,
                "metadata": {"helper_path": helper_path},
            }
        )

    if source_used in {"faq", "pricing", "tool", "rule", "service_truth", "policy_truth"} and answer:
        append_candidate(
            {
                "memory_category": "useful_approved_answer",
                "candidate_type": "structured_reply_pattern",
                "question": question,
                "answer": answer,
                "summary": "Strukturierte Antwortbasis fuer spaetere Wiederverwendung.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.72,
                "approved_answer_candidate": True,
                "metadata": {"helper_path": helper_path, "faq_id": faq_id},
            }
        )

    if (service_type and service_type != "umzug") or source_used in {"pricing", "tool"}:
        append_candidate(
            {
                "memory_category": "service_knowledge",
                "candidate_type": "service_pattern",
                "question": question,
                "answer": answer,
                "summary": "Servicebezogene Antwort oder Rueckfrage fuer lokales Wissen.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.68,
                "metadata": {"helper_path": helper_path},
            }
        )

    if context_problems:
        append_candidate(
            {
                "memory_category": "failure_case",
                "candidate_type": "context_problem",
                "question": question,
                "answer": answer,
                "summary": "Beobachteter Problemfall mit Kontext-, Fallback- oder Flow-Risiko.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.74,
                "metadata": {"context_problems": context_problems, "helper_path": helper_path},
            }
        )

    if repetition_signals:
        append_candidate(
            {
                "memory_category": "repeated_question",
                "candidate_type": "repetition_pattern",
                "question": question,
                "answer": answer,
                "summary": "Wiederholtes Frage- oder Antwortmuster fuer spaetere Entschaerfung.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.7,
                "metadata": {"repetition_signals": repetition_signals},
            }
        )

    if source_used == "faq" and faq_id:
        append_candidate(
            {
                "memory_category": "faq_candidate",
                "candidate_type": "faq_hit_validation",
                "question": question,
                "answer": answer,
                "summary": f"Bestehender FAQ-Treffer {faq_id} fuer spaetere Qualitaetspruefung.",
                "service_type": service_type,
                "intent_type": intent_type,
                "confidence": 0.61,
                "metadata": {"faq_id": faq_id},
            }
        )

    return candidates


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
    source_label = normalize_text(payload.source_label)
    test_run_id = normalize_text(payload.test_run_id)
    conversation_type = _normalize_conversation_type(
        payload.conversation_type,
        conversation_id,
        source_label,
    )
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
        conversation_type=conversation_type,
        source_label=source_label,
        test_run_id=test_run_id,
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
            conversation_type=conversation_type,
            source_label=source_label,
            test_run_id=test_run_id,
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
            conversation_type=conversation_type,
            source_label=source_label,
            test_run_id=test_run_id,
            lang=payload.lang,
            page=page or "-",
            conversion_step="contact_intent",
            success=True,
        )

    reply_trace: dict[str, Any] = {}
    try:
        generate_reply_kwargs = {
            "messages": payload.messages,
            "page": page,
            "lang": payload.lang,
            "session_factory": SessionLocal,
            "assigned_price_calculator": calculate_assigned_price,
            "logger": logger,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "trace": reply_trace,
        }
        try:
            reply = generate_reply(**generate_reply_kwargs)
        except TypeError as exc:
            if "unexpected keyword argument 'trace'" not in str(exc):
                raise
            generate_reply_kwargs.pop("trace", None)
            reply_trace = {}
            reply = generate_reply(**generate_reply_kwargs)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_chat_event(
            logger,
            "chat_request_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            conversation_type=conversation_type,
            source_label=source_label,
            test_run_id=test_run_id,
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
    source_used = str(reply_trace.get("source_used") or "openai")
    helper_path = normalize_text(str(reply_trace.get("helper_path") or "")) or "openai_primary_general"
    fallback_used = bool(reply_trace.get("fallback_used"))
    faq_meta = reply_trace.get("faq_meta") if isinstance(reply_trace.get("faq_meta"), dict) else {}
    truth_meta = reply_trace.get("truth_meta") if isinstance(reply_trace.get("truth_meta"), dict) else {}
    repetition_signals = _detect_repetition_signals(payload.messages, reply or "")

    classified_intent = None
    try:
        if last_user_message_raw:
            classified_intent = classify_intent(last_user_message_raw, lang=payload.lang)
    except Exception:
        classified_intent = None

    context_problems = _detect_context_problems(
        source_used=source_used,
        fallback_used=fallback_used,
        helper_path=helper_path,
        faq_score=faq_meta.get("faq_score") if isinstance(faq_meta.get("faq_score"), (int, float)) else None,
        classified_intent=classified_intent,
        booking_action=booking_action,
        repetition_signals=repetition_signals,
    )
    candidate_knowledge = _build_candidate_knowledge(
        incoming_message=last_user_message_raw,
        final_response=reply or "",
        service_type=getattr(classified_intent, "service_type", None),
        intent_type=getattr(classified_intent, "intent_type", None),
        source_used=source_used,
        helper_path=helper_path,
        faq_id=faq_meta.get("faq_id"),
        context_problems=context_problems,
        repetition_signals=repetition_signals,
    )

    memory_capture_result: dict[str, Any] = {
        "captured": False,
        "review_required": bool(payload.memory_review_required),
        "candidates_created": 0,
        "candidate_ids": [],
    }
    if _capture_local_memory is not None:
        try:
            memory_capture_result = _capture_local_memory(
                {
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "conversation_type": conversation_type,
                    "source_label": source_label,
                    "test_run_id": test_run_id,
                    "lang": payload.lang,
                    "page": page or "-",
                    "incoming_message": sanitize_chat_log_text(last_user_message_raw, max_length=320),
                    "intent_type": getattr(classified_intent, "intent_type", None),
                    "service_type": getattr(classified_intent, "service_type", None),
                    "source_used": source_used,
                    "helper_path": helper_path,
                    "fallback_used": fallback_used,
                    "final_response": sanitize_chat_log_text(reply or "", max_length=420),
                    "context_problems": context_problems,
                    "repetition_signals": repetition_signals,
                    "candidate_knowledge": candidate_knowledge,
                    "memory_review_required": payload.memory_review_required,
                    "lead_submitted": bool(lead_data),
                    "faq_meta": faq_meta,
                    "truth_meta": truth_meta,
                }
            )
        except Exception:
            memory_capture_result = {
                "captured": False,
                "review_required": bool(payload.memory_review_required),
                "candidates_created": 0,
                "candidate_ids": [],
                "reason": "capture_failed",
            }

    log_chat_event(
        logger,
        "chat_memory_capture",
        request_id=request_id,
        conversation_id=conversation_id,
        conversation_type=conversation_type,
        source_label=source_label,
        test_run_id=test_run_id,
        lang=payload.lang,
        page=page or "-",
        source_used=source_used,
        helper_path=helper_path,
        fallback_used=fallback_used,
        memory_candidate_count=memory_capture_result.get("candidates_created"),
        repetition_detected=bool(repetition_signals),
        context_problem_count=len(context_problems),
        success=bool(memory_capture_result.get("captured")),
    )
    log_chat_event(
        logger,
        "chat_request_completed",
        request_id=request_id,
        conversation_id=conversation_id,
        conversation_type=conversation_type,
        source_label=source_label,
        test_run_id=test_run_id,
        lang=payload.lang,
        page=page or "-",
        source_used=source_used,
        helper_path=helper_path,
        fallback_used=fallback_used,
        memory_candidate_count=memory_capture_result.get("candidates_created"),
        repetition_detected=bool(repetition_signals),
        context_problem_count=len(context_problems),
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
        "supervisor": {
            "conversation_type": conversation_type,
            "source_label": source_label,
            "test_run_id": test_run_id,
            "source_used": source_used,
            "helper_path": helper_path,
            "fallback_used": fallback_used,
            "truth_meta": truth_meta,
            "context_problems": context_problems,
            "repetition_signals": repetition_signals,
            "memory_candidates_created": memory_capture_result.get("candidates_created", 0),
            "memory_review_required": memory_capture_result.get("review_required", False),
        },
    }

    if _save_learning_conversation is not None:
        db = None
        try:
            db = SessionLocal()
            messages_for_learning = [
                {"role": message.role, "content": message.content} for message in payload.messages
            ]
            messages_for_learning.append({"role": "assistant", "content": reply or ""})
            outcome = "lead_created" if lead_data else "chat_completed"
            _save_learning_conversation(
                db,
                conversation_id=conversation_id,
                messages=messages_for_learning,
                conversation_type=conversation_type,
                source_label=source_label,
                test_run_id=test_run_id,
                service_type=getattr(classified_intent, "service_type", None),
                intent_type=getattr(classified_intent, "intent_type", None),
                source_used=source_used,
                helper_path=helper_path,
                fallback_used=fallback_used,
                telemetry={
                    "request_id": request_id,
                    "source_used": source_used,
                    "helper_path": helper_path,
                    "fallback_used": fallback_used,
                    "faq_meta": faq_meta,
                    "truth_meta": truth_meta,
                    "context_problems": context_problems,
                    "repetition_signals": repetition_signals,
                    "memory_capture": memory_capture_result,
                    "candidate_knowledge": candidate_knowledge,
                },
                outcome=outcome,
                language=payload.lang,
            )
        except Exception:
            pass  # Learning is optional - never block the chat
        finally:
            if db is not None:
                db.close()

    return success_response(
        "Dode reply generated",
        data=reply_data,
        legacy=reply_data,
    )
