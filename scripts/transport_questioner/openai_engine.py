from __future__ import annotations

import json
import re
import time
from typing import Any

from .domain import ALLOWED_QUESTION_TYPES, ALLOWED_TURN_KINDS, DOMAIN_SYSTEM_GUARDRAIL, ensure_domain_safe_message
from .models import EvaluationResult, MemoryArtifact, NextTurnPlan, PersonaProfile, QuestionerConfig, ScenarioState, TestObjective


class OpenAITransportBrain:
    def __init__(self, *, api_key: str, model: str, max_retries: int) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.max_retries = max_retries
        self._client = None

    def _client_or_raise(self):
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY fehlt fuer den Transport Questioner.")
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise ValueError("Keine JSON-Antwort gefunden.")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("JSON-Antwort ist kein Objekt.")
        return payload

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int,
        task_name: str,
    ) -> dict[str, Any]:
        client = self._client_or_raise()
        payload_text = json.dumps(user_payload, ensure_ascii=True, indent=2)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = client.responses.create(
                    model=self.model,
                    instructions=system_prompt,
                    input=payload_text,
                    max_output_tokens=max_output_tokens,
                    store=False,
                )
                output_text = (getattr(response, "output_text", "") or "").strip()
                if not output_text:
                    raise ValueError(f"Leere OpenAI-Antwort bei {task_name}.")
                return self._extract_json_object(output_text)
            except Exception as exc:
                last_error = exc
                time.sleep(min(0.8 * attempt, 2.5))

        raise RuntimeError(f"OpenAI-Aufgabe fehlgeschlagen ({task_name}): {last_error}") from last_error

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int,
        task_name: str,
    ) -> str:
        client = self._client_or_raise()
        payload_text = json.dumps(user_payload, ensure_ascii=True, indent=2)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = client.responses.create(
                    model=self.model,
                    instructions=system_prompt,
                    input=payload_text,
                    max_output_tokens=max_output_tokens,
                    store=False,
                )
                output_text = (getattr(response, "output_text", "") or "").strip()
                if output_text:
                    return output_text
                raise ValueError(f"Leere OpenAI-Antwort bei {task_name}.")
            except Exception as exc:
                last_error = exc
                time.sleep(min(0.8 * attempt, 2.5))
        raise RuntimeError(f"OpenAI-Textaufgabe fehlgeschlagen ({task_name}): {last_error}") from last_error

    def plan_next_turn(
        self,
        *,
        config: QuestionerConfig,
        persona: PersonaProfile,
        objective: TestObjective,
        scenario: ScenarioState,
        transcript_excerpt: list[dict[str, str]],
        memory_snippets: list[dict[str, Any]],
        last_evaluation: EvaluationResult | None,
        coverage: dict[str, list[str]],
    ) -> NextTurnPlan:
        system_prompt = (
            f"{DOMAIN_SYSTEM_GUARDRAIL}\n"
            "Du bist der eigentliche Questioner-Engine fuer einen professionellen Black-Box-Test "
            "gegen einen externen Transport-/Umzugs-Chatbot. "
            "Du entscheidest die naechste Nutzeraktion intelligent anhand von Szenario, Persona, "
            "letzter Bot-Antwort, Memory-Artefakten, bekannten Schwachpunkten, Testziel und offener Coverage. "
            "Erlaube nur diese turn_kind-Werte: probe_question, scenario_reply, challenge, clarification, "
            "booking_push, complaint_follow_up, stop. "
            "Erlaube nur diese question_type-Werte: price_question, service_question, faq_question, "
            "booking_question, complaint, objection, policy_probe, contradiction_probe, edge_case, "
            "expert_follow_up, process_question, quality_question, special_case_transport_question, "
            "differentiation_question. "
            "Wenn der Bot nach fehlenden Fakten fragt und die Fakten im Szenario vorhanden sind, "
            "kannst du scenario_reply waehlen. Dann darfst du KEINE Fakten erfinden, sondern musst "
            "in fact_keys_to_use nur reale Szenario-Schluessel nennen. "
            "Wenn du probe_question, challenge oder clarification waehlst, schreibe eine natuerliche, "
            "realistische, branchenspezifische und professionelle Nutzer-Nachricht auf Deutsch. "
            "Kein Offtopic, keine Technikfragen, keine juristischen Allgemeinthemen ausserhalb des Transportkontexts. "
            "Gib JSON mit den Feldern turn_kind, question_type, goal, message, reasoning, fact_keys_to_use, "
            "source_memory_ids, focus_area zurueck."
        )
        payload = {
            "persona": persona.__dict__,
            "objective": objective.__dict__,
            "scenario": scenario.summary(),
            "last_evaluation": last_evaluation.__dict__ if last_evaluation else None,
            "coverage": coverage,
            "memory_snippets": memory_snippets,
            "transcript_excerpt": transcript_excerpt,
        }
        raw = self.complete_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=config.question_max_output_tokens,
            task_name="plan_next_turn",
        )

        plan = NextTurnPlan(
            turn_kind=(
                str(raw.get("turn_kind") or "probe_question")
                if str(raw.get("turn_kind") or "probe_question") in ALLOWED_TURN_KINDS
                else "probe_question"
            ),  # type: ignore[arg-type]
            question_type=(
                str(raw.get("question_type") or "expert_follow_up")
                if str(raw.get("question_type") or "expert_follow_up") in ALLOWED_QUESTION_TYPES
                else "expert_follow_up"
            ),  # type: ignore[arg-type]
            goal=str(raw.get("goal") or objective.primary_goal),
            message=str(raw.get("message") or "").strip(),
            reasoning=str(raw.get("reasoning") or "OpenAI-Plan ohne Begruendung."),
            fact_keys_to_use=[
                str(item).strip()
                for item in raw.get("fact_keys_to_use", [])
                if str(item).strip()
            ],
            source_memory_ids=[
                str(item).strip()
                for item in raw.get("source_memory_ids", [])
                if str(item).strip()
            ],
            focus_area=str(raw.get("focus_area") or (objective.focus_areas[0] if objective.focus_areas else "")),
            generated_by="openai",
        )
        if plan.turn_kind != "scenario_reply":
            plan.message = ensure_domain_safe_message(
                plan.message,
                service_hints=scenario.services,
                focus_area=plan.focus_area,
            )
        if not plan.message and plan.turn_kind != "scenario_reply":
            plan.message = ensure_domain_safe_message(
                "Wie genau handhaben Sie diesen Fall in der Praxis?",
                service_hints=scenario.services,
                focus_area=plan.focus_area,
            )
        return plan

    def evaluate_answer(
        self,
        *,
        config: QuestionerConfig,
        scenario: ScenarioState,
        last_user_message: str,
        bot_answer: str,
        prior_bot_claims: list[str],
        heuristic_hints: dict[str, Any],
    ) -> dict[str, Any]:
        system_prompt = (
            f"{DOMAIN_SYSTEM_GUARDRAIL}\n"
            "Bewerte die letzte Antwort eines Transport-/Umzugs-Chatbots. "
            "Pruefe, ob die echte Frage beantwortet wurde, ob Kontext verloren ging, "
            "ob Preise verdaechtig wirken, ob Policy unstabil ist, ob Leistungen vermischt werden, "
            "ob starre Preisflow-Rueckfragen dominieren, ob Versprechen ungesichert wirken und "
            "welcher naechste Testschritt sinnvoll ist. "
            "Gib JSON mit den Feldern summary, answered_real_question, contradiction, lost_context, "
            "rigid_price_flow, suspicious_price, mixed_services, ungrounded_promise, unstable_policy, "
            "overly_generic, bot_claims, missing_edge_cases, recommended_turn_kind, recommended_question_type, "
            "severity, evidence zurueck."
        )
        payload = {
            "scenario": scenario.summary(),
            "last_user_message": last_user_message,
            "bot_answer": bot_answer,
            "prior_bot_claims": prior_bot_claims[-8:],
            "heuristic_hints": heuristic_hints,
        }
        return self.complete_json(
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=config.evaluator_max_output_tokens,
            task_name="evaluate_answer",
        )
