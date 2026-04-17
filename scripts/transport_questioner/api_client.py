from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .models import BotResponse, ChatTurn, QuestionerConfig


def _get_by_path(payload: Any, path: str | None) -> Any:
    if not path:
        return None
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _search_common_reply_fields(payload: Any) -> str | None:
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, dict):
        common_paths = [
            ("reply",),
            ("response",),
            ("answer",),
            ("message",),
            ("data", "reply"),
            ("data", "response"),
            ("data", "answer"),
            ("data", "message"),
            ("choices",),
        ]
        for path in common_paths:
            current: Any = payload
            for part in path:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = None
                    break
            if isinstance(current, str) and current.strip():
                return current.strip()
            if isinstance(current, list) and current and isinstance(current[0], dict):
                for candidate in current:
                    if isinstance(candidate.get("message"), dict):
                        content = candidate["message"].get("content")
                        if isinstance(content, str) and content.strip():
                            return content.strip()
    return None


class BlackBoxChatbotClient:
    def __init__(self, config: QuestionerConfig) -> None:
        self.config = config

    def send(self, *, conversation_id: str, turns: list[ChatTurn]) -> BotResponse:
        payload = self._build_payload(conversation_id=conversation_id, turns=turns)
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            **self.config.chatbot_extra_headers,
        }
        if self.config.chatbot_api_key:
            if self.config.chatbot_api_header.lower() == "authorization":
                headers[self.config.chatbot_api_header] = f"Bearer {self.config.chatbot_api_key}"
            else:
                headers[self.config.chatbot_api_header] = self.config.chatbot_api_key

        request = urllib.request.Request(
            self.config.chatbot_api_url,
            data=data,
            headers=headers,
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.config.chatbot_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                try:
                    raw_payload: Any = json.loads(raw_body)
                except json.JSONDecodeError:
                    raw_payload = raw_body
                text = self._extract_text(raw_payload)
                return BotResponse(
                    text=text,
                    status_code=getattr(response, "status", 200),
                    raw_payload=raw_payload,
                    latency_ms=latency_ms,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            raise RuntimeError(f"Chatbot API HTTP {exc.code}: {body[:400]} ({latency_ms} ms)") from exc
        except urllib.error.URLError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            raise RuntimeError(f"Chatbot API nicht erreichbar: {exc.reason} ({latency_ms} ms)") from exc

    def _build_payload(self, *, conversation_id: str, turns: list[ChatTurn]) -> dict[str, Any]:
        payload = {
            "conversation_id": conversation_id,
            "lang": self.config.lang,
            **self.config.chatbot_extra_payload,
        }
        if self.config.chatbot_request_mode == "last_message":
            last_user_message = next((turn.content for turn in reversed(turns) if turn.role == "user"), "")
            payload["message"] = last_user_message
        else:
            payload["messages"] = [{"role": turn.role, "content": turn.content} for turn in turns]
        return payload

    def _extract_text(self, raw_payload: Any) -> str:
        path_value = _get_by_path(raw_payload, self.config.chatbot_response_text_path)
        if isinstance(path_value, str) and path_value.strip():
            return path_value.strip()

        text = _search_common_reply_fields(raw_payload)
        if text:
            return text

        return json.dumps(raw_payload, ensure_ascii=True)[:1000]
