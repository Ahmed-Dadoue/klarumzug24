"""Company-specific pricing brain for Klarumzug24 v2 estimates."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from math import ceil
from typing import Any, Literal

from .schemas import ChatLanguage, ChatTurn


PricingV2ServiceType = Literal[
    "umzug",
    "transporthilfe",
    "einzeltransport",
    "entsorgung",
    "entruempelung",
    "haushaltsaufloesung",
    "wohnungsaufloesung",
    "kuechenmontage",
    "arbeitsplatte_only",
    "moebelmontage",
]

DifficultyLevel = Literal["simple", "medium", "hard"]


@dataclass(frozen=True)
class CompanyPricingProfile:
    monthly_target_gross_eur: int = 7000
    working_days_per_month: int = 18
    owner_hourly_rate_eur: int = 45
    helper_hourly_rate_eur: int = 35
    minimum_order_solo_eur: int = 150
    minimum_order_with_transporter_eur: int = 250
    included_hours_in_minimum: float = 3.0
    km_rate_from_bordesholm_one_way_eur: float = 0.60
    base_location: str = "Bordesholm"
    vehicle: str = "Mercedes Sprinter"
    coverage_area: str = "Schleswig-Holstein"
    kitchen_meter_rate_eur: int = 160
    sink_cutout_eur: int = 80
    cooktop_cutout_eur: int = 60
    weekend_surcharge_eur: int = 0
    express_surcharge_eur: int = 0
    request_images_in_chat: bool = False

    @property
    def daily_target_eur(self) -> int:
        return int(round(self.monthly_target_gross_eur / self.working_days_per_month))


DEFAULT_COMPANY_PRICING_PROFILE = CompanyPricingProfile()


@dataclass(frozen=True)
class PricingV2Input:
    service_type: PricingV2ServiceType
    distance_km: float | None = None
    estimated_hours_min: float | None = None
    estimated_hours_max: float | None = None
    workers_total: int | None = None
    needs_transporter: bool | None = None
    kitchen_meters: float | None = None
    sink_cutout: bool = False
    cooktop_cutout: bool = False
    difficulty: DifficultyLevel | None = None
    rooms: int | None = None
    cartons: int | None = None
    furniture_items: int | None = None
    kitchen_count: int | None = None
    heavy_items: int | None = None
    floor_from: int | None = None
    floor_to: int | None = None
    elevator_from: bool | None = None
    elevator_to: bool | None = None
    description: str | None = None


@dataclass(frozen=True)
class PricingV2Result:
    service_type: PricingV2ServiceType
    pricing_model: str
    price_min_eur: int | None
    price_max_eur: int | None
    workers_total: int
    helpers_count: int
    needs_transporter: bool
    estimated_hours_min: float | None
    estimated_hours_max: float | None
    distance_km: float | None
    missing_fields: tuple[str, ...]
    explanation_de: str
    internal_notes: tuple[str, ...]
    profile: dict[str, Any]

    @property
    def can_quote(self) -> bool:
        return self.price_min_eur is not None and self.price_max_eur is not None and not self.missing_fields


DISTANCE_PATTERN = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:km|kilometer)\b", re.IGNORECASE)
HOURS_PATTERN = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:h|std|stunde|stunden)\b", re.IGNORECASE)
METER_PATTERN = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:m|meter|laufmeter)\b", re.IGNORECASE)
ROOMS_PATTERN = re.compile(r"(\d{1,2})\s*(?:zimmern?|raeume|räume|room|rooms)\b", re.IGNORECASE)
CARTONS_PATTERN = re.compile(r"(\d{1,4})\s*(?:karton|kartons|kisten)\b", re.IGNORECASE)
CARTONS_LABEL_PATTERN = re.compile(r"(?:karton|kartons|kisten)\s*:\s*(?:ca\.?\s*)?(\d{1,4})\b", re.IGNORECASE)
WORKERS_PATTERN = re.compile(r"(\d{1,2})\s*(?:mann|maenner|männer|arbeiter|mitarbeiter|helfer|personen)\b", re.IGNORECASE)
FLOOR_PATTERN = re.compile(r"(\d{1,2})\s*\.?\s*(?:stock|stockwerk|og|etage)\b", re.IGNORECASE)
FURNITURE_ITEMS_PATTERN = re.compile(
    r"(\d{1,4})\s*(?:schreibtische|schreibtisch|schreib\s*tische|tische|moebelstuecke|moebel)",
    re.IGNORECASE,
)
KITCHEN_COUNT_PATTERN = re.compile(r"(\d{1,2})\s*(?:kuechen|kueche)\b", re.IGNORECASE)
FLOOR_WORDS = {
    "erste": 1,
    "ersten": 1,
    "zweite": 2,
    "zweiten": 2,
    "dritte": 3,
    "dritten": 3,
    "vierte": 4,
    "vierten": 4,
    "fuenfte": 5,
    "fuenften": 5,
    "sechste": 6,
    "sechsten": 6,
}

NUMBER_WORDS = {
    "ein": 1,
    "eine": 1,
    "einen": 1,
    "einem": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fuenf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
}

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "bordesholm": (
        "bordesholm",
        "bordes",
        "24582",
        "24583",
        "luettparten",
        "luettbarten",
        "luetbarten",
        "luttparten",
        "luttbarten",
    ),
    "kiel": ("kiel", "kie", "gaarden", "holtenauer strasse"),
    "stuttgart": ("stuttgart", "stutgart"),
    "hamburg": ("hamburg",),
    "berlin": ("berlin",),
}

CITY_DISTANCE_FROM_BORDESHOLM_KM: dict[str, float] = {
    "bordesholm": 0.0,
    "kiel": 30.0,
    "hamburg": 95.0,
    "berlin": 350.0,
    "stuttgart": 735.0,
}

ROUTE_DISTANCE_KM: dict[tuple[str, str], float] = {
    ("bordesholm", "kiel"): 30.0,
    ("kiel", "hamburg"): 95.0,
    ("kiel", "berlin"): 355.0,
    ("kiel", "stuttgart"): 735.0,
    ("bordesholm", "stuttgart"): 735.0,
}

CLEARANCE_SERVICE_TYPES = {
    "entsorgung",
    "entruempelung",
    "haushaltsaufloesung",
    "wohnungsaufloesung",
}


def _normalize(value: str) -> str:
    text = " ".join((value or "").lower().split())
    replacements = {
        "\u00e4": "ae",
        "\u00f6": "oe",
        "\u00fc": "ue",
        "\u00df": "ss",
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ã¤": "ae",
        "Ã¶": "oe",
        "Ã¼": "ue",
        "ÃŸ": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _round_up_to_10(value: float) -> int:
    return int(ceil(max(0.0, value) / 10.0) * 10)


def _safe_non_negative_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    safe_value = float(value)
    return safe_value if safe_value >= 0 else None


def _safe_non_negative_int(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, int(value))


def _extract_first_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _extract_first_int(pattern: re.Pattern[str], text: str) -> int | None:
    value = _extract_first_float(pattern, text)
    if value is None:
        return None
    return int(round(value))


def _extract_word_count_before(text_ascii: str, nouns: tuple[str, ...]) -> int | None:
    noun_pattern = "|".join(re.escape(noun) for noun in nouns)
    word_pattern = "|".join(re.escape(word) for word in NUMBER_WORDS)
    match = re.search(rf"\b(\d{{1,4}}|{word_pattern})\s+(?:{noun_pattern})\b", text_ascii)
    if not match:
        return None
    value = match.group(1)
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS.get(value)


def _extract_furniture_items(text_ascii: str) -> int | None:
    count = _extract_first_int(FURNITURE_ITEMS_PATTERN, text_ascii)
    if count is not None:
        return count
    return _extract_word_count_before(
        text_ascii,
        ("schreibtische", "schreibtisch", "schreib tische", "tische", "moebelstuecke", "moebel"),
    )


def _extract_kitchen_count(text_ascii: str) -> int | None:
    count = _extract_first_int(KITCHEN_COUNT_PATTERN, text_ascii)
    if count is not None:
        return count
    return _extract_word_count_before(text_ascii, ("kuechen", "kueche"))


def _city_mentions(text_ascii: str) -> list[tuple[int, str]]:
    mentions: list[tuple[int, str]] = []
    for city, aliases in CITY_ALIASES.items():
        for alias in aliases:
            for match in re.finditer(rf"\b{re.escape(alias)}\b", text_ascii):
                mentions.append((match.start(), city))
    return sorted(mentions, key=lambda item: item[0])


def _route_distance_from_cities(origin: str, destination: str) -> float | None:
    if origin == destination:
        return 0.0
    direct = ROUTE_DISTANCE_KM.get((origin, destination))
    if direct is not None:
        return direct
    return ROUTE_DISTANCE_KM.get((destination, origin))


def _has_explicit_route_signal(text_ascii: str) -> bool:
    return bool(re.search(r"\b(?:von|aus|ab)\s+.{2,120}\s+(?:nach|bis|zu)\b", text_ascii)) or (
        "start" in text_ascii and "ziel" in text_ascii
    )


def _extract_known_route_distance(text_ascii: str) -> float | None:
    mentions = _city_mentions(text_ascii)
    if len(mentions) < 2:
        return None

    best_match: tuple[int, str, str] | None = None
    for index, (origin_pos, origin_city) in enumerate(mentions):
        for destination_pos, destination_city in mentions[index + 1 :]:
            between = text_ascii[origin_pos:destination_pos]
            before = text_ascii[max(0, origin_pos - 35) : origin_pos]
            has_route_words = any(marker in between for marker in (" nach ", " bis ", " zu "))
            has_origin_words = any(marker in before for marker in ("von ", "aus ", "ab ", "start", "route"))
            has_start_target_words = "start" in before and "ziel" in between
            if (has_route_words and has_origin_words) or has_start_target_words:
                best_match = (destination_pos, origin_city, destination_city)

    if not best_match:
        return None
    _, origin_city, destination_city = best_match
    return _route_distance_from_cities(origin_city, destination_city)


def _detect_bool(text_ascii: str, positive: tuple[str, ...], negative: tuple[str, ...]) -> bool | None:
    if any(marker in text_ascii for marker in negative):
        return False
    if any(marker in text_ascii for marker in positive):
        return True
    return None


def _detect_service_type(text_ascii: str) -> PricingV2ServiceType | None:
    has_price_signal = any(
        token in text_ascii
        for token in ("preis", "kosten", "kostet", "angebot", "schaetzung", "schätzung", "eur", "euro")
    )
    has_worktop = any(
        token in text_ascii
        for token in ("arbeitsplatte", "kuechenplatte", "platte", "tischplatte", "ausschnitt", "spuele", "kochfeld")
    )
    has_route = _extract_known_route_distance(text_ascii) is not None or _has_explicit_route_signal(text_ascii)
    has_move_scope = any(
        token in text_ascii
        for token in ("zimmer", "karton", "kartons", "kisten", "transporter", "transport", "trasport")
    )
    if has_route and has_move_scope:
        return "umzug"

    has_large_furniture = bool(_extract_furniture_items(text_ascii)) and any(
        token in text_ascii for token in ("aufbau", "aufbauen", "montage", "montieren")
    )
    has_full_kitchen = any(
        token in text_ascii
        for token in (
            "kuechenmontage",
            "kueche komplett",
            "komplette kueche",
            "kuechen aufbau",
            "kuechenaufbau",
            "kueche montieren",
            "kueche aufbauen",
            "kueche aufgebaut",
            "kuechen montiert",
            "kueche montiert",
            "unterschrank",
            "oberschrank",
            "schraenke",
            "schrankelemente",
        )
    )
    if has_full_kitchen and has_large_furniture:
        return "moebelmontage"
    only_markers = ("nur arbeitsplatte", "nur platte", "platte only", "arbeitsplatte only", "nur tischplatte")
    if has_worktop and (any(marker in text_ascii for marker in only_markers) or not has_full_kitchen):
        return "arbeitsplatte_only"
    if has_full_kitchen:
        return "kuechenmontage"

    has_move = any(token in text_ascii for token in ("umzug", "umziehen", "ziehe um", "wohnung wechseln"))
    if has_move and has_move_scope:
        return "umzug"

    if any(token in text_ascii for token in ("haushaltsaufloesung", "hausaufloesung")):
        return "haushaltsaufloesung"
    if any(token in text_ascii for token in ("wohnungsaufloesung", "wohnung aufloesen")):
        return "wohnungsaufloesung"
    if any(
        token in text_ascii
        for token in (
            "entruempelung",
            "entruempeln",
            "entrumpelung",
            "entrumpeln",
            "raeumung",
            "kellerraeumung",
            "dachbodenraeumung",
            "garage raeumen",
            "keller raeumen",
            "dachboden raeumen",
            "betriebsaufloesung",
            "firmenaufloesung",
        )
    ):
        return "entruempelung"
    if any(
        token in text_ascii
        for token in ("entsorgung", "entsorgen", "sperrmuell", "muell", "wegwerfen", "wegschmeissen")
    ):
        return "entsorgung"

    if any(token in text_ascii for token in ("umzugshilfe", "nur hilfe", "nur tragen", "tragen helfen")):
        return "transporthilfe"
    if any(token in text_ascii for token in ("einzeltransport", "nur transport", "transportieren", "abholen", "lieferung")):
        return "einzeltransport"
    if has_move or ("ziehe" in text_ascii and " um" in text_ascii):
        return "umzug"
    if has_price_signal and any(
        token in text_ascii
        for token in ("moebel", "moebelmontage", "schrank", "regal", "bett", "schreibtisch", "aufbau", "aufbauen", "montage")
    ):
        return "moebelmontage"
    return None


def _detect_difficulty(text_ascii: str) -> DifficultyLevel | None:
    if any(token in text_ascii for token in ("schwer", "kompliziert", "komplex", "alt", "winkel", "ecke", "anpassen", "anpassung")):
        return "hard"
    if any(token in text_ascii for token in ("mittel", "normal", "ausschnitt", "spuele", "kochfeld")):
        return "medium"
    if any(token in text_ascii for token in ("einfach", "leicht", "klein", "nur montieren", "nur aufbauen")):
        return "simple"
    return None


def _default_hours_for_service(data: PricingV2Input) -> tuple[float | None, float | None]:
    if data.estimated_hours_min and data.estimated_hours_max:
        return data.estimated_hours_min, max(data.estimated_hours_min, data.estimated_hours_max)

    if data.service_type == "arbeitsplatte_only":
        if data.difficulty == "hard":
            return 5.0, 7.0
        if data.difficulty == "medium" or data.sink_cutout or data.cooktop_cutout:
            return 3.0, 5.0
        if data.difficulty == "simple":
            return 2.0, 3.0
        return None, None

    if data.service_type == "moebelmontage":
        furniture_items = _safe_non_negative_int(data.furniture_items)
        kitchen_count = _safe_non_negative_int(data.kitchen_count)
        if furniture_items or kitchen_count:
            workers = max(1, _default_workers_for_service(data))
            man_hours = furniture_items * 0.45 + kitchen_count * 10.0
            hours_min = max(3.0, 1.0 + (man_hours / workers) * 0.85)
            hours_max = max(hours_min + 1.0, 2.0 + (man_hours / workers) * 1.25)
            return round(hours_min, 2), round(hours_max, 2)
        if data.difficulty == "hard":
            return 4.0, 6.0
        if data.difficulty == "medium":
            return 3.0, 5.0
        if data.difficulty == "simple":
            return 2.0, 3.0
        return None, None

    if data.service_type in {"transporthilfe", "einzeltransport"}:
        if data.difficulty == "hard":
            return 4.0, 6.0
        if data.difficulty == "medium":
            return 3.0, 5.0
        if data.difficulty == "simple":
            return 2.0, 3.0
        return None, None

    if data.service_type in CLEARANCE_SERVICE_TYPES:
        rooms = _safe_non_negative_int(data.rooms)
        cartons = _safe_non_negative_int(data.cartons)
        heavy_items = _safe_non_negative_int(data.heavy_items)
        if not rooms and not cartons and not heavy_items and not data.difficulty:
            return None, None
        if data.difficulty == "hard":
            return 5.0, 8.0
        if data.difficulty == "medium":
            return 3.0, 5.5
        if data.difficulty == "simple" and not rooms and not cartons:
            return 2.0, 3.0

        if data.service_type == "entsorgung":
            hours = 1.5 + rooms * 0.8 + cartons * 0.04 + heavy_items * 0.5
        else:
            hours = 2.0 + rooms * 1.25 + cartons * 0.04 + heavy_items * 0.35
        floor_from = _safe_non_negative_int(data.floor_from)
        if floor_from and not data.elevator_from:
            hours += floor_from * 0.35
        if data.distance_km:
            hours += data.distance_km / 55.0
        return max(2.0, round(hours * 0.9, 2)), max(3.0, round(hours * 1.25, 2))

    if data.service_type == "umzug":
        rooms = _safe_non_negative_int(data.rooms)
        cartons = _safe_non_negative_int(data.cartons)
        heavy_items = _safe_non_negative_int(data.heavy_items)
        if not rooms and not cartons and not heavy_items:
            return None, None
        hours = 1.0 + rooms * 0.9 + cartons * 0.03 + heavy_items * 0.3
        floor_from = _safe_non_negative_int(data.floor_from)
        floor_to = _safe_non_negative_int(data.floor_to)
        if floor_from and not data.elevator_from:
            hours += floor_from * 0.35
        if floor_to and not data.elevator_to:
            hours += floor_to * 0.35
        if data.distance_km:
            hours += data.distance_km / 55.0
        return max(2.0, round(hours * 0.9, 2)), max(2.5, round(hours * 1.2, 2))

    return None, None


def _default_workers_for_service(data: PricingV2Input) -> int:
    if data.workers_total and data.workers_total > 0:
        return max(1, int(data.workers_total))

    rooms = _safe_non_negative_int(data.rooms)
    heavy_items = _safe_non_negative_int(data.heavy_items)
    if data.service_type == "umzug":
        if rooms >= 4 or heavy_items >= 5:
            return 3
        if rooms >= 2 or heavy_items >= 2:
            return 2
        return 1
    if data.service_type in {"entruempelung", "haushaltsaufloesung", "wohnungsaufloesung"}:
        if rooms >= 4 or heavy_items >= 4:
            return 3
        return 2 if rooms or heavy_items else 1
    if data.service_type == "entsorgung" and heavy_items:
        return 2 if heavy_items <= 2 else 3
    if data.service_type in {"einzeltransport", "transporthilfe"} and heavy_items:
        return 2 if heavy_items <= 2 else 3
    if data.service_type == "moebelmontage":
        furniture_items = _safe_non_negative_int(data.furniture_items)
        kitchen_count = _safe_non_negative_int(data.kitchen_count)
        if furniture_items >= 100 or kitchen_count >= 2:
            return 7
        if furniture_items >= 30:
            return 4
        if furniture_items >= 10 or kitchen_count:
            return 2
    return 1


def estimate_company_price_v2(
    data: PricingV2Input,
    *,
    profile: CompanyPricingProfile = DEFAULT_COMPANY_PRICING_PROFILE,
) -> PricingV2Result:
    distance_km = _safe_non_negative_float(data.distance_km)
    needs_transporter = bool(data.needs_transporter)
    if data.needs_transporter is None and data.service_type in {"umzug", "einzeltransport", *CLEARANCE_SERVICE_TYPES}:
        needs_transporter = True

    workers_total = _default_workers_for_service(data)
    helpers_count = max(0, workers_total - 1)
    missing_fields: list[str] = []
    internal_notes: list[str] = []

    if distance_km is None:
        missing_fields.append("ort_oder_entfernung_ab_bordesholm")

    price_min: int | None = None
    price_max: int | None = None
    hours_min: float | None = data.estimated_hours_min
    hours_max: float | None = data.estimated_hours_max
    pricing_model = "time_and_distance"

    if data.service_type == "kuechenmontage":
        pricing_model = "kitchen_meter_rate"
        if not data.kitchen_meters or data.kitchen_meters <= 0:
            missing_fields.append("laufmeter_kueche_oder_arbeitsplatte")
        else:
            base = data.kitchen_meters * profile.kitchen_meter_rate_eur
            extras = 0
            if data.sink_cutout:
                extras += profile.sink_cutout_eur
            if data.cooktop_cutout:
                extras += profile.cooktop_cutout_eur
            distance_cost = (distance_km or 0.0) * profile.km_rate_from_bordesholm_one_way_eur
            minimum = profile.minimum_order_with_transporter_eur if needs_transporter else profile.minimum_order_solo_eur
            raw_min = max(minimum, base + extras + distance_cost)
            raw_max = raw_min * 1.15
            price_min = _round_up_to_10(raw_min)
            price_max = _round_up_to_10(raw_max)
            internal_notes.append(f"Kuechenmontage mit {profile.kitchen_meter_rate_eur} EUR/m gerechnet.")
    else:
        hours_min, hours_max = _default_hours_for_service(data)
        if hours_min is None or hours_max is None:
            missing_fields.append("umfang_fuer_zeit_schaetzung")
        else:
            minimum = profile.minimum_order_with_transporter_eur if needs_transporter else profile.minimum_order_solo_eur
            distance_cost = (distance_km or 0.0) * profile.km_rate_from_bordesholm_one_way_eur
            extras = 0
            if data.sink_cutout:
                extras += profile.sink_cutout_eur
            if data.cooktop_cutout:
                extras += profile.cooktop_cutout_eur
            owner_extra_min = max(0.0, hours_min - profile.included_hours_in_minimum) * profile.owner_hourly_rate_eur
            owner_extra_max = max(0.0, hours_max - profile.included_hours_in_minimum) * profile.owner_hourly_rate_eur
            helper_min = helpers_count * profile.helper_hourly_rate_eur * hours_min
            helper_max = helpers_count * profile.helper_hourly_rate_eur * hours_max
            price_min = _round_up_to_10(minimum + owner_extra_min + helper_min + distance_cost + extras)
            price_max = _round_up_to_10(minimum + owner_extra_max + helper_max + distance_cost + extras)
            internal_notes.append(
                f"Mindestpreis {minimum} EUR deckt bis {profile.included_hours_in_minimum:g} Stunden ab."
            )
            if data.service_type in CLEARANCE_SERVICE_TYPES:
                internal_notes.append(
                    "Entsorgungs-/Deponiegebuehren koennen je nach Material zusaetzlich geprueft werden."
                )

    explanation = _build_explanation_de(
        service_type=data.service_type,
        pricing_model=pricing_model,
        price_min=price_min,
        price_max=price_max,
        workers_total=workers_total,
        needs_transporter=needs_transporter,
        hours_min=hours_min,
        hours_max=hours_max,
        distance_km=distance_km,
        missing_fields=missing_fields,
        profile=profile,
    )

    return PricingV2Result(
        service_type=data.service_type,
        pricing_model=pricing_model,
        price_min_eur=price_min,
        price_max_eur=price_max,
        workers_total=workers_total,
        helpers_count=helpers_count,
        needs_transporter=needs_transporter,
        estimated_hours_min=hours_min,
        estimated_hours_max=hours_max,
        distance_km=distance_km,
        missing_fields=tuple(dict.fromkeys(missing_fields)),
        explanation_de=explanation,
        internal_notes=tuple(internal_notes),
        profile=asdict(profile),
    )


def _build_explanation_de(
    *,
    service_type: PricingV2ServiceType,
    pricing_model: str,
    price_min: int | None,
    price_max: int | None,
    workers_total: int,
    needs_transporter: bool,
    hours_min: float | None,
    hours_max: float | None,
    distance_km: float | None,
    missing_fields: list[str],
    profile: CompanyPricingProfile,
) -> str:
    if missing_fields:
        return _build_follow_up_question_de(service_type, tuple(dict.fromkeys(missing_fields)))

    service_label = {
        "umzug": "Ihren Umzug",
        "transporthilfe": "die Umzugshilfe",
        "einzeltransport": "den Einzeltransport",
        "entsorgung": "die Entsorgung",
        "entruempelung": "die Entruempelung",
        "haushaltsaufloesung": "die Haushaltsaufloesung",
        "wohnungsaufloesung": "die Wohnungsaufloesung",
        "kuechenmontage": "die Kuechenmontage",
        "arbeitsplatte_only": "die Montage/Anpassung der Arbeitsplatte",
        "moebelmontage": "die Moebelmontage",
    }.get(service_type, "den Auftrag")

    if price_min is None or price_max is None:
        return _build_follow_up_question_de(service_type, tuple(missing_fields))

    if price_min == price_max:
        price_text = f"ca. {price_min} EUR"
    else:
        price_text = f"ca. {price_min} bis {price_max} EUR"

    vehicle_text = f" mit {profile.vehicle}" if needs_transporter else ""
    time_text = ""
    if hours_min is not None and hours_max is not None:
        time_text = f", voraussichtlich ca. {hours_min:g} bis {hours_max:g} Stunden"
    distance_text = ""
    if distance_km is not None:
        distance_text = f" und {distance_km:g} km einfache Strecke"
    model_text = "nach Laufmetern" if pricing_model == "kitchen_meter_rate" else "nach Zeit, Aufwand und Strecke"
    return (
        f"Fuer {service_label} liegt die unverbindliche Schaetzung bei {price_text}. "
        f"Gerechnet wurde {model_text} mit {workers_total} Person(en){vehicle_text}{time_text}{distance_text}. "
        "Der genaue Preis kann je nach tatsaechlichem Umfang, Zugang und Zusatzarbeiten abweichen."
    )


def _build_follow_up_question_de(service_type: PricingV2ServiceType, missing_fields: tuple[str, ...]) -> str:
    if service_type in {"umzug", "transporthilfe", "einzeltransport"}:
        return (
            "Damit ich den Auftrag sinnvoll einschaetzen kann, beschreiben Sie bitte kurz: "
            "Start/Ziel oder Entfernung ab Bordesholm, Etagen/Aufzug, ungefaehre Menge "
            "und ob ein Transporter gebraucht wird."
        )
    if service_type in CLEARANCE_SERVICE_TYPES:
        return (
            "Damit ich den Auftrag wie eine Transportfirma einschaetzen kann, nennen Sie bitte Ort/PLZ "
            "oder Entfernung ab Bordesholm, was genau raus muss, ungefaehre Menge/Raeume, Etage/Aufzug "
            "und ob Demontage oder nur Abholung/Entsorgung noetig ist."
        )
    if service_type == "kuechenmontage":
        return (
            "Damit ich die Kuechenmontage schaetzen kann, nennen Sie bitte Ort/PLZ oder Entfernung ab Bordesholm, "
            "ungefaehre Laufmeter und ob Spuele- oder Kochfeld-Ausschnitte noetig sind."
        )
    if service_type == "arbeitsplatte_only":
        return (
            "Damit ich die Arbeitsplatte sauber schaetzen kann, nennen Sie bitte Ort/PLZ oder Entfernung ab Bordesholm, "
            "ob es Ausschnitte fuer Spuele oder Kochfeld gibt und ob es eher einfach, normal oder schwierig ist."
        )
    return (
        "Damit ich eine unverbindliche Schaetzung geben kann, beschreiben Sie bitte kurz Ort, Umfang, "
        "Etage/Aufzug und ob ein Transporter oder weitere Helfer gebraucht werden."
    )


def _extract_distance_or_base_location(combined_text: str, text_ascii: str) -> float | None:
    distance_km = _extract_first_float(DISTANCE_PATTERN, combined_text)
    if distance_km is not None:
        return distance_km
    route_distance = _extract_known_route_distance(text_ascii)
    if route_distance is not None:
        return route_distance
    if _has_explicit_route_signal(text_ascii):
        return None
    mentions = _city_mentions(text_ascii)
    if mentions:
        latest_city = mentions[-1][1]
        return CITY_DISTANCE_FROM_BORDESHOLM_KM.get(latest_city)
    return None


def _extract_floors(combined_text: str, text_ascii: str) -> list[int]:
    floors = [int(value) for value in FLOOR_PATTERN.findall(combined_text)]
    for word, value in FLOOR_WORDS.items():
        if f"{word} etage" in text_ascii or f"{word} stock" in text_ascii:
            floors.append(value)
    return floors


def _detect_elevator(text_ascii: str) -> bool | None:
    if any(token in text_ascii for token in ("kein aufzug", "keinen aufzug", "ohne aufzug", "kein lift", "ohne lift")):
        return False
    if any(
        token in text_ascii
        for token in ("mit aufzug", "aufzug vorhanden", "es gibt ein aufzug", "es gibt einen aufzug", "lift vorhanden")
    ):
        return True
    return None


def _has_cutout_for(text_ascii: str, item_tokens: tuple[str, ...], explicit_tokens: tuple[str, ...]) -> bool:
    if any(token in text_ascii for token in explicit_tokens):
        return True
    if "ausschnitt" not in text_ascii and "ausschneiden" not in text_ascii and "loch" not in text_ascii:
        return False
    return any(token in text_ascii for token in item_tokens)


def extract_pricing_v2_input_from_messages(messages: list[ChatTurn]) -> PricingV2Input | None:
    user_texts = [" ".join(message.content.split()) for message in messages if message.role == "user"]
    if not user_texts:
        return None
    combined_text = " ".join(user_texts)
    text_ascii = _normalize(combined_text)
    service_type = _detect_service_type(text_ascii)
    if not service_type:
        return None

    distance_km = _extract_distance_or_base_location(combined_text, text_ascii)
    hours = _extract_first_float(HOURS_PATTERN, combined_text)
    kitchen_meters = _extract_first_float(METER_PATTERN, combined_text) if service_type == "kuechenmontage" else None
    kitchen_count = _extract_kitchen_count(text_ascii)
    furniture_items = _extract_furniture_items(text_ascii)
    workers_total = _extract_first_int(WORKERS_PATTERN, combined_text)
    rooms = _extract_first_int(ROOMS_PATTERN, combined_text) or _extract_word_count_before(
        text_ascii, ("zimmer", "zimmern", "raeume", "raum", "rooms")
    )
    cartons = _extract_first_int(CARTONS_PATTERN, combined_text) or _extract_first_int(CARTONS_LABEL_PATTERN, combined_text)
    floors = _extract_floors(combined_text, text_ascii)
    elevator = _detect_elevator(text_ascii)
    heavy_items = sum(
        1
        for token in (
            "waschmaschine",
            "kuehlschrank",
            "klavier",
            "tresor",
            "safe",
            "sofa",
            "schrank",
            "kommode",
            "bett",
        )
        if token in text_ascii
    )

    needs_transporter = _detect_bool(
        text_ascii,
        positive=("transporter", "trasport", "sprinter", "auto", "fahrzeug", "wagen"),
        negative=(
            "ohne transporter",
            "ohne transport",
            "ohne auto",
            "kein transporter",
            "kein transport",
            "keinen transport",
            "transport brauchen wir nicht",
            "nur helfer",
            "nur hilfe",
        ),
    )
    if service_type in {"umzug", "einzeltransport", *CLEARANCE_SERVICE_TYPES} and needs_transporter is None:
        needs_transporter = True
    if service_type == "transporthilfe" and needs_transporter is None:
        needs_transporter = False

    difficulty = _detect_difficulty(text_ascii)
    sink_cutout = _has_cutout_for(
        text_ascii,
        ("spuele", "spuelbecken"),
        ("spuelenausschnitt", "spuele ausschnitt", "ausschnitt fuer spuele", "ausschnitt für spuele"),
    )
    cooktop_cutout = _has_cutout_for(
        text_ascii,
        ("kochfeld", "herd", "ceran", "gas"),
        ("kochfeldausschnitt", "kochfeld-ausschnitt", "ausschnitt fuer kochfeld", "ausschnitt für kochfeld"),
    )
    if service_type == "arbeitsplatte_only":
        sink_cutout = sink_cutout or any(token in text_ascii for token in ("spuele", "spuelbecken"))
        cooktop_cutout = cooktop_cutout or any(token in text_ascii for token in ("kochfeld", "ceran", "gas"))

    return PricingV2Input(
        service_type=service_type,
        distance_km=distance_km,
        estimated_hours_min=hours,
        estimated_hours_max=hours,
        workers_total=workers_total,
        needs_transporter=needs_transporter,
        kitchen_meters=kitchen_meters,
        sink_cutout=sink_cutout,
        cooktop_cutout=cooktop_cutout,
        difficulty=difficulty,
        rooms=rooms,
        cartons=cartons,
        furniture_items=furniture_items,
        kitchen_count=kitchen_count,
        heavy_items=heavy_items or None,
        floor_from=floors[0] if floors else None,
        floor_to=floors[1] if len(floors) > 1 else None,
        elevator_from=elevator,
        elevator_to=elevator if len(floors) > 1 else None,
        description=combined_text,
    )


def build_company_pricing_helper_payload(
    messages: list[ChatTurn],
    *,
    lang: ChatLanguage = "de",
) -> dict[str, Any] | None:
    if lang != "de":
        return None
    pricing_input = extract_pricing_v2_input_from_messages(messages)
    if not pricing_input:
        return None

    result = estimate_company_price_v2(pricing_input)
    helper_path = (
        f"openai_primary_pricing_v2_{result.service_type}_follow_up"
        if result.missing_fields
        else f"openai_primary_pricing_v2_{result.service_type}_price"
    )
    helper_lines = [
        "Pricing v2 ist die aktive interne Grundlage fuer diesen Auftrag.",
        f"Erkannter Service: {result.service_type}",
        f"Pricing-Modell: {result.pricing_model}",
        f"Erkannte Eingaben: {asdict(pricing_input)}",
        f"Berechnung/Antwortbasis: {result.explanation_de}",
    ]
    if result.internal_notes:
        helper_lines.append("Interne Notizen: " + " | ".join(result.internal_notes))
    if result.missing_fields:
        helper_lines.append("Es fehlen: " + ", ".join(result.missing_fields))

    return {
        "path": helper_path,
        "helper_context": "\n".join(helper_lines),
        "fallback_reply": result.explanation_de,
        "force_reply": True,
        "faq_meta": {},
        "truth_meta": {
            "truth_type": "pricing",
            "truth_key": result.service_type,
            "pricing_source": "company_pricing_v2",
            "pricing_model": result.pricing_model,
            "price_min_eur": result.price_min_eur,
            "price_max_eur": result.price_max_eur,
            "workers_total": result.workers_total,
            "helpers_count": result.helpers_count,
            "needs_transporter": result.needs_transporter,
            "estimated_hours_min": result.estimated_hours_min,
            "estimated_hours_max": result.estimated_hours_max,
            "distance_km": result.distance_km,
            "missing_fields": list(result.missing_fields),
            "daily_target_eur": result.profile.get("daily_target_eur")
            or DEFAULT_COMPANY_PRICING_PROFILE.daily_target_eur,
        },
    }
