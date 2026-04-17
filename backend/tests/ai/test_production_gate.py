"""
Production regression gate for the pricing and intent layer.

Exit code 0 means all checks passed.
Exit code 1 means at least one regression was detected.
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ai import get_pricing_tool


class TestGate:
    """Production readiness test gate."""

    def __init__(self):
        self.tool = get_pricing_tool()
        self.results: list[tuple[str, str, str]] = []
        self.passed = 0
        self.failed = 0

    def log_test(self, name: str, passed: bool, details: str = "") -> None:
        status = "OK" if passed else "FAIL"
        self.results.append((status, name, details))
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def test_pillar_1_intent_classification(self) -> None:
        print("\n" + "=" * 80)
        print("PILLAR 1: INTENT CLASSIFICATION TESTS")
        print("=" * 80)

        groups = {
            "UMZUG": [
                ("Ich ziehe von Kiel nach Berlin um", "umzug"),
                ("Was kostet ein Umzug von Hamburg nach München?", "umzug"),
                ("Umzugsangebot bitte", "umzug"),
                ("5 Zimmer von Ost nach West", "umzug"),
                ("Wir ziehen nächsten Monat", "umzug"),
            ],
            "ENTSORGUNG": [
                ("Ich möchte 3 Sofas entsorgen", "entsorgung"),
                ("Entrümpelung einer Wohnung", "entsorgung"),
                ("Was kostet die Entsorgung von Möbeln?", "entsorgung"),
                ("Stickmaschine 450kg wegschmeissen", "entsorgung"),
                ("Entrümplung im Keller", "entsorgung"),
            ],
            "LAMINAT": [
                ("Laminat 50m² abbauen und entsorgen", "laminat"),
                ("Was kostet Laminatabau in Hamburg?", "laminat"),
                ("Parkett entfernen und entsorgen", "laminat"),
                ("Flooring abbau 75 qm", "laminat"),
                ("Bodenbelag entfernung", "laminat"),
            ],
            "MOEBELMONTAGE": [
                ("IKEA Regal aufbauen in meiner Wohnung", "moebelmontage"),
                ("Möbelmontage Küche 4m Unterschrank", "moebelmontage"),
                ("Was kostet Möbelaufbau?", "moebelmontage"),
                ("Schrank abbau und neue Montage", "moebelmontage"),
                ("Regale aufbauen lassen", "moebelmontage"),
            ],
            "EINZELTRANSPORT": [
                ("Waschmaschine transportieren", "einzeltransport"),
                ("Kühlschrank von Kiel nach Hamburg", "einzeltransport"),
                ("Sofa einzeln mitnehmen", "einzeltransport"),
                ("Clavinova Klavier Transport", "einzeltransport"),
                ("Safe transport", "einzeltransport"),
            ],
        }

        for label, cases in groups.items():
            print(f"\n{label}:")
            for text, expected in cases:
                intent = self.tool.classify_user_message(text)
                passed = intent.service_type == expected
                self.log_test(f"{label}: {text[:35]}", passed, intent.service_type or "None")
                status = "OK" if passed else "FAIL"
                print(f"  {status:4} {text[:55]} -> {intent.service_type}")

    def test_pillar_2_pricing_consistency(self) -> None:
        print("\n" + "=" * 80)
        print("PILLAR 2: PRICING CONSISTENCY TESTS")
        print("=" * 80)

        print("\nDETERMINISM:")
        test_cases = [
            ("entsorgung", {"item_type": "3 Sofas", "location": "Kiel"}),
            ("laminat", {"area_m2": 50, "location": "Hamburg"}),
            ("moebelmontage", {"furniture_type": "IKEA Regal", "location": "Berlin"}),
        ]

        for service, details in test_cases:
            p1 = self.tool.calculate_estimated_price(service, details)
            p2 = self.tool.calculate_estimated_price(service, details)
            p3 = self.tool.calculate_estimated_price(service, details)
            deterministic = (
                p1.min_price_eur == p2.min_price_eur == p3.min_price_eur
                and p1.max_price_eur == p2.max_price_eur == p3.max_price_eur
            )
            self.log_test(
                f"Determinism: {service}",
                deterministic,
                f"{p1.min_price_eur}-{p1.max_price_eur} EUR",
            )
            status = "OK" if deterministic else "FAIL"
            print(f"  {status:4} {service}: {p1.min_price_eur}-{p1.max_price_eur} EUR")

        print("\nEXPECTED RANGES:")
        range_tests = [
            ("entsorgung", {"item_type": "Sofa", "location": "Any"}, 50, 100),
            ("entsorgung", {"item_type": "3 Sofas", "location": "Any"}, 120, 200),
            ("laminat", {"area_m2": 50, "location": "Any"}, 400, 650),
            ("moebelmontage", {"furniture_type": "Schrank", "location": "Any"}, 120, 180),
        ]

        for service, details, min_exp, max_exp in range_tests:
            p = self.tool.calculate_estimated_price(service, details)
            in_range = min_exp <= p.min_price_eur <= p.max_price_eur <= max_exp
            self.log_test(
                f"Range: {service}",
                in_range,
                f"{p.min_price_eur}-{p.max_price_eur} EUR",
            )
            status = "OK" if in_range else "FAIL"
            print(f"  {status:4} {service}: {p.min_price_eur}-{p.max_price_eur} EUR")

    def test_pillar_3_missing_fields(self) -> None:
        print("\n" + "=" * 80)
        print("PILLAR 3: MISSING FIELDS AND DEFAULTS")
        print("=" * 80)

        vague_tests = [
            ("preis?", None),
            ("was kostet?", None),
            ("entsorgung ort?", "entsorgung"),
            ("laminat preis", "laminat"),
        ]

        print("\nNO FALSE UMZUG DEFAULT:")
        for text, expected_service in vague_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == expected_service
            self.log_test(
                f"No Umzug default: {text[:25]}",
                passed,
                intent.service_type or "None",
            )
            status = "OK" if passed else "FAIL"
            print(f"  {status:4} '{text}' -> {intent.service_type}")

        print("\nREQUIRED FIELDS:")
        field_tests = [
            ("entsorgung", ["location", "item_type"]),
            ("laminat", ["location", "area_m2"]),
            ("moebelmontage", ["location", "furniture_type"]),
            ("umzug", ["from_city", "to_city"]),
        ]

        for service_type, expected_fields in field_tests:
            service = self.tool.get_service_info(service_type)
            passed = all(field in service.required_fields for field in expected_fields)
            self.log_test(
                f"Required fields: {service_type}",
                passed,
                f"{service.required_fields}",
            )
            status = "OK" if passed else "FAIL"
            print(f"  {status:4} {service_type}: {service.required_fields}")

    def test_pillar_4_conversation_switch(self) -> None:
        print("\n" + "=" * 80)
        print("PILLAR 4: CONVERSATION SWITCH TESTS")
        print("=" * 80)

        scenarios = [
            (
                "Umzug -> Entsorgung switch",
                ["Ich ziehe um", "Nein, eigentlich nur entsorgen"],
                "entsorgung",
            ),
            (
                "Entsorgung -> Laminat switch",
                ["Ich brauche Entsorgung", "Warte, eher Laminat abbauen"],
                "laminat",
            ),
            (
                "Generic -> Specific switch",
                ["Was kostet ihr?", "Für Laminat 100m²"],
                "laminat",
            ),
        ]

        print("\nINTENT SWITCHES:")
        for name, messages, expected in scenarios:
            last_intent = None
            for msg in messages:
                last_intent = self.tool.classify_user_message(msg)
            passed = last_intent.service_type == expected
            self.log_test(name, passed, last_intent.service_type or "None")
            status = "OK" if passed else "FAIL"
            print(f"  {status:4} {name} -> {last_intent.service_type}")

        print("\nMETA QUESTIONS:")
        meta_tests = [
            "Warum fragst du mich das?",
            "Das macht keinen Sinn",
            "Das passt nicht",
        ]
        for text in meta_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.intent_type is not None
            self.log_test(f"Meta-Q: {text[:25]}", passed, intent.intent_type)
            status = "OK" if passed else "FAIL"
            print(f"  {status:4} '{text}' -> {intent.intent_type}")

    def print_report(self) -> bool:
        print("\n" + "#" * 80)
        print("FINAL TEST GATE REPORT")
        print("#" * 80)

        total = self.passed + self.failed
        percentage = (self.passed / total * 100) if total else 0.0
        print(f"\nResults: {self.passed}/{total} tests passed ({percentage:.1f}%)")

        if self.failed > 0:
            print(f"\nFAILED TESTS ({self.failed}):")
            for status, name, details in self.results:
                if status == "FAIL":
                    print(f"   {name}: {details}")

        print("\n" + "=" * 80)
        if self.failed == 0:
            print("GO/NO-GO DECISION: GO LIVE")
            print("   All checks passed. Production deployment approved.")
            return True

        print("GO/NO-GO DECISION: DO NOT DEPLOY")
        print("   At least one regression was detected and should be fixed first.")
        return False

    def run_all_tests(self) -> bool:
        print("\n" + "#" * 80)
        print("PRODUCTION TEST GATE - STARTING")
        print("#" * 80)

        self.test_pillar_1_intent_classification()
        self.test_pillar_2_pricing_consistency()
        self.test_pillar_3_missing_fields()
        self.test_pillar_4_conversation_switch()
        return self.print_report()


def main() -> None:
    gate = TestGate()
    success = gate.run_all_tests()

    print("\n" + "#" * 80)
    if success:
        print("TEST GATE PASSED - READY FOR DEPLOYMENT")
        print("#" * 80)
        sys.exit(0)

    print("TEST GATE FAILED - DO NOT DEPLOY YET")
    print("#" * 80)
    sys.exit(1)


if __name__ == "__main__":
    main()
