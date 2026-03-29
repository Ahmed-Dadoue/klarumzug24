import logging
import os
import re
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import HTTPException

from .faq_store import find_best_faq_match, get_faq_filename
from .logging_utils import log_chat_event, log_chat_exception
from .prompts import build_dode_system_prompt, build_general_chat_prompt
from .prompts_v2 import build_dode_system_prompt_v2
from .schemas import ChatLanguage, ChatTurn, MoveDetails
from .tools import calculate_move_price
from .pricing_tool import get_pricing_tool

DODE_MODEL = os.getenv("DODE_MODEL", "gpt-4.1-mini").strip()
DODE_MAX_MESSAGES = int(os.getenv("DODE_MAX_MESSAGES", "12"))
DODE_MAX_OUTPUT_TOKENS = int(os.getenv("DODE_MAX_OUTPUT_TOKENS", "220"))

NON_CITY_WORDS = {
    "hallo", "hi", "hey", "hello", "ja", "nein", "yes", "no", "ok", "okay",
    "preis", "kosten", "price", "cost", "quote", "angebot", "umzug", "move",
    "moving", "estimate", "schaetzung",
}

CITY_PATTERN = re.compile(
    r"(?:von|aus|from)\s+([A-Za-zA-Z][A-Za-zA-Z .-]{1,80}?)\s+(?:nach|in|to)\s+([A-Za-zA-Z][A-Za-zA-Z .-]{1,80})(?:[,.!?]|$)",
    re.IGNORECASE,
)
TRAILING_VERB_PATTERN = re.compile(r"\s+(?:umziehen|umzuziehen|ziehen|fahren|gehen|move|moving)\s*$", re.IGNORECASE)
CITY_ONLY_PATTERN = re.compile(r"^[A-Za-zA-Z][A-Za-zA-Z .-]{1,80}$")
ROOMS_PATTERN = re.compile(r"(\d{1,2})\s*(?:zimmer|raeume|raume|rooms?)", re.IGNORECASE)
DISTANCE_PATTERN = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:km|kilometer|kilometres|kilometers)", re.IGNORECASE)
MOVE_DATE_PATTERN = re.compile(r"\b(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\b")
FLOOR_FROM_PATTERN = re.compile(r"(?:auszug|von|aus|from)\D{0,20}(\d{1,2})\s*\.?\s*(?:stock|stockwerk|og|floor)", re.IGNORECASE)
FLOOR_TO_PATTERN = re.compile(r"(?:einzug|nach|in|ins|to)\D{0,20}(\d{1,2})\s*\.?\s*(?:stock|stockwerk|og|floor)", re.IGNORECASE)
ELEVATOR_FROM_TRUE_PATTERN = re.compile(r"(?:auszug|start|von|from)\D{0,20}(?:mit|vorhanden|with).{0,12}(?:aufzug|elevator|lift)", re.IGNORECASE)
ELEVATOR_FROM_FALSE_PATTERN = re.compile(r"(?:auszug|start|von|from)\D{0,20}(?:ohne|kein(?:en|em)?|without|no).{0,12}(?:aufzug|elevator|lift)", re.IGNORECASE)
ELEVATOR_TO_TRUE_PATTERN = re.compile(r"(?:einzug|ziel|nach|to)\D{0,20}(?:mit|vorhanden|with).{0,12}(?:aufzug|elevator|lift)", re.IGNORECASE)
ELEVATOR_TO_FALSE_PATTERN = re.compile(r"(?:einzug|ziel|nach|to)\D{0,20}(?:ohne|kein(?:en|em)?|without|no).{0,12}(?:aufzug|elevator|lift)", re.IGNORECASE)
STANDALONE_NUMBER_PATTERN = re.compile(r"\b(\d{1,4}(?:[.,]\d{1,2})?)\b")
ROOM_HINT_PATTERN = re.compile(r"\b(?:zimmer|raum|raeume|raume|room|rooms)\b", re.IGNORECASE)
DISTANCE_HINT_PATTERN = re.compile(r"\b(?:km|kilometer|kilometres|kilometers|strecke|distanz|entfernung|distance|route)\b", re.IGNORECASE)
ESTIMATE_REPLY_PATTERN = re.compile(r"(?:unverbindlich\w*\s+schaetz\w+|non-binding\s+estimate).*(?:eur|euro)", re.IGNORECASE)
DONT_KNOW_DISTANCE_PATTERN = re.compile(r"\b(?:weiss nicht|keine ahnung|keine angabe|unbekannt|nicht sicher|don't know|do not know|not sure|unknown)\b", re.IGNORECASE)

CITY_DISTANCES: dict[frozenset[str], int] = {
    frozenset({"kiel", "hamburg"}): 90,
    frozenset({"luebeck", "hamburg"}): 65,
    frozenset({"berlin", "hamburg"}): 290,
    frozenset({"berlin", "hannover"}): 285,
    frozenset({"hamburg", "hannover"}): 150,
    frozenset({"hamburg", "bremen"}): 120,
    frozenset({"frankfurt", "koeln"}): 190,
    frozenset({"koeln", "duesseldorf"}): 45,
    frozenset({"muenchen", "stuttgart"}): 220,
}

NUMBER_WORDS = {
    "null": 0, "ein": 1, "eins": 1, "eine": 1, "einen": 1, "zwei": 2, "drei": 3,
    "vier": 4, "fuenf": 5, "funf": 5, "sechs": 6, "sieben": 7, "acht": 8,
    "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12, "zwolf": 12, "dreizehn": 13,
    "vierzehn": 14, "fuenfzehn": 15, "funfzehn": 15, "sechzehn": 16, "siebzehn": 17,
    "achtzehn": 18, "neunzehn": 19, "zwanzig": 20,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

TEXT = {
    "de": {
        "customer_label": "Kunde",
        "from_city": ["Aus welcher Stadt ziehen Sie um?", "Von welcher Stadt aus startet Ihr Umzug?"],
        "to_city": ["In welche Stadt ziehen Sie um?", "In welche Zielstadt soll es gehen?"],
        "rooms": ["Wie viele Zimmer sind es ungefaehr?", "Wie viele Zimmer hat die Wohnung etwa?"],
        "distance_km": ["Wie viele Kilometer liegen ungefaehr zwischen Start und Ziel?", "Wie gross ist die Strecke ungefaehr in Kilometern?"],
        "intros": [
            "Gern helfe ich Ihnen mit einer unverbindlichen Schaetzung.",
            "Danke, dann machen wir direkt mit der unverbindlichen Schaetzung weiter.",
            "Alles klar, fuer die unverbindliche Schaetzung brauche ich noch kurz diese Angabe.",
        ],
        "distance_hint": "Orientierung: {from_city} nach {to_city} sind ungefaehr {km} km.",
        "sanity": "Meinten Sie wirklich {value} Zimmer oder eher die Entfernung in Kilometern?",
        "same_city_note": " Hinweis: Start- und Zielort sind identisch. Bitte pruefen Sie die Eingabe der Strecke.",
        "move_date_note": " Fuer den Termin {date} kann die Planung spaeter noch konkretisiert werden.",
        "estimate_single": "ca. {price} EUR",
        "estimate_range": "ca. {price_min} bis {price_max} EUR",
        "estimate_reply": "Fuer Ihren Umzug von {from_city} nach {to_city} liegt die unverbindliche Schaetzung aktuell bei {price_text}. {explanation} Das ist kein verbindliches Festpreisangebot.{same_city_note}{move_date_note}",
        "faq_suffix": "Weitere Informationen finden Sie auf {source_page}.",
        "dode_unavailable": "Dode ist gerade nicht erreichbar.",
        "estimate_keywords": ("preis", "kosten", "schaetzung", "angebot", "umzug", "umziehen", "umzugs"),
        "general_keywords": ("kontakt", "erreichen", "telefon", "anrufen", "email", "e-mail", "whatsapp", "adresse", "oeffnungszeiten"),
        "reuse_keywords": ("nochmal", "noch mal", "wieder", "erneut", "gleich", "gleiche", "noch eine", "noch einen"),
        "move_markers": ("umzug", "ich ziehe"),
        "single_transport_keywords": ("transport", "einzeltransport", "nur transport", "nur waschmaschine", "nur kuehlschrank"),
        "single_transport_items": (
            "waschmaschine",
            "kuehlschrank",
            "kühlschrank",
            "sofa",
            "schrank",
            "bett",
            "matratze",
            "fernseher",
            "tv",
            "kommode",
            "spuelmaschine",
            "spülmaschine",
            "trockner",
        ),
        "single_transport_no_move_markers": (
            "kein umzug",
            "nicht umziehen",
            "nur transport",
            "nur eine",
            "nur ein",
        ),
        "single_transport_reply": (
            "Verstanden, dann geht es um einen Einzeltransport und nicht um einen kompletten Umzug. "
            "Das ist grundsaetzlich moeglich. Fuer eine sinnvolle unverbindliche Einschaetzung brauche ich nur kurz: "
            "Abhol- und Zieladresse, Etage bei Abholung und Ziel sowie ob ein Aufzug vorhanden ist. "
            "Wenn Sie moechten, kann ich Sie direkt zur Anfrage ueber /kontakt.html oder WhatsApp fuehren."
        ),
        "assistant_expected": {
            "from_city": ("aus welcher stadt", "von welcher stadt"),
            "to_city": ("in welche stadt", "zielstadt"),
            "rooms": ("wie viele zimmer",),
            "distance_km": ("wie viele kilometer", "strecke"),
        },
        "localized_pages": {
            "/index.html": "/index.html",
            "/kontakt.html": "/kontakt.html",
            "/umzugsrechner.html": "/umzugsrechner.html",
            "/ueber-uns.html": "/ueber-uns.html",
            "/agb.html": "/agb.html",
            "/datenschutz.html": "/datenschutz.html",
            "/impressum.html": "/impressum.html",
        },
    },
    "en": {
        "customer_label": "Customer",
        "from_city": ["Which city are you moving from?", "What is the start city of your move?"],
        "to_city": ["Which city are you moving to?", "What is the destination city?"],
        "rooms": ["How many rooms are involved approximately?", "How many rooms does the home have roughly?"],
        "distance_km": ["How many kilometres are there approximately between start and destination?", "What is the approximate distance in kilometres?"],
        "intros": [
            "I am happy to help with a non-binding estimate.",
            "Thanks, let's continue with the non-binding estimate.",
            "Alright, I just need this short detail for the non-binding estimate.",
        ],
        "distance_hint": "For orientation: {from_city} to {to_city} is approximately {km} km.",
        "sanity": "Did you really mean {value} rooms, or did you mean the distance in kilometres?",
        "same_city_note": " Note: the start and destination city are identical. Please check the distance input.",
        "move_date_note": " The planning for {date} can be refined later.",
        "estimate_single": "about {price} EUR",
        "estimate_range": "about {price_min} to {price_max} EUR",
        "estimate_reply": "For your move from {from_city} to {to_city}, the current non-binding estimate is {price_text}. {explanation} This is not a binding fixed-price offer.{same_city_note}{move_date_note}",
        "faq_suffix": "You can find more information on {source_page}.",
        "dode_unavailable": "Dode is currently unavailable.",
        "estimate_keywords": ("price", "cost", "quote", "estimate", "move", "moving"),
        "general_keywords": ("contact", "reach", "phone", "call", "email", "whatsapp", "address", "opening hours"),
        "reuse_keywords": ("again", "same", "another", "repeat", "once more"),
        "move_markers": ("move", "moving"),
        "single_transport_keywords": ("transport", "single transport", "item transport"),
        "single_transport_items": (
            "washing machine",
            "fridge",
            "refrigerator",
            "sofa",
            "cabinet",
            "wardrobe",
            "bed",
            "mattress",
            "tv",
            "television",
            "dishwasher",
            "dryer",
        ),
        "single_transport_no_move_markers": (
            "not moving",
            "no move",
            "only transport",
            "just transport",
            "only one item",
            "just one item",
        ),
        "single_transport_reply": (
            "Understood, this is a single-item transport and not a full move. "
            "That is generally possible. For a useful non-binding estimate I only need: "
            "pickup and destination address, floor at pickup and destination, and whether an elevator is available. "
            "If you want, I can guide you directly to /kontakt-en.html or WhatsApp to submit the request."
        ),
        "assistant_expected": {
            "from_city": ("which city are you moving from", "start city"),
            "to_city": ("which city are you moving to", "destination city"),
            "rooms": ("how many rooms",),
            "distance_km": ("how many kilometres", "approximate distance"),
        },
        "localized_pages": {
            "/index.html": "/index-en.html",
            "/kontakt.html": "/kontakt-en.html",
            "/umzugsrechner.html": "/umzugsrechner-en.html",
            "/ueber-uns.html": "/ueber-uns-en.html",
            "/agb.html": "/agb-en.html",
            "/datenschutz.html": "/datenschutz-en.html",
            "/impressum.html": "/impressum-en.html",
            "/index-en.html": "/index-en.html",
            "/kontakt-en.html": "/kontakt-en.html",
            "/umzugsrechner-en.html": "/umzugsrechner-en.html",
            "/ueber-uns-en.html": "/ueber-uns-en.html",
            "/agb-en.html": "/agb-en.html",
            "/datenschutz-en.html": "/datenschutz-en.html",
            "/impressum-en.html": "/impressum-en.html",
        },
    },
}


def _lookup_distance(from_city: str, to_city: str) -> int | None:
    key = frozenset({_normalize_for_compare(from_city), _normalize_for_compare(to_city)})
    return CITY_DISTANCES.get(key)


def get_dode_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Dode AI ist noch nicht konfiguriert.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OpenAI client library is not installed.") from exc

    return OpenAI(api_key=api_key)


def _lang_config(lang: ChatLanguage) -> dict[str, Any]:
    return TEXT[lang if lang in TEXT else "de"]


def _localize_page_path(path: str | None, lang: ChatLanguage) -> str | None:
    if not path:
        return None
    config = _lang_config(lang)
    return config["localized_pages"].get(path, path)


def _localize_text_links(text: str, lang: ChatLanguage) -> str:
    if not text:
        return text
    localized = text
    for source, target in _lang_config(lang)["localized_pages"].items():
        localized = localized.replace(source, target)
    return localized


def _as_chat_turn(message: Any) -> ChatTurn:
    if isinstance(message, ChatTurn):
        return message
    if hasattr(message, "model_dump"):
        return ChatTurn.model_validate(message.model_dump())
    if isinstance(message, dict):
        return ChatTurn.model_validate(message)
    return ChatTurn.model_validate({"role": getattr(message, "role"), "content": getattr(message, "content")})


def _normalize_city(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" ,.;:!?")
    cleaned = TRAILING_VERB_PATTERN.sub("", cleaned).strip()
    if not cleaned:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def _normalize_for_compare(value: str) -> str:
    return " ".join(value.lower().split())


def _is_city_like_answer(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or not CITY_ONLY_PATTERN.fullmatch(cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in NON_CITY_WORDS:
        return False
    return len(cleaned.split()) <= 4


def _extract_number_from_text(text: str) -> float | None:
    direct_match = STANDALONE_NUMBER_PATTERN.search(text)
    if direct_match:
        return float(direct_match.group(1).replace(",", "."))
    for token in re.findall(r"[A-Za-zA-Z]+", text.lower()):
        if token in NUMBER_WORDS:
            return float(NUMBER_WORDS[token])
    return None


def _extract_rooms_value(text: str, expect_rooms: bool) -> int | None:
    rooms_match = ROOMS_PATTERN.search(text)
    if rooms_match:
        return int(rooms_match.group(1))
    if not expect_rooms and not ROOM_HINT_PATTERN.search(text):
        return None
    number = _extract_number_from_text(text)
    if number is None:
        return None
    rooms = int(round(number))
    if 1 <= rooms <= 50:
        return rooms
    return None


def _extract_distance_value(text: str, expect_distance: bool) -> float | None:
    distance_match = DISTANCE_PATTERN.search(text)
    if distance_match:
        return float(distance_match.group(1).replace(",", "."))
    if not expect_distance and not DISTANCE_HINT_PATTERN.search(text):
        return None
    number = _extract_number_from_text(text)
    if number is None:
        return None
    if 1 <= number <= 200000:
        return float(number)
    return None


def _infer_expected_field_from_assistant(text: str, lang: ChatLanguage) -> str | None:
    lowered = " ".join(text.lower().split())
    for field, markers in _lang_config(lang)["assistant_expected"].items():
        if any(marker in lowered for marker in markers):
            return field
    if "meinten sie wirklich" in lowered or "did you really mean" in lowered:
        return "rooms"
    return None


def _is_estimate_reply(text: str) -> bool:
    normalized = " ".join(text.split())
    return bool(ESTIMATE_REPLY_PATTERN.search(normalized))


def _last_estimate_reply_index(messages: Sequence[ChatTurn]) -> int:
    for idx in range(len(messages) - 1, -1, -1):
        if messages[idx].role == "assistant" and _is_estimate_reply(messages[idx].content):
            return idx
    return -1


def _last_assistant_message(messages: Sequence[ChatTurn]) -> str | None:
    for message in reversed(messages):
        if message.role == "assistant":
            return message.content
    return None


def _last_user_message(messages: Sequence[ChatTurn]) -> str | None:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return None


def _is_reuse_estimate_request(messages: Sequence[ChatTurn], lang: ChatLanguage) -> bool:
    user_messages = [" ".join(message.content.lower().split()) for message in messages if message.role == "user"]
    if not user_messages:
        return False
    user_text = " ".join(user_messages)
    estimate_keywords = _lang_config(lang)["estimate_keywords"]
    if not any(keyword in user_text for keyword in estimate_keywords):
        return False
    return any(keyword in user_text for keyword in _lang_config(lang)["reuse_keywords"])


def _is_general_topic_switch(messages: Sequence[ChatTurn], lang: ChatLanguage) -> bool:
    last_user_text = _last_user_message(messages)
    if not last_user_text:
        return False
    lowered = " ".join(last_user_text.lower().split())
    if any(keyword in lowered for keyword in _lang_config(lang)["estimate_keywords"]):
        return False
    return any(keyword in lowered for keyword in _lang_config(lang)["general_keywords"])


def _merge_missing_move_details(current: MoveDetails, previous: MoveDetails) -> MoveDetails:
    merged_data = current.model_dump()
    for key, value in previous.model_dump().items():
        if merged_data.get(key) is None and value is not None:
            merged_data[key] = value
    return MoveDetails.model_validate(merged_data)


def _build_sanity_clarification(messages: Sequence[ChatTurn], move_details: MoveDetails, lang: ChatLanguage) -> str | None:
    expected_field = _infer_expected_field_from_assistant(_last_assistant_message(messages) or "", lang)
    if expected_field != "rooms" or move_details.rooms is not None:
        return None
    last_user_text = _last_user_message(messages)
    if not last_user_text:
        return None
    number = _extract_number_from_text(last_user_text)
    if number is None:
        return None
    rounded_value = int(round(number))
    if rounded_value >= 30:
        return _lang_config(lang)["sanity"].format(value=rounded_value)
    return None


def _choose_variant(options: list[str], last_assistant_text: str | None) -> str:
    if not options:
        return ""
    if not last_assistant_text:
        return options[0]
    normalized_last = _normalize_for_compare(last_assistant_text)
    for option in options:
        if _normalize_for_compare(option) not in normalized_last:
            return option
    return options[1] if len(options) > 1 else options[0]


def _extract_move_details(messages: Sequence[ChatTurn], lang: ChatLanguage) -> MoveDetails:
    details = MoveDetails()
    expected_field: str | None = None
    for message in messages:
        if message.role == "assistant":
            expected_field = _infer_expected_field_from_assistant(message.content, lang)
            continue
        if message.role != "user":
            continue

        text = " ".join(message.content.split())
        city_match = CITY_PATTERN.search(text)
        if city_match:
            details.from_city = _normalize_city(city_match.group(1))
            details.to_city = _normalize_city(city_match.group(2))
        elif _is_city_like_answer(text):
            city_name = _normalize_city(text)
            if expected_field == "from_city" and not details.from_city:
                details.from_city = city_name
                expected_field = None
            elif expected_field == "to_city" and not details.to_city:
                if not details.from_city or city_name.lower() != details.from_city.lower():
                    details.to_city = city_name
                    expected_field = None
            elif not details.from_city:
                details.from_city = city_name
            elif not details.to_city and city_name.lower() != details.from_city.lower():
                details.to_city = city_name

        rooms_value = _extract_rooms_value(text, expect_rooms=expected_field == "rooms")
        if rooms_value is not None:
            details.rooms = rooms_value
            if expected_field == "rooms":
                expected_field = None

        distance_value = _extract_distance_value(text, expect_distance=expected_field == "distance_km")
        if distance_value is not None:
            details.distance_km = distance_value
            if expected_field == "distance_km":
                expected_field = None
        elif expected_field == "distance_km" and DONT_KNOW_DISTANCE_PATTERN.search(text) and details.from_city and details.to_city:
            looked_up = _lookup_distance(details.from_city, details.to_city)
            if looked_up:
                details.distance_km = float(looked_up)
                expected_field = None

        date_match = MOVE_DATE_PATTERN.search(text)
        if date_match:
            details.move_date = date_match.group(1)

        floor_from_match = FLOOR_FROM_PATTERN.search(text)
        if floor_from_match:
            details.floor_from = int(floor_from_match.group(1))
        floor_to_match = FLOOR_TO_PATTERN.search(text)
        if floor_to_match:
            details.floor_to = int(floor_to_match.group(1))

        if ELEVATOR_FROM_TRUE_PATTERN.search(text):
            details.elevator_from = True
        elif ELEVATOR_FROM_FALSE_PATTERN.search(text):
            details.elevator_from = False
        if ELEVATOR_TO_TRUE_PATTERN.search(text):
            details.elevator_to = True
        elif ELEVATOR_TO_FALSE_PATTERN.search(text):
            details.elevator_to = False

    return details


def _has_estimate_intent(messages: Sequence[ChatTurn], lang: ChatLanguage) -> bool:
    user_messages = [" ".join(message.content.lower().split()) for message in messages if message.role == "user"]
    user_text = " ".join(user_messages)
    if any(keyword in user_text for keyword in _lang_config(lang)["estimate_keywords"]):
        return True
    has_route_pattern = any(CITY_PATTERN.search(text) for text in user_messages)
    has_rooms = any(ROOMS_PATTERN.search(text) for text in user_messages)
    has_distance = any(DISTANCE_PATTERN.search(text) for text in user_messages)
    move_markers = _lang_config(lang)["move_markers"]
    mentions_move = any(any(marker in text for marker in move_markers) for text in user_messages)
    has_city_like_answer = any(_is_city_like_answer(text) for text in user_messages)
    return has_route_pattern or (mentions_move and (has_rooms or has_distance)) or (has_city_like_answer and (has_rooms or has_distance))


def _is_single_item_transport_request(messages: Sequence[ChatTurn], lang: ChatLanguage) -> bool:
    user_messages = [" ".join(message.content.lower().split()) for message in messages if message.role == "user"]
    if not user_messages:
        return False
    text = " ".join(user_messages)
    config = _lang_config(lang)
    has_transport = any(keyword in text for keyword in config["single_transport_keywords"])
    has_item = any(item in text for item in config["single_transport_items"])
    has_no_move = any(marker in text for marker in config["single_transport_no_move_markers"])
    has_route = any(CITY_PATTERN.search(msg) for msg in user_messages)
    return (has_transport and has_item and has_route) or (has_item and has_no_move and has_route)


def _is_single_item_transport_context(messages: Sequence[ChatTurn], lang: ChatLanguage) -> bool:
    last_user_text = _last_user_message(messages)
    last_assistant_text = _last_assistant_message(messages)
    if not last_user_text or not last_assistant_text:
        return False

    normalized_user = " ".join(last_user_text.lower().split())
    has_route_now = bool(CITY_PATTERN.search(normalized_user))
    if not has_route_now:
        return False

    normalized_assistant = " ".join(last_assistant_text.lower().split())
    config = _lang_config(lang)
    mentioned_item_before = any(item in normalized_assistant for item in config["single_transport_items"])
    mentioned_single_transport_before = any(
        marker in normalized_assistant
        for marker in ("einzeltransport", "single-item transport", "single item transport", "nur transport", "only transport")
    )
    return mentioned_item_before or mentioned_single_transport_before


def _build_follow_up_question(move_details: MoveDetails, last_assistant_text: str | None, lang: ChatLanguage) -> str | None:
    if not move_details.from_city:
        key = "from_city"
    elif not move_details.to_city:
        key = "to_city"
    elif move_details.rooms is None:
        key = "rooms"
    elif move_details.distance_km is None:
        key = "distance_km"
    else:
        return None

    config = _lang_config(lang)
    question = _choose_variant(config[key], last_assistant_text)
    intro = _choose_variant(config["intros"], last_assistant_text)

    if key == "distance_km" and move_details.from_city and move_details.to_city:
        known_km = _lookup_distance(move_details.from_city, move_details.to_city)
        if known_km:
            hint = config["distance_hint"].format(from_city=move_details.from_city, to_city=move_details.to_city, km=known_km)
            return f"{intro} {question} ({hint})"

    return f"{intro} {question}"


def _build_estimate_reply(move_details: MoveDetails, estimate_result, lang: ChatLanguage) -> str:
    config = _lang_config(lang)
    move_date_note = ""
    if move_details.move_date:
        move_date_note = config["move_date_note"].format(date=move_details.move_date)

    same_city_note = ""
    if move_details.from_city and move_details.to_city and _normalize_for_compare(move_details.from_city) == _normalize_for_compare(move_details.to_city):
        same_city_note = config["same_city_note"]

    if estimate_result.price_min == estimate_result.price_max:
        price_text = config["estimate_single"].format(price=estimate_result.price_min)
    else:
        price_text = config["estimate_range"].format(price_min=estimate_result.price_min, price_max=estimate_result.price_max)

    explanation = estimate_result.explanation
    if lang == "en":
        explanation = "The non-binding estimate was generated with the existing backend pricing logic based on distance, number of rooms and the move details provided so far."

    return config["estimate_reply"].format(
        from_city=move_details.from_city,
        to_city=move_details.to_city,
        price_text=price_text,
        explanation=explanation,
        same_city_note=same_city_note,
        move_date_note=move_date_note,
    )


def _build_transcript(messages: Sequence[ChatTurn], lang: ChatLanguage) -> str:
    transcript_lines: list[str] = []
    customer_label = _lang_config(lang)["customer_label"]
    for message in messages[-DODE_MAX_MESSAGES:]:
        role_name = customer_label if message.role == "user" else "Dode"
        content = " ".join(message.content.split())
        if len(content) > 1200:
            content = content[:1200].rstrip() + "..."
        transcript_lines.append(f"{role_name}: {content}")
    return "\n".join(transcript_lines)


def _build_faq_reply(
    messages: Sequence[ChatTurn],
    lang: ChatLanguage,
    logger: logging.Logger | None = None,
    request_id: str | None = None,
    conversation_id: str | None = None,
) -> str | None:
    last_user_text = _last_user_message(messages)
    if not last_user_text:
        return None
    faq_match = find_best_faq_match(last_user_text, lang=lang)
    if not faq_match:
        return None
    log_chat_event(
        logger,
        "chat_processing_path",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=lang,
        path="faq",
        faq_file=get_faq_filename(lang),
        faq_id=faq_match["item"].get("id"),
        faq_score=faq_match.get("score"),
        success=True,
    )
    item = faq_match["item"]
    answer = _localize_text_links((item.get("answer") or "").strip(), lang)
    source_page = _localize_page_path((item.get("source_page") or "").strip(), lang)
    if not answer:
        return None
    if source_page and source_page not in answer:
        suffix = _lang_config(lang)["faq_suffix"].format(source_page=source_page)
        return f"{answer} {suffix}"
    return answer


def _generate_general_reply(
    messages: Sequence[ChatTurn],
    page: str | None,
    lang: ChatLanguage,
    logger: logging.Logger | None,
    request_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    faq_reply = _build_faq_reply(messages, lang, logger, request_id, conversation_id)
    if faq_reply:
        return faq_reply

    log_chat_event(
        logger,
        "chat_processing_path",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=lang,
        path="general_chat",
        faq_file=get_faq_filename(lang),
        success=True,
    )
    client = get_dode_client()
    transcript = _build_transcript(messages, lang)
    try:
        response = client.responses.create(
            model=DODE_MODEL,
            instructions=build_dode_system_prompt(page, lang),
            input=build_general_chat_prompt(transcript, lang),
            max_output_tokens=DODE_MAX_OUTPUT_TOKENS,
            store=False,
        )
        reply = (getattr(response, "output_text", "") or "").strip()
        if not reply:
            raise ValueError("empty response from Dode")
        return _localize_text_links(reply, lang)
    except HTTPException:
        raise
    except Exception as exc:
        log_chat_exception(
            logger,
            "chat_processing_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            path="general_chat",
            error_type=type(exc).__name__,
            success=False,
        )
        raise HTTPException(status_code=502, detail=_lang_config(lang)["dode_unavailable"]) from exc


def _handle_new_service_inquiry(
    messages: Sequence[ChatTurn],
    page: str | None,
    lang: ChatLanguage,
    logger: logging.Logger | None = None,
    request_id: str | None = None,
    conversation_id: str | None = None,
) -> str | None:
    """Handle new service types (Entsorgung, Laminat, etc.) using the new pricing architecture."""
    try:
        last_user_text = _last_user_message(messages)
        if not last_user_text:
            return None
        
        pricing_tool = get_pricing_tool()
        classified = pricing_tool.classify_user_message(last_user_text)
        
        # Only handle if a specific service is detected (not umzug or generic)
        if not classified.service_type or classified.service_type == "umzug":
            return None
        
        # Check if this looks like a pricing inquiry
        if classified.intent_type not in ("PRICING_INQUIRY", "SERVICE_DETAILS"):
            return None
        
        # Log the new service path
        log_chat_event(
            logger,
            "chat_processing_path",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            path=f"new_service_{classified.service_type}",
            service_type=classified.service_type,
            intent=classified.intent_type,
            success=True,
        )
        
        # Use the new system prompt for this service type
        client = get_dode_client()
        transcript = _build_transcript(messages, lang)
        
        response = client.responses.create(
            model=DODE_MODEL,
            instructions=build_dode_system_prompt_v2(page, classified.service_type, lang),
            input=build_general_chat_prompt(transcript, lang),
            max_output_tokens=DODE_MAX_OUTPUT_TOKENS,
            store=False,
        )
        
        reply = (getattr(response, "output_text", "") or "").strip()
        if not reply:
            raise ValueError("empty response from new service handler")
        
        return _localize_text_links(reply, lang)
        
    except HTTPException:
        raise
    except Exception as exc:
        # If new service handler fails, return None to fall back to general flow
        log_chat_exception(
            logger,
            "new_service_processing_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            error_type=type(exc).__name__,
            success=False,
        )
        return None


def generate_dode_reply(
    *,
    messages: Sequence[Any],
    page: str | None,
    lang: ChatLanguage = "de",
    session_factory: Callable[[], Any],
    assigned_price_calculator: Callable[..., int],
    logger: logging.Logger | None = None,
    request_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    chat_turns = [_as_chat_turn(message) for message in messages]
    if not chat_turns:
        raise HTTPException(status_code=422, detail="messages are required")

    estimate_reply_idx = _last_estimate_reply_index(chat_turns)
    previous_details = MoveDetails()
    if estimate_reply_idx >= 0:
        previous_details = _extract_move_details(chat_turns[: estimate_reply_idx + 1], lang)

    active_turns = chat_turns
    if estimate_reply_idx >= 0 and estimate_reply_idx < len(chat_turns) - 1:
        active_turns = chat_turns[estimate_reply_idx + 1 :]

    move_details = _extract_move_details(active_turns, lang)
    
    # Try new service handler first (Entsorgung, Laminat, Möbelmontage, Einzeltransport, etc.)
    new_service_reply = _handle_new_service_inquiry(
        active_turns, page, lang, logger, request_id, conversation_id
    )
    if new_service_reply:
        return new_service_reply
    
    if _is_single_item_transport_request(active_turns, lang) or _is_single_item_transport_context(active_turns, lang):
        log_chat_event(
            logger,
            "chat_processing_path",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            path="single_item_transport",
            success=True,
        )
        return _lang_config(lang)["single_transport_reply"]

    if _has_estimate_intent(active_turns, lang):
        active_user_message_count = sum(1 for message in active_turns if message.role == "user")
        if active_user_message_count == 1:
            log_chat_event(
                logger,
                "chat_conversion",
                request_id=request_id,
                conversation_id=conversation_id,
                lang=lang,
                page=page or "-",
                conversion_step="entered_price_flow",
                success=True,
            )
        if _is_general_topic_switch(active_turns, lang):
            return _generate_general_reply(active_turns, page, lang, logger, request_id, conversation_id)

        sanity_clarification = _build_sanity_clarification(active_turns, move_details, lang)
        if sanity_clarification:
            log_chat_event(
                logger,
                "chat_processing_path",
                request_id=request_id,
                conversation_id=conversation_id,
                lang=lang,
                path="sanity_clarification",
                success=True,
            )
            return sanity_clarification

        if _is_reuse_estimate_request(active_turns, lang):
            move_details = _merge_missing_move_details(move_details, previous_details)

        follow_up_question = _build_follow_up_question(move_details, _last_assistant_message(active_turns), lang)
        if follow_up_question:
            log_chat_event(
                logger,
                "chat_processing_path",
                request_id=request_id,
                conversation_id=conversation_id,
                lang=lang,
                path="follow_up",
                success=True,
            )
            return follow_up_question

        estimate_result = calculate_move_price(
            move_details,
            session_factory=session_factory,
            assigned_price_calculator=assigned_price_calculator,
            logger=logger,
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
        )
        log_chat_event(
            logger,
            "chat_processing_path",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=lang,
            path="price_estimate",
            success=True,
        )
        return _build_estimate_reply(move_details, estimate_result, lang)

    return _generate_general_reply(active_turns, page, lang, logger, request_id, conversation_id)
