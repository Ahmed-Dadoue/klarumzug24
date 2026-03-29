from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CONVERSION_STEPS = (
    "chat_started",
    "entered_price_flow",
    "contact_intent",
    "lead_created",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze chat conversion events from backend log files."
    )
    parser.add_argument(
        "logfiles",
        nargs="*",
        help="Optional log files to analyze. Defaults to backend/*.log.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Optional path for CSV export.",
    )
    parser.add_argument(
        "--md",
        dest="md_path",
        help="Optional path for Markdown report export.",
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        help="Optional UTC date filter in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--last-days",
        dest="last_days",
        type=int,
        help="Optional UTC lookback window in whole days.",
    )
    return parser.parse_args()


def default_logfiles() -> list[Path]:
    backend_dir = Path(__file__).resolve().parent
    return sorted(path for path in backend_dir.glob("*.log") if path.is_file())


def extract_json_payload(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    end = line.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(line[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or "event" not in payload:
        return None
    return payload


def load_events(logfiles: list[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for logfile in logfiles:
        try:
            with logfile.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    payload = extract_json_payload(line)
                    if payload:
                        payload["_logfile"] = logfile.name
                        events.append(payload)
        except OSError:
            continue
    return events


def parse_event_date(event: dict[str, Any]) -> date | None:
    raw_value = event.get("timestamp_utc")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).date()


def filter_events_by_date(
    events: list[dict[str, Any]],
    *,
    report_date: str | None,
    last_days: int | None,
) -> list[dict[str, Any]]:
    if report_date and last_days:
        raise ValueError("--date und --last-days koennen nicht zusammen verwendet werden.")

    if report_date:
        target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        return [event for event in events if parse_event_date(event) == target_date]

    if last_days is not None:
        if last_days <= 0:
            raise ValueError("--last-days muss groesser als 0 sein.")
        today_utc = datetime.now(timezone.utc).date()
        earliest_date = today_utc - timedelta(days=last_days - 1)
        filtered: list[dict[str, Any]] = []
        for event in events:
            event_date = parse_event_date(event)
            if event_date and earliest_date <= event_date <= today_utc:
                filtered.append(event)
        return filtered

    return events


def conversation_key(event: dict[str, Any]) -> str | None:
    value = event.get("conversation_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def format_ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "-"
    return f"{(numerator / denominator) * 100:.1f}%"


def print_counter(title: str, counter: Counter[str]) -> None:
    print(title)
    if not counter:
        print("  -")
        return
    for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key}: {value}")


def ratio_value(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 2)


def build_csv_rows(
    conversion_counts: dict[str, int],
    lang_counters: dict[str, Counter[str]],
    page_counters: dict[str, Counter[str]],
    page_metrics: list[dict[str, Any]],
    lang_metrics: list[dict[str, Any]],
    top_page: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    started = conversion_counts["chat_started"]
    rows: list[dict[str, Any]] = []

    for stage in CONVERSION_STEPS:
        count = conversion_counts[stage]
        rows.append(
            {
                "scope": "overall",
                "stage": stage,
                "count": count,
                "rate": ratio_value(count, started),
                "lang": "",
                "page": "",
            }
        )

    for stage in CONVERSION_STEPS:
        stage_total = conversion_counts[stage]
        for lang, count in sorted(lang_counters[stage].items(), key=lambda item: (-item[1], item[0])):
            rows.append(
                {
                    "scope": "lang",
                    "stage": stage,
                    "count": count,
                    "rate": ratio_value(count, stage_total),
                    "lang": lang,
                    "page": "",
                }
            )
        for page, count in sorted(page_counters[stage].items(), key=lambda item: (-item[1], item[0])):
            rows.append(
                {
                    "scope": "page",
                    "stage": stage,
                    "count": count,
                    "rate": ratio_value(count, stage_total),
                    "lang": "",
                    "page": page,
                }
            )

    for item in lang_metrics:
        rows.append(
            {
                "scope": "lang_metric",
                "stage": item["stage"],
                "count": item["count"],
                "rate": item["rate"],
                "lang": item["lang"],
                "page": "",
            }
        )

    for item in page_metrics:
        rows.append(
            {
                "scope": "page_metric",
                "stage": item["stage"],
                "count": item["count"],
                "rate": item["rate"],
                "lang": "",
                "page": item["page"],
            }
        )

    if top_page:
        rows.append(
            {
                "scope": "top_page",
                "stage": top_page["stage"],
                "count": top_page["count"],
                "rate": top_page["rate"],
                "lang": "",
                "page": top_page["page"],
            }
        )
    return rows


def write_csv_report(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["scope", "stage", "count", "rate", "lang", "page"],
        )
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown_report(
    logfiles: list[Path],
    events_count: int,
    filter_label: str,
    conversion_counts: dict[str, int],
    lang_counters: dict[str, Counter[str]],
    page_counters: dict[str, Counter[str]],
    page_metrics: list[dict[str, Any]],
    lang_metrics: list[dict[str, Any]],
    top_page: dict[str, Any] | None,
) -> str:
    started = conversion_counts["chat_started"]
    summary_rows = [
        [stage, str(conversion_counts[stage]), format_ratio(conversion_counts[stage], started)]
        for stage in CONVERSION_STEPS
    ]

    lines = [
        "# Chat Conversion Report",
        "",
        f"- Logdateien: {', '.join(path.name for path in logfiles)}",
        f"- Auswertbare Events: {events_count}",
        f"- Zeitraum: {filter_label}",
        "",
        "## Summary",
        markdown_table(["stage", "count", "rate"], summary_rows),
        "",
        "## Language Conversion Rates",
    ]

    if lang_metrics:
        lines.append(markdown_table(["lang", "stage", "count", "rate"], [[item["lang"], item["stage"], str(item["count"]), item["rate"]] for item in lang_metrics]))
    else:
        lines.append("Keine Sprachquoten verfuegbar.")

    lines.extend(
        [
            "",
            "## Page Conversion Metrics",
        ]
    )

    if page_metrics:
        lines.append(markdown_table(["page", "stage", "count", "rate"], [[item["page"], item["stage"], str(item["count"]), item["rate"]] for item in page_metrics]))
    else:
        lines.append("Keine Seitenmetriken verfuegbar.")

    lines.extend(
        [
            "",
            "## Top Converting Page",
        ]
    )

    if top_page:
        lines.append(markdown_table(["page", "stage", "count", "rate"], [[top_page["page"], top_page["stage"], str(top_page["count"]), top_page["rate"]]]))
    else:
        lines.append("Keine Top-Converting-Page verfuegbar.")

    lines.extend(
        [
            "",
        "## By Language",
        ]
    )

    for stage in CONVERSION_STEPS:
        rows = [[lang, str(count)] for lang, count in sorted(lang_counters[stage].items(), key=lambda item: (-item[1], item[0]))]
        if not rows:
            rows = [["-", "0"]]
        lines.extend(
            [
                "",
                f"### {stage}",
                markdown_table(["lang", "count"], rows),
            ]
        )

    lines.append("")
    lines.append("## By Page")
    for stage in CONVERSION_STEPS:
        rows = [[page, str(count)] for page, count in sorted(page_counters[stage].items(), key=lambda item: (-item[1], item[0]))]
        if not rows:
            rows = [["-", "0"]]
        lines.extend(
            [
                "",
                f"### {stage}",
                markdown_table(["page", "count"], rows),
            ]
        )

    return "\n".join(lines) + "\n"


def write_markdown_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_page_metrics(page_counters: dict[str, Counter[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started_counter = page_counters["chat_started"]
    for page, started_count in sorted(started_counter.items(), key=lambda item: (-item[1], item[0])):
        leads_count = page_counters["lead_created"].get(page, 0)
        rows.append(
            {
                "page": page,
                "stage": "bounce_rate",
                "count": started_count - leads_count,
                "rate": format_ratio(started_count - leads_count, started_count),
            }
        )
        rows.append(
            {
                "page": page,
                "stage": "lead_conversion_rate",
                "count": leads_count,
                "rate": format_ratio(leads_count, started_count),
            }
        )
    return rows


def build_lang_metrics(lang_counters: dict[str, Counter[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started_counter = lang_counters["chat_started"]
    for lang, started_count in sorted(started_counter.items(), key=lambda item: (-item[1], item[0])):
        for stage in ("entered_price_flow", "contact_intent", "lead_created"):
            count = lang_counters[stage].get(lang, 0)
            rows.append(
                {
                    "lang": lang,
                    "stage": stage,
                    "count": count,
                    "rate": format_ratio(count, started_count),
                }
            )
    return rows


def find_top_converting_page(page_counters: dict[str, Counter[str]]) -> dict[str, Any] | None:
    started_counter = page_counters["chat_started"]
    best_page: dict[str, Any] | None = None
    for page, started_count in started_counter.items():
        if started_count <= 0:
            continue
        leads_count = page_counters["lead_created"].get(page, 0)
        rate = ratio_value(leads_count, started_count) or 0.0
        candidate = {
            "page": page,
            "stage": "lead_conversion_rate",
            "count": leads_count,
            "rate": f"{rate:.1f}%",
            "_rate_numeric": rate,
            "_started": started_count,
        }
        if best_page is None or candidate["_rate_numeric"] > best_page["_rate_numeric"] or (
            candidate["_rate_numeric"] == best_page["_rate_numeric"] and candidate["_started"] > best_page["_started"]
        ):
            best_page = candidate
    if best_page:
        best_page.pop("_rate_numeric", None)
        best_page.pop("_started", None)
    return best_page


def main() -> int:
    args = parse_args()
    logfiles = [Path(path) for path in args.logfiles] if args.logfiles else default_logfiles()
    events = load_events(logfiles)

    if not logfiles:
        print("Keine Logdateien gefunden.")
        return 1

    try:
        events = filter_events_by_date(
            events,
            report_date=args.report_date,
            last_days=args.last_days,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    if args.report_date:
        filter_label = args.report_date
    elif args.last_days is not None:
        filter_label = f"letzte {args.last_days} Tage (UTC)"
    else:
        filter_label = "gesamt"

    if not events:
        print("Keine auswertbaren JSON-Chat-Events gefunden.")
        print("Gepruefte Dateien:")
        for logfile in logfiles:
            print(f"  {logfile}")
        return 1

    conversation_meta: dict[str, dict[str, str]] = defaultdict(dict)
    conversion_conversations: dict[str, set[str]] = {step: set() for step in CONVERSION_STEPS}
    conversion_events: dict[str, int] = {step: 0 for step in CONVERSION_STEPS}
    leads_without_conversation = 0

    for event in events:
        conversation_id = conversation_key(event)
        if conversation_id:
            for field in ("lang", "page", "source"):
                value = event.get(field)
                if isinstance(value, str) and value.strip():
                    conversation_meta[conversation_id][field] = value.strip()

        if event.get("event") != "chat_conversion":
            continue

        step = event.get("conversion_step")
        if step not in CONVERSION_STEPS:
            continue

        conversion_events[step] += 1
        if conversation_id:
            conversion_conversations[step].add(conversation_id)
        elif step == "lead_created":
            leads_without_conversation += 1

    started = len(conversion_conversations["chat_started"])
    entered_price_flow = len(conversion_conversations["entered_price_flow"])
    contact_intent = len(conversion_conversations["contact_intent"])
    lead_created = len(conversion_conversations["lead_created"]) + leads_without_conversation
    conversion_counts = {
        "chat_started": started,
        "entered_price_flow": entered_price_flow,
        "contact_intent": contact_intent,
        "lead_created": lead_created,
    }

    print("Chat Conversion Summary")
    print(f"Logdateien: {', '.join(path.name for path in logfiles)}")
    print(f"Auswertbare Events: {len(events)}")
    print(f"Zeitraum: {filter_label}")
    print()
    print("Conversion-Stufen")
    print(f"  chat_started: {conversion_counts['chat_started']}")
    print(f"  entered_price_flow: {conversion_counts['entered_price_flow']}")
    print(f"  contact_intent: {conversion_counts['contact_intent']}")
    print(f"  lead_created: {conversion_counts['lead_created']}")
    print()
    print("Conversion-Quoten")
    print(f"  chat_started -> entered_price_flow: {format_ratio(conversion_counts['entered_price_flow'], started)}")
    print(f"  chat_started -> contact_intent: {format_ratio(conversion_counts['contact_intent'], started)}")
    print(f"  chat_started -> lead_created: {format_ratio(conversion_counts['lead_created'], started)}")

    lang_counters: dict[str, Counter[str]] = {step: Counter() for step in CONVERSION_STEPS}
    page_counters: dict[str, Counter[str]] = {step: Counter() for step in CONVERSION_STEPS}

    for step, conversation_ids in conversion_conversations.items():
        for conversation_id in conversation_ids:
            meta = conversation_meta.get(conversation_id, {})
            lang_counters[step][meta.get("lang", "-")] += 1
            page_counters[step][meta.get("page", "-")] += 1

    print()
    print("Nach Sprache")
    for step in CONVERSION_STEPS:
        print_counter(f"  {step}", lang_counters[step])

    print()
    print("Nach Seite")
    for step in CONVERSION_STEPS:
        print_counter(f"  {step}", page_counters[step])

    page_metrics = build_page_metrics(page_counters)
    lang_metrics = build_lang_metrics(lang_counters)
    top_page = find_top_converting_page(page_counters)

    print()
    print("Seitenmetriken")
    if page_metrics:
        for item in page_metrics:
            print(f"  {item['page']} -> {item['stage']}: {item['count']} ({item['rate']})")
    else:
        print("  -")

    print()
    print("Sprachquoten")
    if lang_metrics:
        for item in lang_metrics:
            print(f"  {item['lang']} -> {item['stage']}: {item['count']} ({item['rate']})")
    else:
        print("  -")

    print()
    print("Top Converting Page")
    if top_page:
        print(f"  {top_page['page']}: {top_page['count']} ({top_page['rate']})")
    else:
        print("  -")

    print()
    print("Roh-Event-Anzahl")
    for step in CONVERSION_STEPS:
        print(f"  {step}: {conversion_events[step]}")

    if leads_without_conversation:
        print()
        print(f"Lead-Events ohne conversation_id: {leads_without_conversation}")

    csv_rows = build_csv_rows(conversion_counts, lang_counters, page_counters, page_metrics, lang_metrics, top_page)
    if args.csv_path:
        csv_path = Path(args.csv_path)
        write_csv_report(csv_path, csv_rows)
        print()
        print(f"CSV-Report geschrieben: {csv_path}")

    if args.md_path:
        md_path = Path(args.md_path)
        markdown = build_markdown_report(
            logfiles,
            len(events),
            filter_label,
            conversion_counts,
            lang_counters,
            page_counters,
            page_metrics,
            lang_metrics,
            top_page,
        )
        write_markdown_report(md_path, markdown)
        print(f"Markdown-Report geschrieben: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
