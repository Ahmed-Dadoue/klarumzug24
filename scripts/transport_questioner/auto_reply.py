from __future__ import annotations

from typing import Any

from .models import NextTurnPlan, QuestionerConfig, ScenarioState
from .openai_engine import OpenAITransportBrain
from .scenario import find_relevant_fact_keys


def _human_label(key: str) -> str:
    return key.replace(".", " ").replace("_", " ")


class AutoReplyEngine:
    def __init__(self, *, brain: OpenAITransportBrain | None = None) -> None:
        self.brain = brain

    def build_reply(
        self,
        *,
        config: QuestionerConfig,
        plan: NextTurnPlan,
        scenario: ScenarioState,
        bot_question: str,
    ) -> str | None:
        fact_keys = plan.fact_keys_to_use or find_relevant_fact_keys(bot_question, scenario)
        fact_payload = scenario.extract_fact_payload(fact_keys)
        if not fact_payload:
            return None

        if self.brain and self.brain.is_configured():
            system_prompt = (
                "Du formulierst eine kurze Nutzerantwort auf Deutsch fuer einen externen Transport-/Umzugs-Chatbot. "
                "Nutze ausschliesslich die gegebenen Szenariofakten. Erfinde nichts. "
                "Bleibe natuerlich, menschlich, klar und kurz. Keine Aufzaehlung."
            )
            user_payload = {
                "bot_question": bot_question,
                "fact_payload": fact_payload,
                "scenario_services": scenario.services,
            }
            return self.brain.complete_text(
                system_prompt=system_prompt,
                user_payload=user_payload,
                max_output_tokens=config.auto_reply_max_output_tokens,
                task_name="auto_reply",
            ).strip()

        parts = [f"{_human_label(key)}: {value}" for key, value in fact_payload.items()]
        return "Gerne. " + "; ".join(parts) + "."
