import unittest
from unittest.mock import Mock, patch

from app.ai.agent import generate_dode_reply
from app.ai.company_pricing import extract_pricing_v2_input_from_messages
from app.ai.schemas import ChatTurn
from app.core.database import SessionLocal


class DodeProfessionalWorkflowTest(unittest.TestCase):
    def test_generic_help_request_uses_intake_instead_of_random_faq(self) -> None:
        trace = {}
        with patch("app.ai.agent.build_insights_prompt_block", return_value=""), patch(
            "app.ai.agent.get_dode_client"
        ) as client_mock:
            reply = generate_dode_reply(
                messages=[
                    ChatTurn(
                        role="user",
                        content="Hallo, ich brauche Hilfe. Kannst du mir helfen?",
                    )
                ],
                page="/index.html",
                lang="de",
                session_factory=SessionLocal,
                assigned_price_calculator=Mock(),
                logger=Mock(),
                trace=trace,
            )

        client_mock.assert_not_called()
        self.assertIn("Worum geht es genau", reply)
        self.assertIn("Kuechenmontage", reply)
        self.assertNotIn("Halteverbotszone", reply)
        self.assertEqual("forced_helper_reply", trace.get("response_origin"))

    def test_kitchen_appliance_words_do_not_create_fake_cutouts(self) -> None:
        pricing_input = extract_pricing_v2_input_from_messages(
            [
                ChatTurn(
                    role="user",
                    content="Nein, ich habe K\u00fcchen montiert und das hat nicht geklappt.",
                ),
                ChatTurn(role="user", content="es handelt sich um einen Aufbau"),
                ChatTurn(role="user", content="In L\u00fcttbarten 8b 24582 Bordesholm"),
                ChatTurn(
                    role="user",
                    content="4 Schraenke, ein Herd, ein Ofen und eine Spuelmaschine",
                ),
                ChatTurn(role="user", content="5 m"),
            ]
        )

        self.assertIsNotNone(pricing_input)
        assert pricing_input is not None
        self.assertEqual("kuechenmontage", pricing_input.service_type)
        self.assertEqual(5.0, pricing_input.kitchen_meters)
        self.assertEqual(0.0, pricing_input.distance_km)
        self.assertFalse(pricing_input.sink_cutout)
        self.assertFalse(pricing_input.cooktop_cutout)

    def test_session_context_note_preserves_long_move_details(self) -> None:
        pricing_input = extract_pricing_v2_input_from_messages(
            [
                ChatTurn(
                    role="user",
                    content=(
                        "KONTEXTNOTIZ aus dieser laufenden Chat-Sitzung, nur als Gedaechtnis nutzen. "
                        "Bekannte strukturierte Angaben: Leistungen: Umzug/Transport, Verpacken/Vorbereiten, "
                        "Entsorgung; Route: von Kiel nach Stuttgart; Umfang: 2 Zimmer; Kartons: ca. 10; "
                        "Zugang: 1. Etage; Zugang: kein Aufzug; Fahrzeug: Transporter benoetigt; "
                        "Wunschtermin: 28.04.2026; Kundenwunsch: weibliche Helferin."
                    ),
                ),
                ChatTurn(role="assistant", content="Wie kann ich Ihnen weiterhelfen?"),
                ChatTurn(role="user", content="Wie viel wuerde alles insgesamt kosten?"),
            ]
        )

        self.assertIsNotNone(pricing_input)
        assert pricing_input is not None
        self.assertEqual("umzug", pricing_input.service_type)
        self.assertEqual(2, pricing_input.rooms)
        self.assertEqual(10, pricing_input.cartons)
        self.assertEqual(1, pricing_input.floor_from)
        self.assertFalse(pricing_input.elevator_from)
        self.assertTrue(pricing_input.needs_transporter)


if __name__ == "__main__":
    unittest.main()
