"""AI-facing service definitions derived from the local service registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .service_registry import get_service_truth

ServiceType = Literal[
    "umzug",
    "entsorgung",
    "laminat",
    "moebelmontage",
    "einzeltransport",
]


@dataclass(frozen=True)
class ServiceDefinition:
    """Defines a service type and the data needed for pricing or follow-up questions."""

    key: ServiceType
    name_de: str
    keywords_de: list[str]
    required_fields: list[str]
    optional_fields: list[str]
    description_de: str


SERVICES: dict[ServiceType, ServiceDefinition] = {
    "umzug": ServiceDefinition(
        key="umzug",
        name_de="Umzug",
        keywords_de=[
            "umzug",
            "umziehen",
            "umzugsservice",
            "privatumzug",
            "firmenumzug",
            "move",
            "moving",
            "transport",
        ],
        required_fields=["from_city", "to_city"],
        optional_fields=[
            "rooms",
            "floor_from",
            "floor_to",
            "has_elevator_from",
            "has_elevator_to",
        ],
        description_de=(get_service_truth("umzug").summary_de if get_service_truth("umzug") else "Umzugsservice"),
    ),
    "entsorgung": ServiceDefinition(
        key="entsorgung",
        name_de="Entsorgung",
        keywords_de=[
            "entsorgung",
            "entsorgen",
            "entruempelung",
            "raeumung",
            "alte moebel",
            "disposal",
            "junk removal",
        ],
        required_fields=["location", "item_type"],
        optional_fields=["quantity", "size_description", "access_difficulty"],
        description_de=(
            get_service_truth("entsorgung").summary_de if get_service_truth("entsorgung") else "Entsorgung"
        ),
    ),
    "laminat": ServiceDefinition(
        key="laminat",
        name_de="Laminat / Parkett",
        keywords_de=[
            "laminat",
            "parkett",
            "boden",
            "bodenbelag",
            "flooring",
        ],
        required_fields=["location", "area_m2"],
        optional_fields=["abbau_only", "entsorgung_included", "floor"],
        description_de=(
            get_service_truth("laminat").summary_de if get_service_truth("laminat") else "Laminat-Abbau"
        ),
    ),
    "moebelmontage": ServiceDefinition(
        key="moebelmontage",
        name_de="Moebelmontage",
        keywords_de=[
            "montage",
            "demontage",
            "aufbau",
            "abbau",
            "moebelmontage",
            "ikea",
            "assembly",
        ],
        required_fields=["location", "furniture_type"],
        optional_fields=["quantity", "aufbau_or_abbau"],
        description_de=(
            get_service_truth("moebelmontage").summary_de
            if get_service_truth("moebelmontage")
            else "Moebelmontage"
        ),
    ),
    "einzeltransport": ServiceDefinition(
        key="einzeltransport",
        name_de="Einzeltransport",
        keywords_de=[
            "einzeltransport",
            "transport",
            "abholung",
            "lieferung",
            "waschmaschine",
            "kuehlschrank",
            "sofa",
            "klavier",
            "safe",
            "item transport",
        ],
        required_fields=["location", "item_description"],
        optional_fields=["destination", "weight_estimate"],
        description_de=(
            get_service_truth("einzeltransport").summary_de
            if get_service_truth("einzeltransport")
            else "Einzeltransport"
        ),
    ),
}


def identify_service_type(user_text: str) -> ServiceType | None:
    """Identify the most likely service type from the user text."""
    normalized = " ".join((user_text or "").lower().split())
    best_match: ServiceType | None = None
    best_score = 0

    for service_key, service in SERVICES.items():
        score = sum(1 for keyword in service.keywords_de if keyword in normalized)
        if score > best_score:
            best_score = score
            best_match = service_key

    return best_match if best_score > 0 else None


def get_service(service_type: ServiceType) -> ServiceDefinition:
    """Return the AI-facing service definition."""
    return SERVICES[service_type]
