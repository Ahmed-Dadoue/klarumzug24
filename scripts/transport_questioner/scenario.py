from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import normalize_text
from .models import ScenarioState


FACT_KEY_ALIASES: dict[str, list[str]] = {
    "route.from_city": ["von welcher stadt", "startstadt", "abholort", "von wo", "startort"],
    "route.to_city": ["in welche stadt", "zielstadt", "wohin", "zielort", "nach wo"],
    "move.rooms": ["wie viele zimmer", "zimmeranzahl", "zimmer"],
    "move.distance_km": ["wie viele kilometer", "entfernung", "strecke", "distanz"],
    "pickup.floor": ["welches stockwerk", "welche etage", "am start", "beim auszug"],
    "dropoff.floor": ["welches stockwerk am ziel", "am ziel", "beim einzug", "ziel-etage"],
    "pickup.elevator": ["aufzug am start", "fahrstuhl am start", "aufzug vorhanden"],
    "dropoff.elevator": ["aufzug am ziel", "fahrstuhl am ziel"],
    "timing.move_date": ["welcher termin", "wann", "umzugstag", "datum"],
    "timing.weekend": ["samstag", "wochenende", "wochentag"],
    "services.halteverbotszone": ["halteverbotszone", "parkverbot", "parksituation"],
    "services.kitchen_montage": ["kuechenmontage", "kueche aufbauen", "kuechenaufbau"],
    "services.kitchen_demontage": ["kuechendemontage", "kueche abbauen", "kuechenabbau"],
    "services.moebelmontage": ["moebelmontage", "moebelaufbau", "montage"],
    "services.moebeldemontage": ["moebeldemontage", "moebelabbau", "demontage"],
    "services.entsorgung": ["entsorgung", "entsorgen"],
    "services.entruempelung": ["entruempelung", "entrumpelung", "hausaufloesung", "wohnungsaufloesung"],
    "services.storage": ["lagerung", "zwischenlagerung", "einlagern"],
    "items.special": ["klavier", "tresor", "safe", "schwere gegenstaende", "schwere moebel"],
    "pricing.budget_eur": ["budget", "preisrahmen"],
    "customer.company_move": ["firmenumzug", "buero", "unternehmen"],
    "insurance.required": ["versicherung", "haftung"],
    "cleanup.related": ["reinigung", "endreinigung"],
}


def _flatten_payload(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"label", "services", "notes"}:
            continue
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_payload(value, prefix=full_key))
        else:
            flattened[full_key] = value
    return flattened


def load_scenario(path: str | Path) -> ScenarioState:
    scenario_path = Path(path)
    payload = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Scenario-Datei muss ein JSON-Objekt sein.")

    services_raw = payload.get("services") or payload.get("service_focus") or []
    services = [str(item).strip() for item in services_raw if str(item).strip()]
    facts_root = payload.get("facts") if isinstance(payload.get("facts"), dict) else payload
    facts = _flatten_payload(facts_root)
    if services and "services.requested" not in facts:
        facts["services.requested"] = services
    notes = [str(item).strip() for item in payload.get("notes", []) if str(item).strip()]
    return ScenarioState(
        label=str(payload.get("label") or scenario_path.stem),
        services=services,
        facts=facts,
        notes=notes,
    )


def summarize_for_prompt(scenario: ScenarioState) -> dict[str, Any]:
    return scenario.summary()


def find_relevant_fact_keys(question_text: str, scenario: ScenarioState) -> list[str]:
    normalized_question = normalize_text(question_text)
    matches: list[str] = []
    for fact_key, aliases in FACT_KEY_ALIASES.items():
        if fact_key not in scenario.facts or scenario.facts[fact_key] in (None, "", [], {}):
            continue
        if any(alias in normalized_question for alias in aliases):
            matches.append(fact_key)

    if matches:
        return sorted(set(matches))

    for fact_key in scenario.available_fact_keys():
        key_hint = fact_key.replace(".", " ")
        if any(part in normalized_question for part in key_hint.split()):
            matches.append(fact_key)
    return sorted(set(matches))
