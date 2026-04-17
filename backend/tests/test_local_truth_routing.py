import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app.ai.agent as agent
from app.ai.faq_store import find_best_faq_match
from app.ai.schemas import ChatTurn
from app.ai.service_registry import find_best_service_truth


class _DummySession:
    def close(self) -> None:
        return None


class LocalTruthRoutingTest(unittest.TestCase):
    def _session_factory(self):
        return _DummySession()

    def test_policy_truth_handles_cancellation_without_openai(self) -> None:
        with patch.object(
            agent,
            "get_dode_client",
            side_effect=HTTPException(status_code=503, detail="not configured"),
        ):
            reply = agent.generate_dode_reply(
                messages=[ChatTurn(role="user", content="Kann ich den Umzug noch stornieren?")],
                page="/kontakt.html",
                lang="de",
                session_factory=self._session_factory,
                assigned_price_calculator=lambda *_args, **_kwargs: 420,
                logger=None,
                request_id="req_truth_cancel",
                conversation_id="conv_truth_cancel",
            )

        self.assertIn("48 Stunden", reply)
        self.assertIn("/agb.html", reply)

    def test_unconfirmed_laminat_pricing_does_not_invent_price(self) -> None:
        with patch.object(
            agent,
            "get_dode_client",
            side_effect=HTTPException(status_code=503, detail="not configured"),
        ):
            reply = agent.generate_dode_reply(
                messages=[ChatTurn(role="user", content="Was kostet Laminat entfernen in Kiel?")],
                page="/kontakt.html",
                lang="de",
                session_factory=self._session_factory,
                assigned_price_calculator=lambda *_args, **_kwargs: 420,
                logger=None,
                request_id="req_truth_laminat",
                conversation_id="conv_truth_laminat",
            )

        self.assertIn("nicht als klare Standardleistung bestaetigt", reply)
        self.assertIn("Kein Chat-Preis", reply)
        self.assertNotIn("EUR", reply)

    def test_service_registry_finds_packaging_service(self) -> None:
        match = find_best_service_truth("Bietet ihr Verpackungsservice und Kartons an?", lang="de")
        self.assertIsNotNone(match)
        self.assertEqual("verpackung", match["key"])

    def test_faq_retrieval_handles_looser_cancellation_phrase(self) -> None:
        match = find_best_faq_match("Kann man spaeter noch absagen, wenn etwas dazwischenkommt?", lang="de")
        self.assertIsNotNone(match)
        self.assertEqual("legal_005", match["item"]["id"])


if __name__ == "__main__":
    unittest.main()
