from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erzeugt eine Chat-Qualitaetsreport-Vorlage."
    )
    parser.add_argument(
        "--period",
        choices=("daily", "weekly", "monthly", "batch"),
        required=True,
        help="Art des Reports.",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Optionales Label, z. B. 2026-W16 oder 2026-04.",
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=0,
        help="Optional fuer Batch-Reports, z. B. 200.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/chat_quality_reports",
        help="Ausgabeordner relativ zum Repo-Root.",
    )
    return parser.parse_args()


def build_filename(period: str, label: str, conversations: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = label.strip() or stamp
    if period == "batch" and conversations > 0:
        return f"{stamp}-{period}-{conversations}-conversations-{suffix}.md"
    return f"{stamp}-{period}-{suffix}.md"


def load_local_memory_stats(repo_root: Path) -> dict[str, object]:
    memory_root = repo_root / "local_knowledge_memory"
    audit_path = memory_root / "logs" / "conversation_audit.jsonl"
    pending_dir = memory_root / "review_queue" / "pending"
    counts_by_type: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    fallback_count = 0
    total = 0

    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            total += 1
            conversation_type = str(payload.get("conversation_type") or "unknown")
            source_used = str(payload.get("source_used") or "unknown")
            counts_by_type[conversation_type] = counts_by_type.get(conversation_type, 0) + 1
            counts_by_source[source_used] = counts_by_source.get(source_used, 0) + 1
            if payload.get("fallback_used"):
                fallback_count += 1

    pending_review = len(list(pending_dir.glob("*.json"))) if pending_dir.exists() else 0
    return {
        "audit_records": total,
        "fallback_records": fallback_count,
        "pending_review": pending_review,
        "by_conversation_type": counts_by_type,
        "by_source_used": counts_by_source,
    }


def build_report(period: str, label: str, conversations: int) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    scope = label.strip() or "auto"
    batch_note = f"{conversations} conversations" if period == "batch" and conversations > 0 else "n/a"
    repo_root = Path(__file__).resolve().parents[1]
    memory_stats = load_local_memory_stats(repo_root)
    conversation_types = memory_stats["by_conversation_type"] or {}
    sources = memory_stats["by_source_used"] or {}

    return f"""# Chat Quality Report

- generated_at_utc: `{generated_at}`
- period: `{period}`
- scope_label: `{scope}`
- batch_size: `{batch_note}`
- report_status: `draft`

## Executive Summary

- Current assessment: `{memory_stats["audit_records"]}` lokal erfasste Chat-Audits, `{memory_stats["pending_review"]}` offene Review-Kandidaten.
- Highest-priority risk: `Fallbacks={memory_stats["fallback_records"]}` und `OpenAI/Helper-Verteilung={sources}`.
- Highest-priority improvement: `Conversation types={conversation_types}` sauber auswerten und Review-Queue regelmaessig pflegen.

## Frequent Error Patterns

- Observation: `Fallback-Nutzung` oder `Review-Stau` zuerst pruefen.
- Evidence source: `local_knowledge_memory/logs/conversation_audit.jsonl`
- Suggested action: `pending_review` taeglich sichten und Fallback-Faelle separat priorisieren.

## Conversation Breakdowns

- Breakdown type: 
- Trigger: `conversation_type`-Mix aktuell `{conversation_types}`
- Suggested action: Test-, Script- und Realgespraeche getrennt bewerten.

## Hallucination Risks

- Risk area: `source_used=openai`
- Root cause guess: `Noch nicht jede Frage ist ueber FAQ/Tool/Pricing abgedeckt.`
- Containment plan: `Offene FAQ-/Service-Kandidaten aus der Review-Queue in lokales Wissen ueberfuehren.`

## Repetitive Or Rigid Replies

- Pattern: `Siehe repetition_signals in conversation_audit.jsonl`
- Impact: `Wiederholungen werden jetzt strukturiert mitgeloggt.`
- Suggested action: `repeated_questions`-Datei regelmaessig freigeben oder entkraeften.

## FAQ Coverage Gaps

- Missing topic: `Offene Kandidaten liegen in local_knowledge_memory/faq_candidates/`
- Current fallback behavior: `OpenAI oder Helper-Fallback`
- Suggested action: `freigegebene FAQ-Kandidaten in die kuratierte Wissensbasis uebernehmen`

## Legal And Policy Clarity

- Document:
- Observed ambiguity:
- Risk level:
- Suggested action:

## Frontend UX Opportunities

- Component:
- Friction:
- Suggested action:

## Backend And Orchestration Opportunities

- Component: `chat_service / local_memory / learning routes`
- Friction: `Noch kein vollautomatischer Scheduler fuer Reports und Reviews`
- Suggested action: `Script ueber Task Scheduler oder Cron gegen echte Produktionssignale laufen lassen`

## Priority List

1. 
2. 
3. 

## Missing Data Or Blocking Factors

- Missing signal: `Produktionsnahe Entscheidung, welche Review-Kandidaten spaeter automatisch in FAQ/Service-Wissen uebernommen werden sollen`
- Why it matters: `Davon haengt die kontrollierte Reduktion der OpenAI-Abhaengigkeit ab`
- Proposed instrumentation: `Admin-Review ueber /api/admin/learning/memory/* plus lokale Freigabedateien`
"""


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = build_filename(args.period, args.label, args.conversations)
    path = output_dir / filename
    path.write_text(
        build_report(args.period, args.label, args.conversations),
        encoding="utf-8",
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
