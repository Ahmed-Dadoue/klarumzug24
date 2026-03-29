from __future__ import annotations

import argparse
import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai import generate_dode_reply
from app.ai.intent_classifier import classify_intent
from app.ai.schemas import ChatTurn
from main import SessionLocal, calculate_assigned_price


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimales Chat-Routing-Harness fuer Intent/Path Regression-Checks."
    )
    parser.add_argument(
        "--cases",
        default="test_data/chat_routing_cases.json",
        help="Pfad zur JSON-Testfall-Datei relativ zu backend/.",
    )
    parser.add_argument(
        "--out-dir",
        default="reports",
        help="Ausgabeordner relativ zu backend/.",
    )
    return parser.parse_args()


class JsonEventCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.events: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        raw = record.getMessage()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(payload, dict):
            self.events.append(payload)


def normalize_actual_intent(message: str, lang: str) -> str:
    classified = classify_intent(message, lang=lang)
    if classified.service_type:
        return f"{classified.intent_type}/{classified.service_type}"
    return classified.intent_type


def resolve_used_path(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("event") == "chat_processing_path":
            route = event.get("route")
            if isinstance(route, str) and route.strip():
                return route.strip()
    return "-"


def make_logger() -> tuple[logging.Logger, JsonEventCollector]:
    logger = logging.getLogger(f"chat_routing_harness.{datetime.now(UTC).timestamp()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    collector = JsonEventCollector()
    logger.handlers = [collector]
    return logger, collector


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    input_text = str(case.get("input", "")).strip()
    expected_intent = str(case.get("expected_intent", "")).strip()
    lang = str(case.get("lang", "de")).strip() or "de"
    case_id = str(case.get("id", "")).strip() or "-"

    actual_intent = normalize_actual_intent(input_text, lang)
    logger, collector = make_logger()

    response_text = ""
    used_path = "-"
    pass_fail = "FAIL"

    try:
        response_text = generate_dode_reply(
            messages=[ChatTurn(role="user", content=input_text)],
            page="/umzugsrechner.html",
            lang=lang,
            session_factory=SessionLocal,
            assigned_price_calculator=calculate_assigned_price,
            logger=logger,
            request_id=f"harness_{case_id}",
            conversation_id=f"harness_{case_id}",
        )
        used_path = resolve_used_path(collector.events)
        pass_fail = "PASS" if actual_intent == expected_intent else "FAIL"
    except Exception as exc:
        used_path = resolve_used_path(collector.events)
        response_text = f"[ERROR] {type(exc).__name__}: {exc}"
        pass_fail = "FAIL"

    return {
        "id": case_id,
        "input": input_text,
        "expected_intent": expected_intent,
        "actual_intent": actual_intent,
        "used_path": used_path,
        "response_text": " ".join(str(response_text).split()),
        "pass_fail": pass_fail,
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown_report(rows: list[dict[str, Any]], generated_at: str) -> str:
    total = len(rows)
    passed = sum(1 for row in rows if row["pass_fail"] == "PASS")
    failed = total - passed

    summary_rows = [
        ["generated_at_utc", generated_at],
        ["total_cases", str(total)],
        ["passed", str(passed)],
        ["failed", str(failed)],
        ["pass_rate", f"{(passed / total * 100):.1f}%" if total else "-"],
    ]

    detail_rows: list[list[str]] = []
    for row in rows:
        detail_rows.append(
            [
                str(row["id"]),
                str(row["input"]),
                str(row["expected_intent"]),
                str(row["actual_intent"]),
                str(row["used_path"]),
                str(row["pass_fail"]),
            ]
        )

    lines = [
        "# Chat Routing Harness Report",
        "",
        "## Summary",
        markdown_table(["metric", "value"], summary_rows),
        "",
        "## Results",
        markdown_table(
            ["id", "input", "expected_intent", "actual_intent", "used_path", "pass_fail"],
            detail_rows,
        ),
        "",
    ]
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "input",
                "expected_intent",
                "actual_intent",
                "used_path",
                "response_text",
                "pass_fail",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    backend_dir = Path(__file__).resolve().parent
    cases_path = (backend_dir / args.cases).resolve()
    out_dir = (backend_dir / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not cases_path.exists():
        print(f"Testfall-Datei nicht gefunden: {cases_path}")
        return 1

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        print("Testfall-Datei muss ein JSON-Array sein.")
        return 1

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")

    rows = [evaluate_case(case) for case in cases if isinstance(case, dict)]

    csv_path = out_dir / f"chat-routing-report-{stamp}.csv"
    md_path = out_dir / f"chat-routing-report-{stamp}.md"

    write_csv(csv_path, rows)
    md_path.write_text(build_markdown_report(rows, generated_at), encoding="utf-8")

    print(f"CSV-Report geschrieben: {csv_path}")
    print(f"Markdown-Report geschrieben: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
