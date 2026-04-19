import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app.ai.agent as agent
from app.ai.company_pricing import (
    PricingV2Input,
    build_company_pricing_helper_payload,
    estimate_company_price_v2,
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
