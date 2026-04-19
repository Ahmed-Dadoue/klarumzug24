from __future__ import annotations

import re
from typing import Any

HANDOFF_CONTEXT_MARKERS = (
    "moechten sie",
    "soll ich",
    "kann ich",
    "weiter pruefen",
    "weiterpruefen",
    "weiterleiten",
    "uebermitteln",
    "zur pruefung",
    "anfrage",
    "angebot",
    "daten",
    "kontaktdaten",
    "intern",
    "team",
    "kollege",
)
HANDOFF_REQUEST_MARKERS = (
    "ja bitte",
    "mach das mal",
    "mach das bitte",
    "mach bitte",
    "mach es",
    "bitte weiterleiten",
    "weiterleiten",
    "leite",
    "senden",
    "schicken",
    "uebermitteln",
    "angebot",
    "anfrage",
    "auftrag",
    "bestellung",
    "email schicken",
    "mail schicken",
    "erwarte die mail",
)

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


def _normalize_for_match(text: str) -> str:
    normalized = " ".join((text or "").lower().split())
    replacements = {
        "\u00e4": "ae",
        "\u00f6": "oe",
        "\u00fc": "ue",
        "\u00df": "ss",
        "\u00c3\u00a4": "ae",
        "\u00c3\u00b6": "oe",
        "\u00c3\u00bc": "ue",
        "\u00c3\u009f": "ss",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _is_company_email_address_question(text: str | None) -> bool:
    normalized = _normalize_for_match(text or "")
    if not normalized:
        return False
    if CHAT_EMAIL_PATTERN.search(text or ""):
        return False
    address_markers = (
        "email adresse",
        "e-mail adresse",
        "e-mail-adresse",
        "mail adresse",
        "mailadresse",
        "eure email",
        "eure e-mail",
        "ihre email",
        "ihre e-mail",
        "welche email",
        "welche e-mail",
        "welche mail",
        "an welche mail",
        "wie lautet eure email",
        "wie lautet ihre email",
        "ich will aber eine email",
        "ich will aber eine e-mail",
        "ich moechte eine email adresse",
        "ich moechte eine e-mail adresse",
    )
    return any(marker in normalized for marker in address_markers)


def _extract_service_from_text(text: str) -> str | None:
    normalized = _normalize_for_match(text)
    if any(keyword in normalized for keyword in ("umzug", "umziehen", "ziehe", "move", "moving")):
        return "Umzug"
    if any(keyword in normalized for keyword in ("haushaltsaufloesung", "hausaufloesung")):
        return "Haushaltsaufloesung"
    if any(keyword in normalized for keyword in ("wohnungsaufloesung", "wohnung aufloesen")):
        return "Wohnungsaufloesung"
    if any(
        keyword in normalized
        for keyword in (
            "entruempelung",
            "entruempeln",
            "entrumpelung",
            "entrumpeln",
            "raeumung",
            "kellerraeumung",
            "dachbodenraeumung",
            "betriebsaufloesung",
            "firmenaufloesung",
        )
    ):
        return "Entruempelung"
    if any(
        keyword in normalized
        for keyword in (
            "arbeitsplatte",
            "kuechenplatte",
            "tischplatte",
            "ausschnitt",
            "spuele",
            "kochfeld",
        )
    ):
        if not any(
            keyword in normalized
            for keyword in (
                "kueche komplett",
                "komplette kueche",
                "kueche montieren",
                "kueche aufbauen",
                "kuechenmontage",
                "unterschrank",
                "oberschrank",
            )
        ):
            return "Arbeitsplatte"
        return "Kuechenmontage"
    if any(
        keyword in normalized
        for keyword in (
            "kueche",
            "kuechen",
            "kuechenmontage",
            "kuechenaufbau",
            "kuechen aufbau",
            "kueche montieren",
            "kueche aufbauen",
            "kuechen montiert",
        )
    ):
        return "Kuechenmontage"
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
    return all(candidate.get(field) for field in ("name", "email", "phone", "service", "location"))


def _last_assistant_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if getattr(message, "role", None) == "assistant":
            return str(getattr(message, "content", "") or "")
    return ""


def _conversation_has_handoff_context(messages: list[Any]) -> bool:
    assistant_text = _normalize_for_match(_last_assistant_text(messages))
    if any(marker in assistant_text for marker in HANDOFF_CONTEXT_MARKERS):
        return True
    joined = _normalize_for_match(
        "\n".join(
            str(getattr(message, "content", "") or "")
            for message in messages[-8:]
            if getattr(message, "role", None) == "assistant"
        )
    )
    return any(marker in joined for marker in HANDOFF_CONTEXT_MARKERS)


def _is_handoff_request(text: str | None, messages: list[Any]) -> bool:
    normalized = _normalize_for_match(text or "")
    if not normalized:
        return False
    if _is_company_email_address_question(text):
        return False
    has_context = _conversation_has_handoff_context(messages)
    if "ich stimme zu" in normalized and not has_context:
        return False
    if any(
        marker in normalized
        for marker in ("weiterleit", "leite", "auftrag", "bestellung")
    ):
        return True
    if has_context and any(
        marker in normalized
        for marker in (
            "mach das mal",
            "mach das bitte",
            "mach bitte",
            "mach es",
            "senden",
            "schicken",
            "uebermitteln",
            "angebot",
            "anfrage",
        )
    ):
        return True
    if "ja bitte" in normalized and has_context:
        return True
    if CHAT_EMAIL_PATTERN.search(text or "") and has_context:
        return True
    if "mail" in normalized and has_context and any(
        marker in normalized
        for marker in ("schicken", "senden", "erwarte", "uebermitteln", "weiterleiten", "anfrage", "angebot")
    ):
        return True
    return any(marker in normalized for marker in HANDOFF_REQUEST_MARKERS) and has_context


def _missing_contact_fields(candidate: dict[str, str | None]) -> list[str]:
    labels = {
        "name": "Name",
        "email": "E-Mail",
        "phone": "Telefonnummer",
        "service": "Leistung",
        "location": "Ort",
    }
    return [label for field, label in labels.items() if not candidate.get(field)]


def _build_missing_contact_reply(candidate: dict[str, str | None], lang: str) -> str:
    missing = _missing_contact_fields(candidate)
    missing_text = ", ".join(missing) if missing else "die Zustimmung"
    if lang == "en":
        return (
            "Not submitted yet. I can only forward the request for internal review after the required contact "
            f"details are complete. Still missing: {missing_text}. This is still a request, not a confirmed order."
        )
    known_parts = []
    if candidate.get("service"):
        known_parts.append(f"Leistung: {candidate.get('service')}")
    if candidate.get("location"):
        known_parts.append(f"Ort: {candidate.get('location')}")
    if candidate.get("email"):
        known_parts.append(f"E-Mail: {candidate.get('email')}")
    known_text = "\n".join(f"- {part}" for part in known_parts) if known_parts else "- bisher noch keine vollstaendigen Kontaktdaten"
    return (
        "Noch nicht uebermittelt. Ich kann die Anfrage erst intern zur Pruefung senden, wenn die Pflichtangaben "
        f"vollstaendig sind. Es fehlt noch: {missing_text}.\n\n"
        f"Bisher notiert:\n{known_text}\n\n"
        "Wichtig: Das ist noch keine Bestellung und kein verbindlicher Auftrag. "
        "Bitte senden Sie die fehlenden Angaben; danach frage ich nach der Zustimmung zu Datenschutz und AGB."
    )


def _is_chat_submit_consent(text: str | None) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    normalized = _normalize_for_match(normalized)
    consent_markers = (
        "ja, ich stimme zu und senden",
        "ja ich stimme zu und senden",
        "ich stimme zu und senden",
        "ja, ich stimme zu",
        "ja ich stimme zu",
        "i agree and send",
    )
    if any(marker in normalized for marker in consent_markers):
        return True
    yes_markers = ("ja", "passt", "ok", "okay", "einverstanden")
    send_markers = ("senden", "schicken", "uebermitteln", "angebot", "anfrage")
    return any(marker in normalized for marker in yes_markers) and any(
        marker in normalized for marker in send_markers
    )


def _build_consent_prompt(candidate: dict[str, str | None], lang: str) -> str:
    appointment = (
        f"{candidate.get('date')}" + (f" {candidate.get('time')}" if candidate.get("time") else "")
        if candidate.get("date")
        else "noch offen"
    )
    if lang == "en":
        return (
            "Before I forward your request for review, please confirm:\n"
            f"- Name: {candidate.get('name')}\n"
            f"- Email: {candidate.get('email')}\n"
            f"- Phone: {candidate.get('phone')}\n"
            f"- Service: {candidate.get('service')}\n"
            f"- Appointment: {appointment}\n"
            f"- Location: {candidate.get('location')}\n\n"
            "This is not a binding fixed-price offer or final appointment confirmation yet.\n"
            "Please confirm that you agree to our privacy policy and have read the terms (AGB).\n"
            "Links: /datenschutz-en.html and /agb-en.html\n"
            "Reply with: 'I agree and send'"
        )
    return (
        "Bevor ich Ihre Anfrage zur Pruefung an unser Team uebermittle, bitte kurz pruefen:\n"
        f"- Name: {candidate.get('name')}\n"
        f"- E-Mail: {candidate.get('email')}\n"
        f"- Telefon: {candidate.get('phone')}\n"
        f"- Service: {candidate.get('service')}\n"
        f"- Termin: {appointment}\n"
        f"- Ort: {candidate.get('location')}\n\n"
        "Das ist noch kein verbindliches Festpreisangebot und keine finale Terminbestaetigung.\n"
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
        if _is_handoff_request(user_message, messages):
            return {
                "action": "reply_only",
                "reply_text": _build_missing_contact_reply(candidate, lang),
                "override_reply": True,
                "lead_candidate": candidate,
            }
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
            "override_reply": True,
            "lead_candidate": candidate,
        }

    lead_message_parts = [
        f"Service: {candidate.get('service')}",
        (
            f"Termin: {candidate.get('date')}" + (f" {candidate.get('time')} Uhr" if candidate.get("time") else "")
            if candidate.get("date")
            else "Termin: noch offen"
        ),
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
