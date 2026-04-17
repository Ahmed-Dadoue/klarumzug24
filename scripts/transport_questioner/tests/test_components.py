from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.transport_questioner.auto_reply import AutoReplyEngine
from scripts.transport_questioner.domain import ensure_domain_safe_message, is_domain_safe
from scripts.transport_questioner.evaluation import TransportAnswerEvaluator
from scripts.transport_questioner.memory import LocalKnowledgeStore
from scripts.transport_questioner.models import ChatTurn, NextTurnPlan, QuestionerConfig, ScenarioState
from scripts.transport_questioner.scenario import find_relevant_fact_keys


class TransportQuestionerComponentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = ScenarioState(
            label="test_case",
            services=["umzug", "kuechenmontage"],
            facts={
                "route.from_city": "Berlin",
                "route.to_city": "Hamburg",
                "move.rooms": 3,
                "pickup.floor": "2. OG",
                "pickup.elevator": False,
                "services.halteverbotszone": True,
                "items.special": ["Klavier"],
            },
            notes=[],
        )

    def test_domain_guardrail_repairs_offtopic_message(self) -> None:
        unsafe = "Kannst du mir auch etwas ueber Python Deployment sagen?"
        repaired = ensure_domain_safe_message(unsafe, service_hints=["umzug"], focus_area="preise")
        self.assertFalse(is_domain_safe(unsafe))
        self.assertTrue(is_domain_safe(repaired))

    def test_scenario_fact_matching_finds_route(self) -> None:
        keys = find_relevant_fact_keys("Von welcher Stadt startet der Umzug?", self.scenario)
        self.assertIn("route.from_city", keys)

    def test_auto_reply_fallback_uses_exact_scenario_values(self) -> None:
        plan = NextTurnPlan(
            turn_kind="scenario_reply",
            question_type="expert_follow_up",
            goal="Frage nach Route beantworten",
            message="",
            reasoning="",
            fact_keys_to_use=["route.from_city", "route.to_city"],
            focus_area="ablauf_organisation",
        )
        config = QuestionerConfig(
            repo_root=Path.cwd(),
            chatbot_api_url="https://example.invalid",
            openai_api_key="",
        )
        reply = AutoReplyEngine(brain=None).build_reply(
            config=config,
            plan=plan,
            scenario=self.scenario,
            bot_question="Von welcher Stadt nach welcher Stadt ziehen Sie um?",
        )
        self.assertIsNotNone(reply)
        self.assertIn("Berlin", reply)
        self.assertIn("Hamburg", reply)

    def test_local_knowledge_store_prefers_matching_service_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            audit_dir = root / "local_knowledge_memory" / "logs"
            review_dir = root / "local_knowledge_memory" / "review_queue" / "pending"
            audit_dir.mkdir(parents=True)
            review_dir.mkdir(parents=True)
            (root / "scripts" / "transport_questioner_data").mkdir(parents=True)

            audit_payload = {
                "request_id": "req_1",
                "incoming_message": "Was kostet ein Umzug mit Halteverbotszone?",
                "final_response": "Es koennen Zuschlaege anfallen.",
                "service_type": "umzug",
                "source_used": "openai",
            }
            (audit_dir / "conversation_audit.jsonl").write_text(
                json.dumps(audit_payload, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            review_payload = {
                "candidate_id": "mem_1",
                "memory_category": "failure_case",
                "question": "Was kostet Entruempelung?",
                "answer": "Unklare Antwort",
                "summary": "Failure",
                "service_type": "entruempelung",
            }
            (review_dir / "mem_1.json").write_text(json.dumps(review_payload, ensure_ascii=True), encoding="utf-8")

            store = LocalKnowledgeStore(
                repo_root=root,
                local_memory_dir="local_knowledge_memory",
                script_memory_dir="scripts/transport_questioner_data",
                max_records_per_file=20,
            )
            artifacts = store.retrieve(
                query_text="Umzug Halteverbotszone Zuschlaege",
                service_hints=["umzug"],
                limit=5,
            )
            self.assertGreaterEqual(len(artifacts), 1)
            self.assertEqual("umzug", artifacts[0].service_type)

    def test_evaluator_flags_rigid_price_flow(self) -> None:
        config = QuestionerConfig(
            repo_root=Path.cwd(),
            chatbot_api_url="https://example.invalid",
            openai_api_key="",
        )
        evaluator = TransportAnswerEvaluator(brain=None)
        result = evaluator.evaluate(
            config=config,
            last_user_turn=ChatTurn(role="user", content="Wie ist Ihre Versicherung fuer einen Klaviertransport geregelt?"),
            bot_turn=ChatTurn(
                role="assistant",
                content="Um eine Schaetzung zu machen, von welcher Stadt ziehen Sie um?",
            ),
            scenario=self.scenario,
            prior_bot_claims=[],
        )
        self.assertTrue(result.rigid_price_flow)
        self.assertTrue(result.lost_context)


if __name__ == "__main__":
    unittest.main()
