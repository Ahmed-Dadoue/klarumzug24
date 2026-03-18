import logging
import os
import re
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import HTTPException

from .prompts import build_dode_system_prompt, build_general_chat_prompt
from .schemas import ChatTurn, MoveDetails
from .tools import calculate_move_price

DODE_MODEL = os.getenv("DODE_MODEL", "gpt-4.1-mini").strip()
DODE_MAX_MESSAGES = int(os.getenv("DODE_MAX_MESSAGES", "12"))
DODE_MAX_OUTPUT_TOKENS = int(os.getenv("DODE_MAX_OUTPUT_TOKENS", "220"))
NON_CITY_WORDS = {
    "hallo",
    "hi",
    "hey",
    "ja",
    "nein",
    "ok",
    "okay",
    "preis",
    "kosten",
    "angebot",
    "umzug",
    "schaetzung",
    "schätzung",
}

CITY_PATTERN = re.compile(
    r"(?:von|aus)\s+([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß .-]{1,80}?)\s+(?:nach|in)\s+([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß .-]{1,80})(?:[,.!?]|$)",
    re.IGNORECASE,
)
CITY_ONLY_PATTERN = re.compile(
    r"^[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß .-]{1,80}$"
)
ROOMS_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:zimmer|raeume|räume)",
    re.IGNORECASE,
)
DISTANCE_PATTERN = re.compile(
    r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:km|kilometer)",
    re.IGNORECASE,
)
MOVE_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\b"
)
FLOOR_FROM_PATTERN = re.compile(
    r"(?:auszug|von|aus)\D{0,20}(\d{1,2})\s*\.?\s*(?:stock|stockwerk|og)",
    re.IGNORECASE,
)
FLOOR_TO_PATTERN = re.compile(
    r"(?:einzug|nach|in|ins)\D{0,20}(\d{1,2})\s*\.?\s*(?:stock|stockwerk|og)",
    re.IGNORECASE,
)
ELEVATOR_FROM_TRUE_PATTERN = re.compile(
    r"(?:auszug|start|von)\D{0,20}(?:mit|vorhanden).{0,10}aufzug",
    re.IGNORECASE,
)
ELEVATOR_FROM_FALSE_PATTERN = re.compile(
    r"(?:auszug|start|von)\D{0,20}(?:ohne|kein(?:en|em)?)\D{0,10}aufzug",
    re.IGNORECASE,
)
ELEVATOR_TO_TRUE_PATTERN = re.compile(
    r"(?:einzug|ziel|nach)\D{0,20}(?:mit|vorhanden).{0,10}aufzug",
    re.IGNORECASE,
)
ELEVATOR_TO_FALSE_PATTERN = re.compile(
    r"(?:einzug|ziel|nach)\D{0,20}(?:ohne|kein(?:en|em)?)\D{0,10}aufzug",
    re.IGNORECASE,
)
STANDALONE_NUMBER_PATTERN = re.compile(r"\b(\d{1,4}(?:[.,]\d{1,2})?)\b")
ROOM_HINT_PATTERN = re.compile(r"\b(?:zimmer|raum|raeume|räume)\b", re.IGNORECASE)
DISTANCE_HINT_PATTERN = re.compile(
    r"\b(?:km|kilometer|strecke|distanz|entfernung)\b",
    re.IGNORECASE,
)
ESTIMATE_REPLY_PATTERN = re.compile(
    r"unverbindlich\w*\s+schaetz\w+.*\b(?:eur|euro)\b",
    re.IGNORECASE,
)

NUMBER_WORDS = {
    "null": 0,
    "ein": 1,
    "eins": 1,
    "eine": 1,
    "einen": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fuenf": 5,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwoelf": 12,
    "zwölf": 12,
    "dreizehn": 13,
    "vierzehn": 14,
    "fuenfzehn": 15,
    "fünfzehn": 15,
    "sechzehn": 16,
    "siebzehn": 17,
    "achtzehn": 18,
    "neunzehn": 19,
    "zwanzig": 20,
}

FOLLOW_UP_VARIANTS = {
    "from_city": [
        "Aus welcher Stadt ziehen Sie um?",
        "Von welcher Stadt aus startet Ihr Umzug?",
    ],
    "to_city": [
        "In welche Stadt ziehen Sie um?",
        "In welche Zielstadt soll es gehen?",
    ],
    "rooms": [
        "Wie viele Zimmer sind es ungefaehr?",
        "Wie viele Zimmer hat die Wohnung etwa?",
    ],
    "distance_km": [
        "Wie viele Kilometer liegen ungefaehr zwischen Start und Ziel?",
        "Wie gross ist die Strecke ungefaehr in Kilometern?",
    ],
}

FOLLOW_UP_INTROS = [
    "Gern helfe ich Ihnen mit einer unverbindlichen Schaetzung.",
    "Danke, dann machen wir direkt mit der unverbindlichen Schaetzung weiter.",
    "Alles klar, fuer die unverbindliche Schaetzung brauche ich noch kurz diese Angabe.",
]

REUSE_ESTIMATE_KEYWORDS = (
    "nochmal",
    "noch mal",
    "wieder",
    "erneut",
    "gleich",
    "gleiche",
    "noch eine",
    "noch einen",
)


def get_dode_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Dode AI ist noch nicht konfiguriert.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenAI client library is not installed.",
        ) from exc

    return OpenAI(api_key=api_key)


def _as_chat_turn(message: Any) -> ChatTurn:
    if isinstance(message, ChatTurn):
        return message
    if hasattr(message, "model_dump"):
        return ChatTurn.model_validate(message.model_dump())
    if isinstance(message, dict):
        return ChatTurn.model_validate(message)
    return ChatTurn.model_validate(
        {
            "role": getattr(message, "role"),
            "content": getattr(message, "content"),
        }
    )


def _normalize_city(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" ,.;:!?")
    if not cleaned:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def _is_city_like_answer(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or not CITY_ONLY_PATTERN.fullmatch(cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in NON_CITY_WORDS:
        return False
    return len(cleaned.split()) <= 4


def _normalize_for_compare(value: str) -> str:
    return " ".join(value.lower().split())


def _extract_number_from_text(text: str) -> float | None:
    direct_match = STANDALONE_NUMBER_PATTERN.search(text)
    if direct_match:
        return float(direct_match.group(1).replace(",", "."))

    for token in re.findall(r"[A-Za-zÄÖÜäöüß]+", text.lower()):
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


def _infer_expected_field_from_assistant(text: str) -> str | None:
    lowered = " ".join(text.lower().split())
    if "meinten sie wirklich" in lowered and "zimmer" in lowered:
        return "rooms"
    if "aus welcher stadt" in lowered or "von welcher stadt" in lowered:
        return "from_city"
    if "in welche stadt" in lowered or "zielstadt" in lowered:
        return "to_city"
    if "wie viele zimmer" in lowered:
        return "rooms"
    if "wie viele kilometer" in lowered or "strecke" in lowered:
        return "distance_km"
    return None


def _is_estimate_reply(text: str) -> bool:
    normalized = " ".join(text.split())
    return bool(ESTIMATE_REPLY_PATTERN.search(normalized))


def _last_estimate_reply_index(messages: Sequence[ChatTurn]) -> int:
    for idx in range(len(messages) - 1, -1, -1):
        message = messages[idx]
        if message.role == "assistant" and _is_estimate_reply(message.content):
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


def _is_reuse_estimate_request(messages: Sequence[ChatTurn]) -> bool:
    user_messages = [
        " ".join(message.content.lower().split())
        for message in messages
        if message.role == "user"
    ]
    if not user_messages:
        return False

    user_text = " ".join(user_messages)
    if "preis" not in user_text and "kosten" not in user_text and "schaetzung" not in user_text and "schätzung" not in user_text:
        return False

    return any(keyword in user_text for keyword in REUSE_ESTIMATE_KEYWORDS)


def _is_general_topic_switch(messages: Sequence[ChatTurn]) -> bool:
    last_user_text = _last_user_message(messages)
    if not last_user_text:
        return False

    lowered = " ".join(last_user_text.lower().split())
    estimate_keywords = (
        "preis",
        "kosten",
        "schaetzung",
        "schätzung",
        "umzug",
        "umziehen",
        "zimmer",
        "kilometer",
        "km",
    )
    if any(keyword in lowered for keyword in estimate_keywords):
        return False

    general_keywords = (
        "kontakt",
        "erreichen",
        "telefon",
        "anrufen",
        "email",
        "e-mail",
        "whatsapp",
        "adresse",
        "oeffnungszeiten",
        "öffnungszeiten",
    )
    return any(keyword in lowered for keyword in general_keywords)


def _merge_missing_move_details(current: MoveDetails, previous: MoveDetails) -> MoveDetails:
    merged_data = current.model_dump()
    previous_data = previous.model_dump()

    for key, value in previous_data.items():
        if merged_data.get(key) is None and value is not None:
            merged_data[key] = value

    return MoveDetails.model_validate(merged_data)


def _build_sanity_clarification(
    messages: Sequence[ChatTurn],
    move_details: MoveDetails,
) -> str | None:
    expected_field = _infer_expected_field_from_assistant(_last_assistant_message(messages) or "")
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
        return (
            f"Meinten Sie wirklich {rounded_value} Zimmer oder eher die Entfernung in Kilometern?"
        )

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


def _extract_move_details(messages: Sequence[ChatTurn]) -> MoveDetails:
    details = MoveDetails()
    expected_field: str | None = None

    for message in messages:
        if message.role == "assistant":
            expected_field = _infer_expected_field_from_assistant(message.content)
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

        distance_value = _extract_distance_value(
            text,
            expect_distance=expected_field == "distance_km",
        )
        if distance_value is not None:
            details.distance_km = distance_value
            if expected_field == "distance_km":
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


def _has_estimate_intent(messages: Sequence[ChatTurn]) -> bool:
    user_messages = [
        " ".join(message.content.lower().split())
        for message in messages
        if message.role == "user"
    ]
    user_text = " ".join(user_messages)
    keywords = (
        "preis",
        "kosten",
        "schaetzung",
        "schätzung",
        "angebot",
        "umzug",
        "umziehen",
        "umzugs",
    )
    if any(keyword in user_text for keyword in keywords):
        return True

    has_route_pattern = any(CITY_PATTERN.search(text) for text in user_messages)
    has_rooms = any(ROOMS_PATTERN.search(text) for text in user_messages)
    has_distance = any(DISTANCE_PATTERN.search(text) for text in user_messages)
    mentions_move = any("umzug" in text or "ich ziehe" in text for text in user_messages)
    has_city_like_answer = any(_is_city_like_answer(text) for text in user_messages)

    if has_route_pattern:
        return True
    if mentions_move and (has_rooms or has_distance):
        return True
    if has_city_like_answer and (has_rooms or has_distance):
        return True

    return False
def _build_follow_up_question(
    move_details: MoveDetails,
    last_assistant_text: str | None,
) -> str | None:
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

    question = _choose_variant(FOLLOW_UP_VARIANTS[key], last_assistant_text)
    intro = _choose_variant(FOLLOW_UP_INTROS, last_assistant_text)
    return f"{intro} {question}"


def _build_estimate_reply(move_details: MoveDetails, estimate_result) -> str:
    move_date_note = ""
    if move_details.move_date:
        move_date_note = f" Fuer den Termin {move_details.move_date} kann die Planung spaeter noch konkretisiert werden."

    same_city_note = ""
    if (
        move_details.from_city
        and move_details.to_city
        and _normalize_for_compare(move_details.from_city) == _normalize_for_compare(move_details.to_city)
    ):
        same_city_note = " Hinweis: Start- und Zielort sind identisch. Bitte pruefen Sie die Eingabe der Strecke."

    if estimate_result.price_min == estimate_result.price_max:
        price_text = f"ca. {estimate_result.price_min} EUR"
    else:
        price_text = f"ca. {estimate_result.price_min} bis {estimate_result.price_max} EUR"

    return (
        f"Fuer Ihren Umzug von {move_details.from_city} nach {move_details.to_city} "
        f"liegt die unverbindliche Schaetzung aktuell bei {price_text}. "
        f"{estimate_result.explanation} "
        f"Das ist kein verbindliches Festpreisangebot.{same_city_note}{move_date_note}"
    )


def _build_transcript(messages: Sequence[ChatTurn]) -> str:
    transcript_lines: list[str] = []
    for message in messages[-DODE_MAX_MESSAGES:]:
        role_name = "Kunde" if message.role == "user" else "Dode"
        content = " ".join(message.content.split())
        if len(content) > 1200:
            content = content[:1200].rstrip() + "..."
        transcript_lines.append(f"{role_name}: {content}")
    return "\n".join(transcript_lines)


def _generate_general_reply(
    messages: Sequence[ChatTurn],
    page: str | None,
    logger: logging.Logger | None,
) -> str:
    client = get_dode_client()
    transcript = _build_transcript(messages)

    try:
        response = client.responses.create(
            model=DODE_MODEL,
            instructions=build_dode_system_prompt(page),
            input=build_general_chat_prompt(transcript),
            max_output_tokens=DODE_MAX_OUTPUT_TOKENS,
            store=False,
        )
        reply = (getattr(response, "output_text", "") or "").strip()
        if not reply:
            raise ValueError("empty response from Dode")
        return reply
    except HTTPException:
        raise
    except Exception as exc:
        if logger:
            logger.exception("Dode AI request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Dode ist gerade nicht erreichbar.",
        ) from exc


def generate_dode_reply(
    *,
    messages: Sequence[Any],
    page: str | None,
    session_factory: Callable[[], Any],
    assigned_price_calculator: Callable[..., int],
    logger: logging.Logger | None = None,
) -> str:
    chat_turns = [_as_chat_turn(message) for message in messages]
    if not chat_turns:
        raise HTTPException(status_code=422, detail="messages are required")

    estimate_reply_idx = _last_estimate_reply_index(chat_turns)
    previous_details = MoveDetails()
    if estimate_reply_idx >= 0:
        previous_details = _extract_move_details(chat_turns[: estimate_reply_idx + 1])

    active_turns = chat_turns
    if estimate_reply_idx >= 0 and estimate_reply_idx < len(chat_turns) - 1:
        # Start a fresh estimate flow after a completed estimate response.
        active_turns = chat_turns[estimate_reply_idx + 1 :]

    move_details = _extract_move_details(active_turns)
    if _has_estimate_intent(active_turns):
        if _is_general_topic_switch(active_turns):
            return _generate_general_reply(active_turns, page, logger)

        sanity_clarification = _build_sanity_clarification(active_turns, move_details)
        if sanity_clarification:
            return sanity_clarification

        if _is_reuse_estimate_request(active_turns):
            move_details = _merge_missing_move_details(move_details, previous_details)

        follow_up_question = _build_follow_up_question(
            move_details,
            _last_assistant_message(active_turns),
        )
        if follow_up_question:
            return follow_up_question

        estimate_result = calculate_move_price(
            move_details,
            session_factory=session_factory,
            assigned_price_calculator=assigned_price_calculator,
        )
        return _build_estimate_reply(move_details, estimate_result)

    return _generate_general_reply(active_turns, page, logger)
