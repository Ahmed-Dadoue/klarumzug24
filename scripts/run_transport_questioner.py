from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.transport_questioner.domain import PERSONA_LIBRARY, load_persona
from scripts.transport_questioner.runner import TransportQuestionerRunner, build_config, load_objective
from scripts.transport_questioner.scenario import load_scenario


def _json_arg(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Ungueltiges JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON-Wert muss ein Objekt sein.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone Black-Box Transport Questioner gegen einen externen Chatbot per API."
    )
    parser.add_argument("--api-url", required=True, help="Externe Chatbot-API-URL.")
    parser.add_argument("--scenario-file", required=True, help="Pfad zur Scenario-JSON-Datei.")
    parser.add_argument("--objective-file", required=True, help="Pfad zur Objective-JSON-Datei.")
    parser.add_argument(
        "--persona",
        default="expert_auditor",
        choices=sorted(PERSONA_LIBRARY.keys()),
        help="Branchen-Persona fuer den Testlauf.",
    )
    parser.add_argument("--api-key", default=os.getenv("CHATBOT_API_KEY", ""), help="Optionaler API-Key fuer den externen Chatbot.")
    parser.add_argument("--api-key-header", default="Authorization", help="HTTP-Header fuer den Chatbot-Key.")
    parser.add_argument("--response-path", default="", help="Optionaler JSON-Pfad zur Antwort, z. B. data.reply")
    parser.add_argument(
        "--request-mode",
        default="messages",
        choices=("messages", "last_message"),
        help="Sende kompletten Verlauf oder nur die letzte User-Nachricht.",
    )
    parser.add_argument("--extra-headers-json", type=_json_arg, default={}, help="Optionale zusaetzliche HTTP-Header als JSON.")
    parser.add_argument("--extra-payload-json", type=_json_arg, default={}, help="Optionale zusaetzliche Payload-Felder als JSON.")
    parser.add_argument("--max-turns", type=int, default=8, help="Maximale Turn-Anzahl fuer einen Lauf.")
    parser.add_argument("--lang", default="de", choices=("de", "en"))
    parser.add_argument("--questioner-model", default=os.getenv("QUESTIONER_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--evaluator-model", default=os.getenv("QUESTIONER_EVAL_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = REPO_ROOT
    if not args.openai_api_key.strip():
        raise SystemExit("OPENAI_API_KEY fehlt. Der Questioner nutzt OpenAI als echten Engine und startet ohne Key nicht.")

    config = build_config(
        repo_root=repo_root,
        chatbot_api_url=args.api_url,
        chatbot_api_key=args.api_key,
        chatbot_response_text_path=args.response_path or None,
        chatbot_request_mode=args.request_mode,
        chatbot_extra_headers=args.extra_headers_json,
        chatbot_extra_payload=args.extra_payload_json,
        openai_api_key=args.openai_api_key,
        questioner_model=args.questioner_model,
        evaluator_model=args.evaluator_model,
        max_turns=args.max_turns,
        lang=args.lang,
    )
    config.chatbot_api_header = args.api_key_header

    scenario = load_scenario(args.scenario_file)
    objective = load_objective(args.objective_file)
    persona = load_persona(args.persona)

    runner = TransportQuestionerRunner(config)
    run_log = runner.run(
        scenario=scenario,
        persona=persona,
        objective=objective,
    )

    print(f"Conversation ID: {run_log.conversation_id}")
    print(f"Turns: {len(run_log.turns)}")
    print(f"Stop reason: {run_log.stop_reason}")
    print(f"Output JSON: {run_log.output_path}")
    if run_log.turns:
        last_eval = run_log.turns[-1].evaluation
        print(f"Last evaluation summary: {last_eval.summary}")
        print(f"Detected flags: {', '.join(last_eval.failure_flags()) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
