from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .api_client import BlackBoxChatbotClient
from .auto_reply import AutoReplyEngine
from .domain import ensure_domain_safe_message, load_persona as _load_persona
from .evaluation import TransportAnswerEvaluator
from .memory import LocalKnowledgeStore, build_memory_prompt_snippets, build_query_text
from .models import ChatTurn, PersonaProfile, QuestionerConfig, RunLog, TestObjective, TurnLog
from .openai_engine import OpenAITransportBrain


def _trim_turns(turns: list[ChatTurn], *, turn_limit: int, char_limit: int) -> list[dict[str, str]]:
    trimmed = turns[-turn_limit:]
    serialized = [{"role": turn.role, "content": turn.content} for turn in trimmed]
    content = json.dumps(serialized, ensure_ascii=True)
    if len(content) <= char_limit:
        return serialized

    reduced: list[dict[str, str]] = []
    remaining = char_limit
    for turn in reversed(trimmed):
        snippet = turn.content.strip()
        if len(snippet) > 520:
            snippet = snippet[:520].rstrip() + "..."
        cost = len(snippet) + 32
        if cost > remaining:
            break
        reduced.append({"role": turn.role, "content": snippet})
        remaining -= cost
    reduced.reverse()
    return reduced


def load_objective(path: str | Path) -> TestObjective:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Objective-Datei muss ein JSON-Objekt sein.")
    return TestObjective(
        label=str(payload.get("label") or Path(path).stem),
        primary_goal=str(payload.get("primary_goal") or "Transport-Chatbot professionell testen"),
        service_focus=[str(item).strip() for item in payload.get("service_focus", []) if str(item).strip()],
        focus_areas=[str(item).strip() for item in payload.get("focus_areas", []) if str(item).strip()],
        known_weak_points=[str(item).strip() for item in payload.get("known_weak_points", []) if str(item).strip()],
        success_signals=[str(item).strip() for item in payload.get("success_signals", []) if str(item).strip()],
        notes=str(payload.get("notes") or ""),
    )


class TransportQuestionerRunner:
    def __init__(self, config: QuestionerConfig) -> None:
        self.config = config
        self.api_client = BlackBoxChatbotClient(config)
        self.knowledge = LocalKnowledgeStore(
            repo_root=config.repo_root,
            local_memory_dir=config.local_memory_dir,
            script_memory_dir=config.script_memory_dir,
            max_records_per_file=500,
        )
        self.question_brain = OpenAITransportBrain(
            api_key=config.openai_api_key,
            model=config.questioner_model,
            max_retries=config.max_retries,
        )
        self.evaluator_brain = OpenAITransportBrain(
            api_key=config.openai_api_key,
            model=config.evaluator_model,
            max_retries=config.max_retries,
        )
        self.auto_reply = AutoReplyEngine(brain=self.question_brain)
        self.evaluator = TransportAnswerEvaluator(brain=self.evaluator_brain)

    def run(
        self,
        *,
        scenario,
        persona: PersonaProfile,
        objective: TestObjective,
        conversation_id: str | None = None,
    ) -> RunLog:
        conversation_id = conversation_id or f"transport_test_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC).isoformat()
        turns: list[ChatTurn] = []
        turn_logs: list[TurnLog] = []
        coverage = {"question_types": [], "focus_areas": [], "failure_flags": []}
        prior_bot_claims: list[str] = []
        previous_failures: list[str] = []
        stop_reason = "max_turns_reached"

        for turn_index in range(1, self.config.max_turns + 1):
            last_bot_answer = turns[-1].content if turns and turns[-1].role == "assistant" else ""
            memory_artifacts = self.knowledge.retrieve(
                query_text=build_query_text(
                    scenario,
                    last_bot_answer=last_bot_answer,
                    focus_areas=objective.focus_areas,
                    previous_failures=previous_failures,
                ),
                service_hints=scenario.services or objective.service_focus,
                limit=self.config.max_memory_items,
            )
            memory_snippets = build_memory_prompt_snippets(memory_artifacts)

            previous_evaluation = turn_logs[-1].evaluation if turn_logs else None
            transcript_excerpt = _trim_turns(
                turns,
                turn_limit=self.config.context_turn_limit,
                char_limit=self.config.context_char_limit,
            )
            plan = self.question_brain.plan_next_turn(
                config=self.config,
                persona=persona,
                objective=objective,
                scenario=scenario,
                transcript_excerpt=transcript_excerpt,
                memory_snippets=memory_snippets,
                last_evaluation=previous_evaluation,
                coverage=coverage,
            )

            if plan.turn_kind == "stop":
                stop_reason = "openai_requested_stop"
                break

            if plan.turn_kind == "scenario_reply":
                auto_reply_text = self.auto_reply.build_reply(
                    config=self.config,
                    plan=plan,
                    scenario=scenario,
                    bot_question=last_bot_answer,
                )
                if auto_reply_text:
                    plan.message = auto_reply_text
                else:
                    plan.turn_kind = "clarification"
                    plan.message = ensure_domain_safe_message(
                        "Koennen Sie bitte praezisieren, welche Angabe Ihnen noch fehlt?",
                        service_hints=scenario.services,
                        focus_area=plan.focus_area,
                    )
                    plan.generated_by = "openai+fallback"

            plan.message = ensure_domain_safe_message(
                plan.message,
                service_hints=scenario.services or objective.service_focus,
                focus_area=plan.focus_area,
            )

            user_turn = ChatTurn(role="user", content=plan.message)
            turns.append(user_turn)
            try:
                bot_response = self.api_client.send(conversation_id=conversation_id, turns=turns)
            except Exception as exc:
                stop_reason = f"api_error:{type(exc).__name__}"
                break
            bot_turn = ChatTurn(role="assistant", content=bot_response.text)
            turns.append(bot_turn)

            evaluation = self.evaluator.evaluate(
                config=self.config,
                last_user_turn=user_turn,
                bot_turn=bot_turn,
                scenario=scenario,
                prior_bot_claims=prior_bot_claims,
            )
            prior_bot_claims.extend(claim for claim in evaluation.bot_claims if claim not in prior_bot_claims)
            previous_failures = evaluation.failure_flags()

            if plan.question_type not in coverage["question_types"]:
                coverage["question_types"].append(plan.question_type)
            if plan.focus_area and plan.focus_area not in coverage["focus_areas"]:
                coverage["focus_areas"].append(plan.focus_area)
            for flag in previous_failures:
                if flag not in coverage["failure_flags"]:
                    coverage["failure_flags"].append(flag)

            turn_log = TurnLog(
                turn_index=turn_index,
                user_turn=user_turn,
                bot_turn=bot_turn,
                plan=plan,
                evaluation=evaluation,
                memory_artifact_ids=[artifact.artifact_id for artifact in memory_artifacts],
                api_status_code=bot_response.status_code,
                latency_ms=bot_response.latency_ms,
            )
            turn_logs.append(turn_log)

            if previous_failures:
                self.knowledge.persist_failure_case(
                    conversation_id=conversation_id,
                    turn_index=turn_index,
                    question=user_turn.content,
                    bot_answer=bot_turn.content,
                    service_type=scenario.services[0] if scenario.services else None,
                    evaluation_flags=previous_failures,
                    summary=evaluation.summary,
                )
            if any(flag in previous_failures for flag in ("contradiction", "suspicious_price", "unstable_policy", "rigid_price_flow")):
                self.knowledge.persist_good_probe(
                    conversation_id=conversation_id,
                    turn_index=turn_index,
                    plan=plan,
                    bot_answer=bot_turn.content,
                    evaluation_flags=previous_failures,
                )

        run_log = RunLog(
            conversation_id=conversation_id,
            started_at_utc=started_at,
            persona=persona,
            objective=objective,
            scenario=scenario,
            turns=turn_logs,
            stop_reason=stop_reason,
        )
        output_path = self.knowledge.persist_run_log(asdict(run_log), conversation_id=conversation_id)
        run_log.output_path = str(output_path)
        return run_log


def build_config(
    *,
    repo_root: Path,
    chatbot_api_url: str,
    chatbot_api_key: str,
    chatbot_response_text_path: str | None,
    chatbot_request_mode: str,
    chatbot_extra_headers: dict[str, str],
    chatbot_extra_payload: dict[str, Any],
    openai_api_key: str,
    questioner_model: str,
    evaluator_model: str,
    max_turns: int,
    lang: str,
) -> QuestionerConfig:
    return QuestionerConfig(
        repo_root=repo_root,
        chatbot_api_url=chatbot_api_url,
        chatbot_api_key=chatbot_api_key,
        chatbot_response_text_path=chatbot_response_text_path,
        chatbot_request_mode=chatbot_request_mode,  # type: ignore[arg-type]
        chatbot_extra_headers=chatbot_extra_headers,
        chatbot_extra_payload=chatbot_extra_payload,
        openai_api_key=openai_api_key,
        questioner_model=questioner_model,
        evaluator_model=evaluator_model,
        max_turns=max_turns,
        lang=lang,
    )


def load_persona(label: str) -> PersonaProfile:
    return _load_persona(label)


def repo_root_from_env() -> Path:
    return Path(__file__).resolve().parents[2]


def openai_key_from_env() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()
