"""Authoritative pricing source registry for safe chatbot estimates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schemas import ChatLanguage

PricingSourceKind = Literal[
    "backend_move_pricing",
    "rule_based_estimator",
    "request_only",
    "included_in_quote",
]


@dataclass(frozen=True)
class PricingTruth:
    service_key: str
    source_kind: PricingSourceKind
    can_quote_estimate: bool
    required_details: tuple[str, ...]
    answer_de: str
    answer_en: str


PRICING_TRUTH_REGISTRY: dict[str, PricingTruth] = {
    "umzug": PricingTruth(
        service_key="umzug",
        source_kind="backend_move_pricing",
        can_quote_estimate=True,
        required_details=("startort", "zielort"),
        answer_de="Preise fuer Umzuege duerfen nur als unverbindliche Schaetzung aus der bestehenden Backend-Preislogik kommen.",
        answer_en="Prices for moves may only be given as non-binding estimates from the existing backend pricing logic.",
    ),
    "entsorgung": PricingTruth(
        service_key="entsorgung",
        source_kind="rule_based_estimator",
        can_quote_estimate=True,
        required_details=("ort", "was_genau", "umfang"),
        answer_de="Preise fuer Entsorgung, Entruempelung und Haushaltsaufloesung duerfen nur als unverbindliche Schaetzung aus der freigegebenen Preislogik kommen.",
        answer_en="Prices for disposal, clearance and household clearance may only be given as non-binding estimates from the approved pricing logic.",
    ),
    "moebelmontage": PricingTruth(
        service_key="moebelmontage",
        source_kind="rule_based_estimator",
        can_quote_estimate=True,
        required_details=("ort", "moebelart"),
        answer_de="Preise fuer Moebelmontage duerfen nur als unverbindliche Schaetzung aus dem lokalen Regel-Schaetzer kommen.",
        answer_en="Assembly prices may only be given as non-binding estimates from the local rule-based estimator.",
    ),
    "einzeltransport": PricingTruth(
        service_key="einzeltransport",
        source_kind="rule_based_estimator",
        can_quote_estimate=True,
        required_details=("startort", "transportgut"),
        answer_de="Preise fuer Einzeltransporte duerfen nur als unverbindliche Schaetzung aus dem lokalen Regel-Schaetzer kommen.",
        answer_en="Single-item transport prices may only be given as non-binding estimates from the local rule-based estimator.",
    ),
    "laminat": PricingTruth(
        service_key="laminat",
        source_kind="request_only",
        can_quote_estimate=False,
        required_details=("ort", "flaeche"),
        answer_de="Fuer Laminat- oder Parkett-Abbau ist aktuell keine freigegebene Chat-Preisquelle hinterlegt; bitte direkt anfragen.",
        answer_en="There is currently no approved chat pricing source for laminate or parquet removal; please contact us directly.",
    ),
    "verpackung": PricingTruth(
        service_key="verpackung",
        source_kind="included_in_quote",
        can_quote_estimate=False,
        required_details=("umfang",),
        answer_de="Verpackungsleistungen werden in der Anfrage oder Umzugs-Schaetzung beruecksichtigt, nicht als fixer Chat-Preis.",
        answer_en="Packing services are considered in the request or moving estimate, not as a fixed chat price.",
    ),
    "auspackservice": PricingTruth(
        service_key="auspackservice",
        source_kind="included_in_quote",
        can_quote_estimate=False,
        required_details=("umfang",),
        answer_de="Auspackservice wird in der Anfrage oder Umzugs-Schaetzung beruecksichtigt, nicht als fixer Chat-Preis.",
        answer_en="Unpacking service is considered in the request or move estimate, not as a fixed chat price.",
    ),
    "express": PricingTruth(
        service_key="express",
        source_kind="request_only",
        can_quote_estimate=False,
        required_details=("termin", "route"),
        answer_de="Fuer Express- oder kurzfristige Faelle ist keine feste Chat-Preisquelle hinterlegt; Verfuegbarkeit und Aufwand muessen direkt geprueft werden.",
        answer_en="There is no fixed chat pricing source for express or short-notice cases; availability and effort must be checked directly.",
    ),
    "halteverbotszone": PricingTruth(
        service_key="halteverbotszone",
        source_kind="request_only",
        can_quote_estimate=False,
        required_details=("ort", "termin"),
        answer_de="Fuer Halteverbotszonen ist keine feste Chat-Pauschale hinterlegt; das wird vorab individuell abgestimmt.",
        answer_en="There is no fixed chat fee for no-parking zones; this is coordinated individually in advance.",
    ),
}


def get_pricing_truth(service_key: str) -> PricingTruth | None:
    return PRICING_TRUTH_REGISTRY.get(service_key)


def build_pricing_safety_reply(service_key: str, lang: ChatLanguage = "de") -> str | None:
    truth = get_pricing_truth(service_key)
    if not truth:
        return None
    return truth.answer_en if lang == "en" else truth.answer_de
