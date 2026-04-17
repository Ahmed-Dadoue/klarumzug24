from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .domain import normalize_text
from .models import MemoryArtifact, NextTurnPlan, ScenarioState, TurnLog


def _tokenize(text: str) -> set[str]:
    normalized = normalize_text(text)
    return {token for token in normalized.replace("/", " ").replace("-", " ").split() if len(token) > 2}


class LocalKnowledgeStore:
    def __init__(
        self,
        *,
        repo_root: Path,
        local_memory_dir: str,
        script_memory_dir: str,
        max_records_per_file: int = 500,
    ) -> None:
        self.repo_root = repo_root
        self.local_memory_root = repo_root / local_memory_dir
        self.script_memory_root = repo_root / script_memory_dir
        self.max_records_per_file = max_records_per_file
        self._artifacts: list[MemoryArtifact] | None = None

    def _tail_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items: deque[dict[str, Any]] = deque(maxlen=self.max_records_per_file)
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    items.append(payload)
        return list(items)

    def _load_review_queue(self, directory: Path) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not directory.exists():
            return items
        for path in sorted(directory.glob("*.json"))[-self.max_records_per_file :]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload["_path"] = str(path.relative_to(self.repo_root))
                items.append(payload)
        return items

    def load(self, *, force_reload: bool = False) -> list[MemoryArtifact]:
        if self._artifacts is not None and not force_reload:
            return self._artifacts

        artifacts: list[MemoryArtifact] = []

        audit_path = self.local_memory_root / "logs" / "conversation_audit.jsonl"
        for index, payload in enumerate(self._tail_jsonl(audit_path)):
            artifacts.append(
                MemoryArtifact(
                    artifact_id=str(payload.get("request_id") or f"audit_{index}"),
                    category="conversation_audit",
                    source_path=str(audit_path.relative_to(self.repo_root)),
                    question=str(payload.get("incoming_message") or ""),
                    answer=str(payload.get("final_response") or ""),
                    summary=str(payload.get("helper_path") or ""),
                    service_type=(str(payload.get("service_type")) if payload.get("service_type") else None),
                    metadata={
                        "source_used": payload.get("source_used"),
                        "context_problems": payload.get("context_problems") or [],
                    },
                )
            )

        for directory in (
            self.local_memory_root / "review_queue" / "pending",
            self.local_memory_root / "review_queue" / "approved",
        ):
            for payload in self._load_review_queue(directory):
                artifacts.append(
                    MemoryArtifact(
                        artifact_id=str(payload.get("candidate_id") or payload.get("request_id") or payload.get("_path")),
                        category=str(payload.get("memory_category") or "review_entry"),
                        source_path=str(payload.get("_path") or directory.relative_to(self.repo_root)),
                        question=str(payload.get("question") or ""),
                        answer=str(payload.get("answer") or ""),
                        summary=str(payload.get("summary") or ""),
                        service_type=(str(payload.get("service_type")) if payload.get("service_type") else None),
                        question_type=(str(payload.get("intent_type")) if payload.get("intent_type") else None),
                        metadata={"review_status": payload.get("review_status")},
                    )
                )

        for filename, category in (
            ("failure_cases.jsonl", "script_failure_case"),
            ("good_probes.jsonl", "good_probe"),
        ):
            path = self.script_memory_root / filename
            for index, payload in enumerate(self._tail_jsonl(path)):
                artifacts.append(
                    MemoryArtifact(
                        artifact_id=str(payload.get("record_id") or f"{category}_{index}"),
                        category=category,
                        source_path=str(path.relative_to(self.repo_root)) if path.exists() else str(path),
                        question=str(payload.get("question") or ""),
                        answer=str(payload.get("bot_answer") or ""),
                        summary=str(payload.get("summary") or payload.get("goal") or ""),
                        service_type=(str(payload.get("service_type")) if payload.get("service_type") else None),
                        question_type=(str(payload.get("question_type")) if payload.get("question_type") else None),
                        metadata={"evaluation_flags": payload.get("evaluation_flags") or []},
                    )
                )

        self._artifacts = artifacts
        return artifacts

    def retrieve(
        self,
        *,
        query_text: str,
        service_hints: Iterable[str],
        limit: int,
    ) -> list[MemoryArtifact]:
        artifacts = self.load()
        query_tokens = _tokenize(query_text)
        services = {normalize_text(service) for service in service_hints if service}
        scored: list[MemoryArtifact] = []

        for artifact in artifacts:
            haystack = " ".join(
                [
                    artifact.question,
                    artifact.answer,
                    artifact.summary,
                    artifact.service_type or "",
                    artifact.question_type or "",
                ]
            )
            artifact_tokens = _tokenize(haystack)
            overlap = len(query_tokens & artifact_tokens)
            if overlap == 0 and not services:
                continue
            score = float(overlap)
            if artifact.service_type and normalize_text(artifact.service_type) in services:
                score += 3.0
            if artifact.category in {"script_failure_case", "failure_case"}:
                score += 2.0
            if artifact.category in {"good_probe", "repeated_question"}:
                score += 1.5
            if artifact.question_type and artifact.question_type in query_text:
                score += 0.5
            if score <= 0:
                continue
            scored.append(
                MemoryArtifact(
                    artifact_id=artifact.artifact_id,
                    category=artifact.category,
                    source_path=artifact.source_path,
                    question=artifact.question,
                    answer=artifact.answer,
                    summary=artifact.summary,
                    service_type=artifact.service_type,
                    question_type=artifact.question_type,
                    tags=list(artifact.tags),
                    metadata=dict(artifact.metadata),
                    score=round(score, 3),
                )
            )

        scored.sort(key=lambda item: (-item.score, item.artifact_id))
        return scored[:limit]

    def persist_failure_case(
        self,
        *,
        conversation_id: str,
        turn_index: int,
        question: str,
        bot_answer: str,
        service_type: str | None,
        evaluation_flags: list[str],
        summary: str,
    ) -> None:
        record = {
            "record_id": f"failure_{conversation_id}_{turn_index}",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "conversation_id": conversation_id,
            "turn_index": turn_index,
            "service_type": service_type,
            "question": question,
            "bot_answer": bot_answer,
            "evaluation_flags": evaluation_flags,
            "summary": summary,
        }
        self._append_jsonl(self.script_memory_root / "failure_cases.jsonl", record)

    def persist_good_probe(
        self,
        *,
        conversation_id: str,
        turn_index: int,
        plan: NextTurnPlan,
        bot_answer: str,
        evaluation_flags: list[str],
    ) -> None:
        record = {
            "record_id": f"probe_{conversation_id}_{turn_index}",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "conversation_id": conversation_id,
            "turn_index": turn_index,
            "question": plan.message,
            "goal": plan.goal,
            "focus_area": plan.focus_area,
            "question_type": plan.question_type,
            "service_type": None,
            "bot_answer": bot_answer,
            "evaluation_flags": evaluation_flags,
            "summary": plan.reasoning,
        }
        self._append_jsonl(self.script_memory_root / "good_probes.jsonl", record)

    def persist_run_log(self, run_payload: dict[str, Any], *, conversation_id: str) -> Path:
        run_dir = self.script_memory_root / "run_logs"
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = run_dir / f"{timestamp}_{conversation_id}.json"
        path.write_text(json.dumps(run_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return path

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def build_memory_prompt_snippets(artifacts: list[MemoryArtifact]) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for artifact in artifacts:
        snippets.append(
            {
                "id": artifact.artifact_id,
                "category": artifact.category,
                "service_type": artifact.service_type,
                "question": artifact.question[:220],
                "answer": artifact.answer[:220],
                "summary": artifact.summary[:180],
                "score": artifact.score,
            }
        )
    return snippets


def build_query_text(
    scenario: ScenarioState,
    *,
    last_bot_answer: str,
    focus_areas: list[str],
    previous_failures: list[str],
) -> str:
    parts = [
        scenario.all_text(),
        last_bot_answer,
        " ".join(focus_areas),
        " ".join(previous_failures),
    ]
    return " ".join(part for part in parts if part).strip()
