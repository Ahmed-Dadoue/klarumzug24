import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app.ai.agent as agent
from app.ai.company_pricing import (
    PricingV2Input,
    build_company_pricing_helper_payload,
    estimate_company_price_v2,
    extract_pricing_v2_input_from_messages,
)
from app.ai.schemas import ChatTurn


class _DummySession:
    def close(self) -> None:
        return None


class CompanyPricingV2Test(unittest.TestCase):
    def _session_factory(self):
        return _DummySession()

    def test_arbeitsplatte_only_uses_minimum_extra_hours_cutouts_and_distance(self) -> None:
        estimate = estimate_company_price_v2(
            PricingV2Input(
                service_type="arbeitsplatte_only",
                distance_km=20,
                difficulty="medium",
                sink_cutout=True,
                cooktop_cutout=True,
            )
        )

        self.assertEqual("time_and_distance", estimate.pricing_model)
        self.assertEqual(310, estimate.price_min_eur)
        self.assertEqual(400, estimate.price_max_eur)
        self.assertEqual(1, estimate.workers_total)
        self.assertEqual((), estimate.missing_fields)

    def test_transporter_uses_250_minimum(self) -> None:
        estimate = estimate_company_price_v2(
            PricingV2Input(
                service_type="einzeltransport",
                distance_km=10,
                estimated_hours_min=1,
                estimated_hours_max=1,
                needs_transporter=True,
            )
        )

        self.assertEqual(260, estimate.price_min_eur)
        self.assertEqual(260, estimate.price_max_eur)
        self.assertTrue(estimate.needs_transporter)

    def test_helpers_are_billed_per_hour(self) -> None:
        estimate = estimate_company_price_v2(
            PricingV2Input(
                service_type="transporthilfe",
                distance_km=0,
                estimated_hours_min=4,
                estimated_hours_max=4,
                workers_total=3,
                needs_transporter=False,
            )
        )

        self.assertEqual(480, estimate.price_min_eur)
        self.assertEqual(480, estimate.price_max_eur)
        self.assertEqual(2, estimate.helpers_count)

    def test_missing_information_returns_follow_up_not_price(self) -> None:
        estimate = estimate_company_price_v2(
            PricingV2Input(service_type="arbeitsplatte_only")
        )

        self.assertIsNone(estimate.price_min_eur)
        self.assertIn("ort_oder_entfernung_ab_bordesholm", estimate.missing_fields)
        self.assertIn("Arbeitsplatte", estimate.explanation_de)

    def test_entruempelung_is_company_pricing_service(self) -> None:
        estimate = estimate_company_price_v2(
            PricingV2Input(
                service_type="entruempelung",
                distance_km=20,
                rooms=2,
            )
        )

        self.assertEqual("time_and_distance", estimate.pricing_model)
        self.assertEqual(2, estimate.workers_total)
        self.assertTrue(estimate.needs_transporter)
        self.assertEqual((), estimate.missing_fields)
        self.assertIsNotNone(estimate.price_min_eur)
        self.assertIsNotNone(estimate.price_max_eur)
        self.assertIn("Entruempelung", estimate.explanation_de)

    def test_dode_detects_clearance_terms_as_pricing_v2(self) -> None:
        payload = build_company_pricing_helper_payload(
            [
                ChatTurn(
                    role="user",
                    content="Was kostet eine Haushaltsaufloesung mit 2 Zimmern, 20 km ab Bordesholm?",
                )
            ],
            lang="de",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("haushaltsaufloesung", payload["truth_meta"]["truth_key"])
        self.assertEqual("company_pricing_v2", payload["truth_meta"]["pricing_source"])
        self.assertEqual(2, payload["truth_meta"]["workers_total"])
        self.assertTrue(payload["truth_meta"]["needs_transporter"])

    def test_latest_route_overrides_old_bordesholm_context(self) -> None:
        payload = build_company_pricing_helper_payload(
            [
                ChatTurn(role="user", content="Ich bin in Bordesholm im Erdgeschoss."),
                ChatTurn(
                    role="user",
                    content=(
                        "Von Kiel nach Stuttgart, nur zwei Zimmer, Wohnzimmer und Schlafzimmer, "
                        "etwa 10 Kartons, Transporter noetig, kein Aufzug, 1. Etage, Termin 28.04.2026. "
                        "Kannst du mir den ungefaehren Preis nennen?"
                    ),
                ),
            ],
            lang="de",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("umzug", payload["truth_meta"]["truth_key"])
        self.assertGreater(payload["truth_meta"]["distance_km"], 500)
        self.assertGreater(payload["truth_meta"]["price_min_eur"], 1000)
        self.assertEqual([], payload["truth_meta"]["missing_fields"])

    def test_route_without_umzug_word_is_detected_as_move(self) -> None:
        pricing_input = extract_pricing_v2_input_from_messages(
            [
                ChatTurn(
                    role="user",
                    content="Von Kiel nach Stuttgart, zwei Zimmer, 10 Kartons und Transporter.",
                )
            ]
        )

        self.assertIsNotNone(pricing_input)
        assert pricing_input is not None
        self.assertEqual("umzug", pricing_input.service_type)
        self.assertEqual(735.0, pricing_input.distance_km)
        self.assertEqual(2, pricing_input.rooms)
        self.assertEqual(10, pricing_input.cartons)

    def test_unknown_explicit_route_does_not_fall_back_to_local_city(self) -> None:
        payload = build_company_pricing_helper_payload(
            [
                ChatTurn(
                    role="user",
                    content="Von Kiel nach Bremen, zwei Zimmer, 10 Kartons und Transporter. Was kostet das?",
                )
            ],
            lang="de",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("umzug", payload["truth_meta"]["truth_key"])
        self.assertIsNone(payload["truth_meta"]["distance_km"])
        self.assertIn("ort_oder_entfernung_ab_bordesholm", payload["truth_meta"]["missing_fields"])

    def test_large_furniture_and_kitchen_assembly_gets_price_range(self) -> None:
        payload = build_company_pricing_helper_payload(
            [
                ChatTurn(
                    role="user",
                    content=(
                        "Wir brauchen in Kiel den Aufbau neuer Moebel, zwei Kuechen montieren, "
                        "etwa 150 Schreibtische, 3 Etagen, Aufzug vorhanden, kein Transport noetig, "
                        "alles bis 30.04.2026 fertig."
                    ),
                ),
                ChatTurn(
                    role="user",
                    content="Nenne mir die Kosten, ich habe es eilig. 7 Helfer oder 10 Helfer sind gut?",
                ),
            ],
            lang="de",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("moebelmontage", payload["truth_meta"]["truth_key"])
        self.assertFalse(payload["truth_meta"]["needs_transporter"])
        self.assertEqual(7, payload["truth_meta"]["workers_total"])
        self.assertGreater(payload["truth_meta"]["price_min_eur"], 2000)
        self.assertEqual([], payload["truth_meta"]["missing_fields"])
        self.assertIn("unverbindliche Schaetzung", payload["fallback_reply"])

    def test_dode_uses_company_pricing_v2_fallback(self) -> None:
        messages = [
            ChatTurn(
                role="user",
                content=(
                    "Ich brauche nur Arbeitsplatte, 20 km von Bordesholm, "
                    "mit Spuele und Kochfeld."
                ),
            )
        ]

        with patch.object(
            agent,
            "get_dode_client",
            side_effect=HTTPException(status_code=503, detail="not configured"),
        ):
            reply = agent.generate_dode_reply(
                messages=messages,
                page="/kontakt.html",
                lang="de",
                session_factory=self._session_factory,
                assigned_price_calculator=lambda *_args, **_kwargs: 420,
                logger=None,
                request_id="req_pricing_v2",
                conversation_id="conv_pricing_v2",
            )

        self.assertIn("unverbindliche Schaetzung", reply)
        self.assertIn("310", reply)
        self.assertIn("400", reply)


if __name__ == "__main__":
    unittest.main()
