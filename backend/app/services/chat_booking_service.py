from __future__ import annotations

import re
from typing import Any

CHAT_NAME_PATTERN = re.compile(
    r"\b(?:mein name ist|ich bin|name)\s+([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß .'-]{1,80})",
    re.IGNORECASE,
)
CHAT_NAME_PATTERN_EN = re.compile(
    r"\b(?:my name is|i am|name is)\s+([A-Za-z][A-Za-z .'-]{1,80})",
    re.IGNORECASE,
)
CHAT_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
CHAT_PHONE_PATTERN = re.compile(r"(?:\+49|0049|0)[\d\s()./-]{7,20}")
CHAT_DATE_TIME_PATTERN = re.compile(
    r"\b(\d{1,2}\.\d{1,2}\.\d{2,4})(?:\s*(?:um|at|,)?\s*(\d{1,2}[:.]\d{2})\s*(?:uhr)?)?",
    re.IGNORECASE,
)
CHAT_LOCATION_PATTERN = re.compile(
    r"\b(?:in|am|an der|an|at)\s+([A-Za-zÄÖÜäöüß0-9 .'-]{2,80})",
    re.IGNORECASE,
)


def _extract_service_from_text(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    if any(keyword in normalized for keyword in ("umzug", "umziehen", "ziehe", "move", "moving")):
        return "Umzug"
    if any(
        keyword in normalized
        for keyword in ("entsorgung", "entsorgen", "entrümpel", "entruempel", "sperrmüll", "sperrmuell", "disposal", "junk removal", "clearance")
    ):
        return "Entsorgung"
    if any(keyword in normalized for keyword in ("laminat", "parkett", "boden", "laminate", "parquet", "flooring")):
        return "Laminat"
    if any(
        keyword in normalized
        for keyword in ("montage", "aufbauen", "möbel", "moebel", "ikea", "assembly", "furniture assembly", "install")
    ):
        return "Möbelmontage"
    if any(
        keyword in normalized
        for keyword in (
            "einzeltransport",
            "transport",
            "waschmaschine",
            "kühlschrank",
            "kuehlschrank",
            "single transport",
            "item transport",
            "washing machine",
            "fridge",
            "refrigerator",
        )
    ):
        return "Einzeltransport"
    return None


def _extract_chat_lead_candidate(messages: list[Any]) -> dict[str, str | None]:
    user_texts = []
    for message in messages:
        if getattr(message, "role", None) == "user":
            user_texts.append(" ".join(str(getattr(message, "content", "")).split()))
    joined = "\n".join(user_texts)

    name = None
    name_match = CHAT_NAME_PATTERN.search(joined) or CHAT_NAME_PATTERN_EN.search(joined)
    if name_match:
        name = name_match.group(1).strip(" .,:;!?")

    email = None
    email_matches = CHAT_EMAIL_PATTERN.findall(joined)
    if email_matches:
        email = email_matches[-1].strip()

    phone = None
    phone_matches = CHAT_PHONE_PATTERN.findall(joined)
    if phone_matches:
        phone = re.sub(r"\s+", "", phone_matches[-1]).strip()

    date_value = None
    time_value = None
    date_matches = CHAT_DATE_TIME_PATTERN.findall(joined)
    if date_matches:
        date_value, time_value = date_matches[-1]
        if time_value:
            time_value = time_value.replace(".", ":")

    location = None
    location_matches = CHAT_LOCATION_PATTERN.findall(joined)
    if location_matches:
        location = location_matches[-1].strip(" .,:;!?")

    service = _extract_service_from_text(joined)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "service": service,
        "date": date_value,
        "time": time_value,
        "location": location,
    }


def _is_chat_lead_complete(candidate: dict[str, str | None]) -> bool:
    return all(candidate.get(field) for field in ("name", "email", "phone", "service", "date", "location"))


def _is_chat_submit_consent(text: str | None) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    consent_markers = (
        "ja, ich stimme zu und senden",
        "ja ich stimme zu und senden",
        "ich stimme zu und senden",
        "ja, ich stimme zu",
        "ja ich stimme zu",
        "i agree and send",
    )
    return any(marker in normalized for marker in consent_markers)


def _build_consent_prompt(candidate: dict[str, str | None], lang: str) -> str:
    appointment = f"{candidate.get('date')}" + (f" {candidate.get('time')}" if candidate.get("time") else "")
    if lang == "en":
        return (
            "Before I submit your request as binding, please confirm:\n"
            f"- Name: {candidate.get('name')}\n"
            f"- Email: {candidate.get('email')}\n"
            f"- Phone: {candidate.get('phone')}\n"
            f"- Service: {candidate.get('service')}\n"
            f"- Appointment: {appointment}\n"
            f"- Location: {candidate.get('location')}\n\n"
            "Please confirm that you agree to our privacy policy and have read the terms (AGB).\n"
            "Links: /datenschutz-en.html and /agb-en.html\n"
            "Reply with: 'I agree and send'"
        )
    return (
        "Bevor ich Ihre Anfrage verbindlich uebermittle, bitte kurz pruefen:\n"
        f"- Name: {candidate.get('name')}\n"
        f"- E-Mail: {candidate.get('email')}\n"
        f"- Telefon: {candidate.get('phone')}\n"
        f"- Service: {candidate.get('service')}\n"
        f"- Termin: {appointment}\n"
        f"- Ort: {candidate.get('location')}\n\n"
        "Bitte bestaetigen Sie, dass Sie unseren Datenschutzbestimmungen zustimmen und die AGB zur Kenntnis genommen haben.\n"
        "Links: /datenschutz.html und /agb.html\n"
        "Antworten Sie mit: 'Ja, ich stimme zu und senden'"
    )


def process(conversation_id: str, user_message: str, current_state: dict[str, Any]) -> dict[str, Any]:
    lang = str(current_state.get("lang", "de"))
    messages = list(current_state.get("messages", []))
    conversation_submitted = bool(current_state.get("conversation_submitted", False))
    candidate = _extract_chat_lead_candidate(messages)

    if not _is_chat_lead_complete(candidate):
        return {"action": "reply_only", "reply_text": None}

    if conversation_submitted:
        duplicate_msg = (
            "Your request has already been submitted. We will contact you shortly."
            if lang == "en"
            else "Ihre Anfrage wurde bereits uebermittelt. Wir melden uns in Kuerze."
        )
        return {"action": "reply_only", "reply_text": duplicate_msg}

    if not _is_chat_submit_consent(user_message):
        return {
            "action": "ask_consent",
            "reply_text": _build_consent_prompt(candidate, lang),
            "lead_candidate": candidate,
        }

    lead_message_parts = [
        f"Service: {candidate.get('service')}",
        f"Termin: {candidate.get('date')}" + (f" {candidate.get('time')} Uhr" if candidate.get("time") else ""),
        f"Ort: {candidate.get('location')}",
        "Quelle: Chat",
        "Consent: Datenschutz+AGB bestaetigt",
    ]

    return {
        "action": "submit_lead",
        "reply_text": None,
        "lead_payload": {
            "name": (candidate.get("name") or "").strip(),
            "phone": (candidate.get("phone") or "").strip(),
            "email": (candidate.get("email") or "").strip(),
            "message": " | ".join(part for part in lead_message_parts if part),
            "accepted_agb": True,
            "accepted_privacy": True,
        },
    }
