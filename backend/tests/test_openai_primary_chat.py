import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app.ai.agent as agent
from app.ai.schemas import ChatTurn


class _DummySession:
    def close(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.output_text = text


class _FakeResponses:
    def __init__(self, *, text: str) -> None:
        self.text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self.text)


class _FakeClient:
    def __init__(self, *, text: str) -> None:
        self.responses = _FakeResponses(text=text)


class OpenAiPrimaryChatTest(unittest.TestCase):
    def _session_factory(self):
        return _DummySession()

    def _messages(self) -> list[ChatTurn]:
        return [
            ChatTurn(role="user", content="Ich ziehe von Kiel nach Hamburg um"),
            ChatTurn(role="user", content="3 Zimmer"),
            ChatTurn(role="user", content="90 km"),
        ]

    def test_company_pricing_is_authoritative_for_move_estimate(self) -> None:
        fake_client = _FakeClient(text="OpenAI finale Antwort")
        trace = {}

        with patch.object(agent, "get_dode_client", return_value=fake_client):
            reply = agent.generate_dode_reply(
                messages=self._messages(),
                page="/umzugsrechner.html",
                lang="de",
                session_factory=self._session_factory,
                assigned_price_calculator=lambda *_args, **_kwargs: 420,
                logger=None,
                request_id="req_test_primary",
                conversation_id="conv_test_primary",
                trace=trace,
            )

        self.assertIn("unverbindliche Schaetzung", reply)
        self.assertIn("560", reply)
        self.assertIn("690", reply)
        self.assertIsNone(fake_client.responses.last_kwargs)
        self.assertEqual("forced_helper_reply", trace.get("response_origin"))

    def test_helper_fallback_is_used_when_openai_client_fails(self) -> None:
        with patch.object(
            agent,
            "get_dode_client",
            side_effect=HTTPException(status_code=503, detail="not configured"),
        ):
            reply = agent.generate_dode_reply(
                messages=self._messages(),
                page="/umzugsrechner.html",
                lang="de",
                session_factory=self._session_factory,
                assigned_price_calculator=lambda *_args, **_kwargs: 420,
                logger=None,
                request_id="req_test_fallback",
                conversation_id="conv_test_fallback",
            )

        self.assertIn("unverbindliche Schaetzung", reply)
        self.assertIn("560", reply)
        self.assertIn("690", reply)


if __name__ == "__main__":
    unittest.main()
