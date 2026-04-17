from __future__ import annotations

import re
from typing import Any

from .domain import ALLOWED_QUESTION_TYPES, ALLOWED_TURN_KINDS, normalize_text
from .models import ChatTurn, EvaluationResult, QuestionerConfig, ScenarioState
from .openai_engine import OpenAITransportBrain
from .scenario import find_relevant_fact_keys


PRICE_PATTERN = re.compile(r"(\d{2,5})(?:\s*[-–]\s*(\d{2,5}))?\s*(?:euro|eur|€)", re.IGNORECASE)

SERVICE_KEYWORDS = {
    "umzug": ["umzug", "umziehen", "firmenumzug", "teilumzug"],
    "einzeltransport": ["einzeltransport", "transport", "abholung", "lieferung"],
    "entruempelung": ["entruempelung", "entrumpelung", "hausaufloesung", "wohnungsaufloesung"],
    "entsorgung": ["entsorgung", "entsorgen"],
    "moebelmontage": ["moebelmontage", "moebelaufbau", "montage", "demontage"],
    "kuechenmontage": ["kuechenmontage", "kuechendemontage", "kuechenabbau", "kuechenaufbau"],
}


def _extract_prices(text: str) -> list[int]:
    prices: list[int] = []
    for first, second in PRICE_PATTERN.findall(text):
        prices.append(int(first))
        if second:
            prices.append(int(second))
    return prices


def _scenario_complexity(scenario: ScenarioState) -> int:
    score = 0
    rooms = scenario.get_fact("move.rooms")
    distance = scenario.get_fact("move.distance_km")
    special_items = str(scenario.get_fact("items.special") or "")
    services_requested = scenario.get_fact("services.requested") or scenario.services

    if isinstance(rooms, (int, float)) and rooms >= 3:
        score += 1
    if isinstance(distance, (int, float)) and distance >= 80:
        score += 1
    if services_requested and len(list(services_requested)) >= 3:
        score += 2
    if any(token in normalize_text(special_items) for token in ("klavier", "tresor", "safe", "schwer")):
        score += 2
    for key in (
        "services.kitchen_montage",
        "services.kitchen_demontage",
        "services.halteverbotszone",
        "services.storage",
    ):
        if scenario.get_fact(key):
            score += 1
    return score


def _detect_mixed_services(text: str, scenario: ScenarioState) -> bool:
    normalized = normalize_text(text)
    allowed = {normalize_text(service) for service in scenario.services}
    detected: set[str] = set()
    for service, keywords in SERVICE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            detected.add(service)
    if not detected:
        return False
    return any(service not in allowed for service in detected) and bool(allowed)


def _heuristic_evaluation(
    *,
    last_user_message: str,
    bot_answer: str,
    scenario: ScenarioState,
) -> dict[str, Any]:
    normalized_user = normalize_text(last_user_message)
    normalized_bot = normalize_text(bot_answer)
    bot_requested_fact_keys = find_relevant_fact_keys(bot_answer, scenario)
    prices = _extract_prices(bot_answer)
    complexity = _scenario_complexity(scenario)

    suspicious_price = bool(prices) and (
        (complexity >= 3 and min(prices) < 300) or (complexity >= 5 and min(prices) < 600)
    )
    rigid_price_flow = (
        any(marker in normalized_bot for marker in ("fuer eine schaetzung", "um eine schaetzung", "von welcher stadt", "wie viele zimmer"))
        and any(marker in normalized_user for marker in ("versicherung", "stornierung", "qualitaet", "beschwerde", "warum", "garantie"))
    )
    ungrounded_promise = (
        any(marker in normalized_bot for marker in ("garantiert", "definitiv", "sicher", "festpreis", "auf jeden fall"))
        and not any(marker in normalized_bot for marker in ("unverbindlich", "kann", "haengt", "abhaengig"))
    )
    overly_generic = len(bot_answer.strip()) < 140 and any(
        marker in normalized_bot for marker in ("gern helfe", "bitte kontaktieren", "weitere informationen", "melden sie sich")
    )
    lost_context = bool(bot_requested_fact_keys)
    mixed_services = _detect_mixed_services(bot_answer, scenario)
    answered_real_question = not (bot_requested_fact_keys and len(normalized_bot) < 220)

    evidence: list[str] = []
    if suspicious_price:
        evidence.append(f"Preis wirkt fuer Szenariokomplexitaet {complexity} zu niedrig: {prices}")
    if rigid_price_flow:
        evidence.append("Bot faellt auf standardisierten Preisflow zurueck statt die eigentliche Fachfrage zu beantworten.")
    if lost_context:
        evidence.append(f"Bot fragt Fakten erneut ab, die im Szenario vorhanden sind: {bot_requested_fact_keys}")
    if mixed_services:
        evidence.append("Bot vermischt Services ausserhalb des aktuellen Szenarios.")
    if ungrounded_promise:
        evidence.append("Bot nutzt zu starke Zusagen ohne sichtbare Einschraenkung.")

    return {
        "summary": "Heuristische Bewertung erzeugt.",
        "answered_real_question": answered_real_question,
        "contradiction": False,
        "lost_context": lost_context,
        "rigid_price_flow": rigid_price_flow,
        "suspicious_price": suspicious_price,
        "mixed_services": mixed_services,
        "ungrounded_promise": ungrounded_promise,
        "unstable_policy": False,
        "overly_generic": overly_generic,
        "bot_requested_fact_keys": bot_requested_fact_keys,
        "recommended_turn_kind": "challenge" if any((suspicious_price, rigid_price_flow, mixed_services, ungrounded_promise)) else "probe_question",
        "recommended_question_type": "contradiction_probe" if suspicious_price else "expert_follow_up",
        "missing_edge_cases": [],
        "bot_claims": [sentence.strip() for sentence in re.split(r"[.!?]", bot_answer) if sentence.strip()][:3],
        "evidence": evidence,
        "severity": "high" if any((suspicious_price, rigid_price_flow, mixed_services, ungrounded_promise)) else "medium" if lost_context else "low",
        "generated_by": "heuristic",
    }


class TransportAnswerEvaluator:
    def __init__(self, *, brain: OpenAITransportBrain | None = None) -> None:
        self.brain = brain

    def evaluate(
        self,
        *,
        config: QuestionerConfig,
        last_user_turn: ChatTurn,
        bot_turn: ChatTurn,
        scenario: ScenarioState,
        prior_bot_claims: list[str],
    ) -> EvaluationResult:
        heuristic = _heuristic_evaluation(
            last_user_message=last_user_turn.content,
            bot_answer=bot_turn.content,
            scenario=scenario,
        )
        merged = dict(heuristic)

        if self.brain and self.brain.is_configured():
            try:
                model_result = self.brain.evaluate_answer(
                    config=config,
                    scenario=scenario,
                    last_user_message=last_user_turn.content,
                    bot_answer=bot_turn.content,
                    prior_bot_claims=prior_bot_claims,
                    heuristic_hints=heuristic,
                )
                for key, value in model_result.items():
                    if key in {"bot_claims", "missing_edge_cases", "evidence"}:
                        merged[key] = list(dict.fromkeys((merged.get(key) or []) + (value or [])))
                    elif isinstance(value, bool):
                        merged[key] = bool(merged.get(key)) or value
                    elif value not in (None, "", []):
                        merged[key] = value
                merged["generated_by"] = "hybrid_openai"
            except Exception as exc:
                merged["generated_by"] = "heuristic_fallback"
                merged["evidence"] = list(dict.fromkeys((merged.get("evidence") or []) + [f"OpenAI-Evaluation ausgefallen: {type(exc).__name__}"]))

        return EvaluationResult(
            summary=str(merged.get("summary") or "Bewertung abgeschlossen."),
            answered_real_question=bool(merged.get("answered_real_question")),
            contradiction=bool(merged.get("contradiction")),
            lost_context=bool(merged.get("lost_context")),
            rigid_price_flow=bool(merged.get("rigid_price_flow")),
            suspicious_price=bool(merged.get("suspicious_price")),
            mixed_services=bool(merged.get("mixed_services")),
            ungrounded_promise=bool(merged.get("ungrounded_promise")),
            unstable_policy=bool(merged.get("unstable_policy")),
            overly_generic=bool(merged.get("overly_generic")),
            bot_requested_fact_keys=[str(item) for item in merged.get("bot_requested_fact_keys", []) if str(item)],
            recommended_turn_kind=(
                str(merged.get("recommended_turn_kind") or "probe_question")
                if str(merged.get("recommended_turn_kind") or "probe_question") in ALLOWED_TURN_KINDS
                else "probe_question"
            ),  # type: ignore[arg-type]
            recommended_question_type=(
                str(merged.get("recommended_question_type") or "expert_follow_up")
                if str(merged.get("recommended_question_type") or "expert_follow_up") in ALLOWED_QUESTION_TYPES
                else "expert_follow_up"
            ),  # type: ignore[arg-type]
            missing_edge_cases=[str(item) for item in merged.get("missing_edge_cases", []) if str(item)],
            bot_claims=[str(item) for item in merged.get("bot_claims", []) if str(item)],
            evidence=[str(item) for item in merged.get("evidence", []) if str(item)],
            severity=str(merged.get("severity") or "low"),
            generated_by=str(merged.get("generated_by") or "heuristic"),
        )
