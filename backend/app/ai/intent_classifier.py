"""
Intent classification for chat requests.
Determines the user's intent and the service they're inquiring about.
"""
import re
from typing import Optional

from .services import ServiceType, identify_service_type


class IntentType:
    """Intent types."""
    PRICING_INQUIRY = "pricing_inquiry"  # User asking for price
    GENERAL_QUESTION = "general_question"  # About services/regions/contact
    SERVICE_DETAILS = "service_details"  # Providing details about service
    CONTACT_REQUEST = "contact_request"  # Want to contact/call
    FEEDBACK = "feedback"  # Complaining or praising
    CLARIFICATION = "clarification"  # Asking for clarification


PRICING_RELATED_INTENTS = {
    IntentType.PRICING_INQUIRY,
    IntentType.SERVICE_DETAILS,
}


class ClassifiedIntent:
    """Result of intent classification."""

    def __init__(
        self,
        intent_type: str,
        service_type: Optional[ServiceType] = None,
        confidence: float = 0.0,
        reasoning: str = "",
    ):
        self.intent_type = intent_type
        self.service_type = service_type
        self.confidence = confidence
        self.reasoning = reasoning

    def __repr__(self):
        return f"Intent({self.intent_type}, service={self.service_type}, conf={self.confidence:.2f})"


def _normalize_text(value: str) -> str:
    text = " ".join((value or "").lower().strip().split())
    return (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _extract_focus_text(text_ascii: str) -> str:
    """Prefer the corrected segment after markers like 'ich meinte' or 'nein'."""
    markers = (
        "ich meinte",
        "ich meine",
        "eigentlich",
        "nein,",
        "nein ",
        "nicht umzug",
        "sondern",
    )
    for marker in markers:
        idx = text_ascii.rfind(marker)
        if idx >= 0:
            tail = text_ascii[idx + len(marker):].strip(" .,:;!?")
            if tail:
                return tail
    return text_ascii


def _detect_service_type(focus_text: str, full_text: str) -> ServiceType | None:
    transport_items = (
        "waschmaschine", "waschmachine", "waschmaschiene",
        "kuehlschrank", "kühlschrank",
        "sofa", "schrank", "bett", "klavier", "safe",
        "trockner", "spuelmaschine", "matratze",
    )

    has_transport_word = any(
        kw in focus_text
        for kw in ("einzeltransport", "transport", "lieferung", "abholung", "abholen", "gebracht")
    )
    has_transport_item = any(item in focus_text for item in transport_items)
    has_route_words = any(kw in focus_text for kw in (" von ", " nach "))
    has_umzug_word = any(kw in focus_text for kw in ("umzug", "umziehen", "ich ziehe", "ziehe von", "ziehe nach"))
    has_no_umzug = bool(re.search(r"\b(?:kein|nicht)\s+umzug\b", full_text))

    has_entsorgung = any(
        kw in focus_text
        for kw in (
            "entsorgung", "entsorgen", "entruempel", "entrumpel", "raeumung",
            "sperrmuell", "wegwerfen", "muell", "entruempelung", "wegmachen", "sofa weg",
        )
    )
    has_strong_entsorgung = any(
        kw in focus_text
        for kw in ("entruempel", "entrumpel", "raeumung", "sperrmuell", "entruempelung")
    )
    has_laminat = any(
        kw in focus_text
        for kw in ("laminat", "laminaten", "parkett", "boden", "fussboden", "quadratmeter", "m2", "bodenbelag")
    )
    has_montage = any(
        kw in focus_text
        for kw in ("moebelmontage", "moebelaufbau", "aufbauen", "montage", "montieren", "ikea")
    )

    if focus_text in ("transport", "transport?", "nur transport"):
        return "einzeltransport"

    # Multi-service mix with explicit move stays in move flow.
    if has_umzug_word and (has_entsorgung or has_laminat or has_montage):
        return "umzug"

    # Mixed service question should be treated as broad inquiry upstream.
    if "kann ich" in focus_text and has_entsorgung and (has_transport_word or has_transport_item):
        return None

    # Strong transport signal should win over generic umzug/montage matches.
    if (has_transport_word and has_transport_item) or (has_transport_word and has_route_words and has_no_umzug):
        return "einzeltransport"
    if has_no_umzug and has_transport_item:
        return "einzeltransport"

    # Laminat must not fall into generic entsorgung, unless strong entsorgung signal is present.
    if has_laminat and has_strong_entsorgung:
        return "entsorgung"
    if has_laminat:
        return "laminat"

    if has_no_umzug and has_entsorgung:
        return "entsorgung"
    if has_no_umzug and (has_transport_word or has_transport_item):
        return "einzeltransport"
    if has_entsorgung:
        return "entsorgung"
    if has_transport_word and (has_transport_item or has_route_words) and not has_umzug_word:
        return "einzeltransport"
    if has_montage and not has_entsorgung and not has_transport_word:
        return "moebelmontage"
    if has_umzug_word:
        return "umzug"

    return identify_service_type(focus_text)


def classify_intent(user_message: str, lang: str = "de") -> ClassifiedIntent:
    """
    Classify user intent from their message.
    Returns: ClassifiedIntent with type, service, confidence.
    """
    _ = lang
    text_ascii = _normalize_text(user_message)
    focus_text = _extract_focus_text(text_ascii)

    pricing_keywords = [
        "preis", "kostet", "kosten", "wie viel", "wieviel",
        "angebot", "schaetzung", "schatzung", "guenstig", "gunstig",
        "teuer", "zu teuer", "bezahlbar", "euro", "eur",
    ]
    is_pricing = any(kw in text_ascii for kw in pricing_keywords)

    contact_keywords = [
        "anrufen", "telefonieren", "whatsapp", "email", "kontakt",
        "berater", "sprechen", "termin", "besuch", "vor ort",
        "kommt vorbei", "telefonnummer", "erreichen", "zurueckrufen",
    ]
    is_contact = any(kw in text_ascii for kw in contact_keywords)

    feedback_keywords = [
        "danke", "super", "gut", "schlecht", "furchtbar", "awesome",
        "warum", "wieso", "macht keinen sinn", "passt nicht",
        "falsch verstanden", "das meine ich nicht", "du hast mich falsch verstanden",
        "warum fragst du", "warum antwortest du", "bitte direkt antworten",
    ]
    is_feedback = any(kw in text_ascii for kw in feedback_keywords)

    general_keywords = [
        "was", "wie", "welche", "leistungen", "regionen", "gehoert",
        "angebote", "services", "ihr",
    ]
    is_general = any(kw in text_ascii for kw in general_keywords)

    service_type = _detect_service_type(focus_text, text_ascii)
    correction_detected = focus_text != text_ascii

    if correction_detected and service_type and not is_pricing:
        return ClassifiedIntent(
            intent_type=IntentType.SERVICE_DETAILS,
            service_type=service_type,
            confidence=0.95,
            reasoning=f"User correction points to {service_type} service",
        )

    if ("warum" in text_ascii or "wieso" in text_ascii) and is_feedback:
        return ClassifiedIntent(
            intent_type=IntentType.FEEDBACK,
            service_type=service_type,
            confidence=0.9,
            reasoning="Why-question indicates feedback/objection intent",
        )

    if is_pricing and service_type:
        return ClassifiedIntent(
            intent_type=IntentType.PRICING_INQUIRY,
            service_type=service_type,
            confidence=0.95,
            reasoning=f"Pricing inquiry for {service_type} service",
        )
    if is_pricing:
        return ClassifiedIntent(
            intent_type=IntentType.PRICING_INQUIRY,
            service_type=None,
            confidence=0.85,
            reasoning="Pricing inquiry but service not clear",
        )
    if is_contact:
        return ClassifiedIntent(
            intent_type=IntentType.CONTACT_REQUEST,
            service_type=service_type,
            confidence=0.9,
            reasoning="User wants to contact or meet",
        )
    if is_feedback:
        return ClassifiedIntent(
            intent_type=IntentType.FEEDBACK,
            service_type=service_type,
            confidence=0.85,
            reasoning="User providing feedback or clarification",
        )
    if service_type:
        return ClassifiedIntent(
            intent_type=IntentType.SERVICE_DETAILS,
            service_type=service_type,
            confidence=0.9,
            reasoning=f"Details about {service_type} service",
        )
    if is_general:
        return ClassifiedIntent(
            intent_type=IntentType.GENERAL_QUESTION,
            service_type=None,
            confidence=0.7,
            reasoning="General question about services",
        )
    return ClassifiedIntent(
        intent_type=IntentType.GENERAL_QUESTION,
        service_type=None,
        confidence=0.3,
        reasoning="Unclear intent",
    )


def is_pricing_related_intent(intent_type: str) -> bool:
    """Return True if intent indicates a pricing/detail flow."""
    return intent_type in PRICING_RELATED_INTENTS
