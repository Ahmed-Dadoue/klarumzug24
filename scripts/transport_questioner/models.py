from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


QuestionType = Literal[
    "price_question",
    "service_question",
    "faq_question",
    "booking_question",
    "complaint",
    "objection",
    "policy_probe",
    "contradiction_probe",
    "edge_case",
    "expert_follow_up",
    "process_question",
    "quality_question",
    "special_case_transport_question",
    "differentiation_question",
]

TurnKind = Literal[
    "probe_question",
    "scenario_reply",
    "challenge",
    "clarification",
    "booking_push",
    "complaint_follow_up",
    "stop",
]

RequestMode = Literal["messages", "last_message"]


@dataclass
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class MemoryArtifact:
    artifact_id: str
    category: str
    source_path: str
    question: str = ""
    answer: str = ""
    summary: str = ""
    service_type: str | None = None
    question_type: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class PersonaProfile:
    label: str
    role: str
    tone: str
    expertise: str
    intent_style: str
    pressure_style: str


@dataclass
class TestObjective:
    label: str
    primary_goal: str
    service_focus: list[str]
    focus_areas: list[str]
    known_weak_points: list[str]
    success_signals: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ScenarioState:
    label: str
    services: list[str]
    facts: dict[str, Any]
    notes: list[str] = field(default_factory=list)

    def get_fact(self, key: str) -> Any:
        return self.facts.get(key)

    def available_fact_keys(self) -> list[str]:
        return sorted(key for key, value in self.facts.items() if value not in (None, "", [], {}))

    def extract_fact_payload(self, keys: list[str]) -> dict[str, Any]:
        return {key: self.facts[key] for key in keys if key in self.facts and self.facts[key] not in (None, "", [], {})}

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "services": self.services,
            "facts": {key: self.facts[key] for key in self.available_fact_keys()},
            "notes": self.notes,
        }

    def all_text(self) -> str:
        values = [self.label, " ".join(self.services), " ".join(self.notes)]
        for key, value in self.summary()["facts"].items():
            values.append(key)
            values.append(str(value))
        return " ".join(values)


@dataclass
class NextTurnPlan:
    turn_kind: TurnKind
    question_type: QuestionType
    goal: str
    message: str
    reasoning: str
    fact_keys_to_use: list[str] = field(default_factory=list)
    source_memory_ids: list[str] = field(default_factory=list)
    focus_area: str = ""
    generated_by: str = "openai"


@dataclass
class EvaluationResult:
    summary: str
    answered_real_question: bool
    contradiction: bool
    lost_context: bool
    rigid_price_flow: bool
    suspicious_price: bool
    mixed_services: bool
    ungrounded_promise: bool
    unstable_policy: bool
    overly_generic: bool
    bot_requested_fact_keys: list[str] = field(default_factory=list)
    recommended_turn_kind: TurnKind = "probe_question"
    recommended_question_type: QuestionType = "expert_follow_up"
    missing_edge_cases: list[str] = field(default_factory=list)
    bot_claims: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    severity: str = "low"
    generated_by: str = "heuristic"

    def failure_flags(self) -> list[str]:
        flags = {
            "contradiction": self.contradiction,
            "lost_context": self.lost_context,
            "rigid_price_flow": self.rigid_price_flow,
            "suspicious_price": self.suspicious_price,
            "mixed_services": self.mixed_services,
            "ungrounded_promise": self.ungrounded_promise,
            "unstable_policy": self.unstable_policy,
            "overly_generic": self.overly_generic,
        }
        return [name for name, active in flags.items() if active]


@dataclass
class BotResponse:
    text: str
    status_code: int
    raw_payload: Any
    latency_ms: float


@dataclass
class TurnLog:
    turn_index: int
    user_turn: ChatTurn
    bot_turn: ChatTurn
    plan: NextTurnPlan
    evaluation: EvaluationResult
    memory_artifact_ids: list[str]
    api_status_code: int
    latency_ms: float


@dataclass
class RunLog:
    conversation_id: str
    started_at_utc: str
    persona: PersonaProfile
    objective: TestObjective
    scenario: ScenarioState
    turns: list[TurnLog]
    stop_reason: str
    output_path: str = ""


@dataclass
class QuestionerConfig:
    repo_root: Path
    chatbot_api_url: str
    chatbot_api_key: str = ""
    chatbot_api_header: str = "Authorization"
    chatbot_timeout_seconds: int = 30
    chatbot_request_mode: RequestMode = "messages"
    chatbot_response_text_path: str | None = None
    chatbot_extra_headers: dict[str, str] = field(default_factory=dict)
    chatbot_extra_payload: dict[str, Any] = field(default_factory=dict)
    openai_api_key: str = ""
    questioner_model: str = "gpt-4.1-mini"
    evaluator_model: str = "gpt-4.1-mini"
    max_turns: int = 10
    question_max_output_tokens: int = 520
    evaluator_max_output_tokens: int = 520
    auto_reply_max_output_tokens: int = 140
    context_turn_limit: int = 12
    context_char_limit: int = 7000
    max_memory_items: int = 6
    max_retries: int = 3
    script_memory_dir: str = "scripts/transport_questioner_data"
    local_memory_dir: str = "local_knowledge_memory"
    lang: str = "de"
