"""File-based local knowledge memory for human-reviewed chatbot learning."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("klarumzug24")

CONVERSATION_TYPES = ("real_user", "test_script", "automated_test")
MEMORY_CATEGORIES = {
    "faq_candidate": "faq_candidates",
    "service_knowledge": "service_knowledge",
    "failure_case": "failure_cases",
    "repeated_question": "repeated_questions",
    "useful_approved_answer": "useful_approved_answers",
}
DEFAULT_CONTROL = {
    "capture_enabled": True,
    "review_required_by_default": True,
    "capture_types": {
        "real_user": True,
        "test_script": True,
        "automated_test": True,
    },
    "updated_at_utc": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _memory_root() -> Path:
    configured = os.getenv("DODE_LOCAL_MEMORY_ROOT", "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / "local_knowledge_memory"


def _path_map() -> dict[str, Path]:
    root = _memory_root()
    return {
        "root": root,
        "control": root / "control.json",
        "readme": root / "README.md",
        "raw_conversations": root / "raw_knowledge" / "raw_conversations.jsonl",
        "conversation_audit": root / "logs" / "conversation_audit.jsonl",
        "approved_memory": root / "approved_knowledge" / "approved_memory.jsonl",
        "faq_candidates": root / "faq_candidates" / "faq_candidates.jsonl",
        "service_knowledge": root / "service_knowledge" / "service_knowledge.jsonl",
        "failure_cases": root / "failure_cases" / "failure_cases.jsonl",
        "repeated_questions": root / "repeated_questions" / "repeated_questions.jsonl",
        "useful_approved_answers": root / "useful_approved_answers" / "useful_approved_answers.jsonl",
        "queue_pending": root / "review_queue" / "pending",
        "queue_approved": root / "review_queue" / "approved",
        "queue_rejected": root / "review_queue" / "rejected",
    }


def _default_readme() -> str:
    return """# Local Knowledge Memory

Dieses Verzeichnis speichert lokal kontrollierte Wissensartefakte aus Chatgespraechen.

- `raw_knowledge/`: rohe Konversationsbeobachtungen
- `review_queue/`: vom Menschen zu pruefende Wissenskandidaten
- `approved_knowledge/`: freigegebene Wissenseintraege
- `faq_candidates/`: offene FAQ-Kandidaten
- `service_knowledge/`: freigegebenes servicebezogenes Wissen
- `failure_cases/`: bekannte Fehlfaelle
- `repeated_questions/`: wiederholte Fragenmuster
- `useful_approved_answers/`: wiederverwendbare, freigegebene Antworten
- `logs/`: strukturierte Audit-Logs fuer Monitoring und Reports

Die Datei `control.json` erlaubt es, lokale Wissensaufnahme pro Gespraechstyp zu pausieren.
"""


def ensure_local_memory_layout() -> dict[str, Path]:
    paths = _path_map()
    for key, path in paths.items():
        if key in {"root", "control", "readme"}:
            continue
        target_dir = path if path.suffix == "" else path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

    paths["root"].mkdir(parents=True, exist_ok=True)
    if not paths["control"].exists():
        paths["control"].write_text(
            json.dumps({**DEFAULT_CONTROL, "updated_at_utc": _now_iso()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not paths["readme"].exists():
        paths["readme"].write_text(_default_readme(), encoding="utf-8")

    for key, path in paths.items():
        if path.suffix != ".jsonl":
            continue
        path.touch(exist_ok=True)
    return paths


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read local memory control file")
        return dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
    return items


def get_capture_control() -> dict[str, Any]:
    paths = ensure_local_memory_layout()
    current = _read_json(paths["control"], DEFAULT_CONTROL)
    capture_types = dict(DEFAULT_CONTROL["capture_types"])
    capture_types.update(current.get("capture_types") or {})
    return {
        "capture_enabled": bool(current.get("capture_enabled", True)),
        "review_required_by_default": bool(current.get("review_required_by_default", True)),
        "capture_types": {name: bool(capture_types.get(name, True)) for name in CONVERSATION_TYPES},
        "updated_at_utc": current.get("updated_at_utc"),
    }


def update_capture_control(
    *,
    capture_enabled: bool | None = None,
    review_required_by_default: bool | None = None,
    capture_types: dict[str, bool] | None = None,
) -> dict[str, Any]:
    paths = ensure_local_memory_layout()
    control = get_capture_control()
    if capture_enabled is not None:
        control["capture_enabled"] = bool(capture_enabled)
    if review_required_by_default is not None:
        control["review_required_by_default"] = bool(review_required_by_default)
    if capture_types:
        for key, value in capture_types.items():
            if key in CONVERSATION_TYPES:
                control["capture_types"][key] = bool(value)
    control["updated_at_utc"] = _now_iso()
    _write_json(paths["control"], control)
    return control


def should_capture_conversation(conversation_type: str) -> bool:
    control = get_capture_control()
    if not control["capture_enabled"]:
        return False
    return bool(control["capture_types"].get(conversation_type, True))


def list_conversation_audits(
    *,
    limit: int = 50,
    conversation_type: str | None = None,
) -> list[dict[str, Any]]:
    paths = ensure_local_memory_layout()
    items = _iter_jsonl(paths["conversation_audit"])
    if conversation_type:
        items = [item for item in items if item.get("conversation_type") == conversation_type]
    items.sort(key=lambda item: item.get("timestamp_utc", ""), reverse=True)
    return items[:limit]


def _pending_candidate_path(candidate_id: str) -> Path:
    paths = ensure_local_memory_layout()
    return paths["queue_pending"] / f"{candidate_id}.json"


def _approved_candidate_path(candidate_id: str) -> Path:
    paths = ensure_local_memory_layout()
    return paths["queue_approved"] / f"{candidate_id}.json"


def _rejected_candidate_path(candidate_id: str) -> Path:
    paths = ensure_local_memory_layout()
    return paths["queue_rejected"] / f"{candidate_id}.json"


def list_review_candidates(
    *,
    status: str = "pending",
    limit: int = 50,
) -> list[dict[str, Any]]:
    paths = ensure_local_memory_layout()
    queue_dir = {
        "pending": paths["queue_pending"],
        "approved": paths["queue_approved"],
        "rejected": paths["queue_rejected"],
    }.get(status, paths["queue_pending"])

    items: list[dict[str, Any]] = []
    for path in sorted(queue_dir.glob("*.json"), key=lambda value: value.stat().st_mtime, reverse=True):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status in {"pending", "approved", "rejected"} and parsed.get("review_status") != status:
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
        if len(items) >= limit:
            break
    return items


def _append_to_category_file(candidate: dict[str, Any]) -> None:
    paths = ensure_local_memory_layout()
    category_name = MEMORY_CATEGORIES.get(candidate.get("memory_category") or "")
    if category_name:
        _append_jsonl(paths[category_name], candidate)
    _append_jsonl(paths["approved_memory"], candidate)


def review_memory_candidate(
    candidate_id: str,
    *,
    decision: str,
    reviewer: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    pending_path = _pending_candidate_path(candidate_id)
    if not pending_path.exists():
        return None

    try:
        payload = json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read pending memory candidate %s", candidate_id)
        return None

    payload["review_status"] = "approved" if decision == "approve" else "rejected"
    payload["reviewed_at_utc"] = _now_iso()
    payload["reviewer"] = (reviewer or "admin").strip()
    if notes:
        payload["review_notes"] = notes.strip()

    target_path = (
        _approved_candidate_path(candidate_id)
        if decision == "approve"
        else _rejected_candidate_path(candidate_id)
    )
    pending_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if decision == "approve":
        _append_to_category_file(payload)
    return payload


def get_memory_stats() -> dict[str, Any]:
    paths = ensure_local_memory_layout()
    audits = _iter_jsonl(paths["conversation_audit"])
    counts_by_type: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    fallback_count = 0
    for audit in audits:
        conversation_type = audit.get("conversation_type") or "unknown"
        counts_by_type[conversation_type] = counts_by_type.get(conversation_type, 0) + 1
        source_used = audit.get("source_used") or "unknown"
        counts_by_source[source_used] = counts_by_source.get(source_used, 0) + 1
        if audit.get("fallback_used"):
            fallback_count += 1

    return {
        "memory_root": str(paths["root"]),
        "audit_records": len(audits),
        "pending_review": len(list_review_candidates(status="pending", limit=100000)),
        "approved_review": len(list_review_candidates(status="approved", limit=100000)),
        "rejected_review": len(list_review_candidates(status="rejected", limit=100000)),
        "by_conversation_type": counts_by_type,
        "by_source_used": counts_by_source,
        "fallback_records": fallback_count,
        "capture_control": get_capture_control(),
    }


def capture_conversation_memory(record: dict[str, Any]) -> dict[str, Any]:
    paths = ensure_local_memory_layout()
    normalized_record = dict(record)
    normalized_record.setdefault("timestamp_utc", _now_iso())
    normalized_record.setdefault("candidate_knowledge", [])
    normalized_record.setdefault("context_problems", [])
    normalized_record.setdefault("repetition_signals", [])
    conversation_type = str(normalized_record.get("conversation_type") or "real_user")
    review_required = normalized_record.get("memory_review_required")
    control = get_capture_control()
    if review_required is None:
        review_required = control["review_required_by_default"]
    normalized_record["memory_review_required"] = bool(review_required)

    if not should_capture_conversation(conversation_type):
        return {
            "captured": False,
            "review_required": bool(review_required),
            "candidates_created": 0,
            "reason": "capture_disabled",
        }

    _append_jsonl(paths["raw_conversations"], normalized_record)
    _append_jsonl(paths["conversation_audit"], normalized_record)

    created_candidates: list[dict[str, Any]] = []
    for candidate in normalized_record.get("candidate_knowledge") or []:
        candidate_id = f"mem_{uuid.uuid4().hex[:12]}"
        payload = {
            "candidate_id": candidate_id,
            "created_at_utc": normalized_record["timestamp_utc"],
            "review_status": "pending",
            "conversation_id": normalized_record.get("conversation_id"),
            "conversation_type": conversation_type,
            "source_label": normalized_record.get("source_label"),
            "test_run_id": normalized_record.get("test_run_id"),
            "memory_category": candidate.get("memory_category"),
            "candidate_type": candidate.get("candidate_type"),
            "question": candidate.get("question") or normalized_record.get("incoming_message"),
            "answer": candidate.get("answer") or normalized_record.get("final_response"),
            "summary": candidate.get("summary"),
            "service_type": candidate.get("service_type") or normalized_record.get("service_type"),
            "intent_type": candidate.get("intent_type") or normalized_record.get("intent_type"),
            "source_used": normalized_record.get("source_used"),
            "helper_path": normalized_record.get("helper_path"),
            "fallback_used": bool(normalized_record.get("fallback_used")),
            "context_problems": normalized_record.get("context_problems") or [],
            "repetition_signals": normalized_record.get("repetition_signals") or [],
            "confidence": candidate.get("confidence", 0.5),
            "approved_answer_candidate": candidate.get("approved_answer_candidate"),
            "metadata": candidate.get("metadata") or {},
        }
        created_candidates.append(payload)

        if review_required:
            _pending_candidate_path(candidate_id).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            payload["review_status"] = "approved"
            payload["reviewed_at_utc"] = _now_iso()
            payload["reviewer"] = "system-auto"
            _approved_candidate_path(candidate_id).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _append_to_category_file(payload)

    return {
        "captured": True,
        "review_required": bool(review_required),
        "candidates_created": len(created_candidates),
        "candidate_ids": [candidate["candidate_id"] for candidate in created_candidates],
    }
