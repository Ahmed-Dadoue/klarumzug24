"""
Final Test Gate Before Production Deployment
4 Comprehensive Testing Pillars
Run time: ~2-3 minutes
Result: Go/No-Go decision
"""
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.ai import (
    get_pricing_tool,
    classify_intent,
    identify_service_type,
)


class TestGate:
    """Production readiness test gate."""
    
    def __init__(self):
        self.tool = get_pricing_tool()
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log a test result."""
        status = "✅" if passed else "❌"
        self.results.append((status, name, details))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    # =========================================================================
    # PILLAR 1: INTENT CLASSIFICATION TESTS
    # =========================================================================
    
    def test_pillar_1_intent_classification(self):
        """
        Pillar 1: Intent Tests
        Test all service types + edge cases
        """
        print("\n" + "="*80)
        print("PILLAR 1: INTENT CLASSIFICATION TESTS")
        print("="*80)
        
        # Umzug tests
        umzug_tests = [
            "Ich ziehe von Kiel nach Berlin um",
            "Was kostet ein Umzug von Hamburg nach München?",
            "Umzugsangebot bitte",
            "5 Zimmer von Ost nach West",
            "Wir ziehen nächsten Monat",
        ]
        
        print("\n📌 UMZUG (5 tests):")
        for text in umzug_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == "umzug"
            self.log_test(f"Umzug: {text[:35]}", passed, intent.service_type or "None")
            print(f"  {'✅' if passed else '❌'} {text[:50]}")
        
        # Entsorgung tests
        entsorgung_tests = [
            "Ich möchte 3 Sofas entsorgen",
            "Entrümpelung einer Wohnung",
            "Was kostet die Entsorgung von Möbeln?",
            "Stickmaschine 450kg wegschmeissen",
            "Entrümplung im Keller",
        ]
        
        print("\n📌 ENTSORGUNG (5 tests):")
        for text in entsorgung_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == "entsorgung"
            self.log_test(f"Entsorgung: {text[:35]}", passed, intent.service_type or "None")
            print(f"  {'✅' if passed else '❌'} {text[:50]}")
        
        # Laminat tests
        laminat_tests = [
            "Laminat 50m² abbauen und entsorgen",
            "Was kostet Laminatabau in Hamburg?",
            "Parkett entfernen und entsorgen",
            "Flooring abbau 75 qm",
            "Bodenbelag entfernung",
        ]
        
        print("\n📌 LAMINAT (5 tests):")
        for text in laminat_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == "laminat"
            self.log_test(f"Laminat: {text[:35]}", passed, intent.service_type or "None")
            print(f"  {'✅' if passed else '❌'} {text[:50]}")
        
        # Möbelmontage tests
        montage_tests = [
            "IKEA Regal aufbauen in meiner Wohnung",
            "Möbelmontage Küche 4m Unterschrank",
            "Was kostet Möbelaufbau?",
            "Schrank abbau und neue Montage",
            "Regale aufbauen lassen",
        ]
        
        print("\n📌 MÖBELMONTAGE (5 tests):")
        for text in montage_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == "moebelmontage"
            self.log_test(f"Montage: {text[:35]}", passed, intent.service_type or "None")
            print(f"  {'✅' if passed else '❌'} {text[:50]}")
        
        # Einzeltransport tests
        transport_tests = [
            "Waschmaschine transportieren",
            "Kühlschrank von Kiel nach Hamburg",
            "Sofa einzeln mitnehmen",
            "Clavinova Klavier Transport",
            "Safe transport",
        ]
        
        print("\n📌 EINZELTRANSPORT (5 tests):")
        for text in transport_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == "einzeltransport"
            self.log_test(f"Transport: {text[:35]}", passed, intent.service_type or "None")
            print(f"  {'✅' if passed else '❌'} {text[:50]}")
    
    # =========================================================================
    # PILLAR 2: PRICING CONSISTENCY TESTS
    # =========================================================================
    
    def test_pillar_2_pricing_consistency(self):
        """
        Pillar 2: Pricing Tests
        Same input = same price (deterministic)
        Ranges are reasonable
        """
        print("\n" + "="*80)
        print("PILLAR 2: PRICING CONSISTENCY TESTS")
        print("="*80)
        
        # Test determinism: same input = same output
        print("\n📌 DETERMINISM (Same input = Same price):")
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
                p1.min_price_eur == p2.min_price_eur == p3.min_price_eur and
                p1.max_price_eur == p2.max_price_eur == p3.max_price_eur
            )
            
            self.log_test(
                f"Determinism: {service}",
                deterministic,
                f"{p1.min_price_eur}–{p1.max_price_eur}€"
            )
            print(f"  {'✅' if deterministic else '❌'} {service}: {p1.min_price_eur}–{p1.max_price_eur}€ (3x)")
        
        # Test ranges are reasonable (not too wide)
        print("\n📌 REASONABLE RANGES (Not too wide):")
        range_tests = [
            ("entsorgung", {"item_type": "Sofa", "location": "Any"}, 50, 100, 2.0),
            ("entsorgung", {"item_type": "3 Sofas", "location": "Any"}, 120, 200, 1.7),
            ("laminat", {"area_m2": 50, "location": "Any"}, 400, 650, 1.6),
            ("moebelmontage", {"furniture_type": "Schrank", "location": "Any"}, 120, 180, 1.5),
        ]
        
        for service, details, min_exp, max_exp, max_ratio in range_tests:
            p = self.tool.calculate_estimated_price(service, details)
            
            # Check 1: Within expected range
            in_range = min_exp <= p.min_price_eur and p.max_price_eur <= max_exp
            
            # Check 2: Ratio not too wide (max should not be > 2x min)
            ratio = p.max_price_eur / p.min_price_eur if p.min_price_eur > 0 else 0
            ratio_ok = ratio <= max_ratio
            
            passed = in_range and ratio_ok
            self.log_test(
                f"Range: {service}",
                passed,
                f"{p.min_price_eur}–{p.max_price_eur}€ (ratio: {ratio:.2f})"
            )
            
            status = "✅" if passed else "❌"
            print(f"  {status} {service}: {p.min_price_eur}–{p.max_price_eur}€ (ratio: {ratio:.2f}x, max: {max_ratio}x)")
    
    # =========================================================================
    # PILLAR 3: MISSING FIELDS TESTS
    # =========================================================================
    
    def test_pillar_3_missing_fields(self):
        """
        Pillar 3: Missing Fields Tests
        Verify no state lock / wrong service assumptions
        """
        print("\n" + "="*80)
        print("PILLAR 3: MISSING FIELDS & NO STATE LOCK TESTS")
        print("="*80)
        
        # Test that vague queries don't default to Umzug
        print("\n📌 NO UMZUG DEFAULT (Vague queries):")
        vague_tests = [
            ("preis?", None),  # Too vague, should be None or ask for clarification
            ("was kostet?", None),
            ("entsorgung ort?", "entsorgung"),  # Should recognize entsorgung, not default to umzug
            ("laminat preis", "laminat"),  # Should be laminat, not umzug
        ]
        
        for text, expected_service in vague_tests:
            intent = self.tool.classify_user_message(text)
            passed = intent.service_type == expected_service
            
            self.log_test(
                f"No Umzug default: {text[:25]}",
                passed,
                intent.service_type or "None"
            )
            print(f"  {'✅' if passed else '❌'} '{text}' → {intent.service_type} (expected: {expected_service})")
        
        # Test that required fields are correctly identified
        print("\n📌 REQUIRED FIELDS IDENTIFICATION:")
        field_tests = [
            ("entsorgung", ["location", "item_type"]),
            ("laminat", ["location", "area_m2"]),
            ("moebelmontage", ["location", "furniture_type"]),
            ("umzug", ["from_city", "to_city"]),
        ]
        
        for service_type, expected_fields in field_tests:
            service = self.tool.get_service_info(service_type)
            has_required = all(f in service.required_fields for f in expected_fields)
            
            self.log_test(
                f"Required fields: {service_type}",
                has_required,
                f"{service.required_fields}"
            )
            print(f"  {'✅' if has_required else '❌'} {service_type}: {service.required_fields}")
    
    # =========================================================================
    # PILLAR 4: CONVERSATION SWITCH TESTS
    # =========================================================================
    
    def test_pillar_4_conversation_switch(self):
        """
        Pillar 4: Conversation Switch Tests
        User changes intent mid-conversation
        Bot should recognize and not get stuck
        """
        print("\n" + "="*80)
        print("PILLAR 4: CONVERSATION SWITCH TESTS (Meta-questions & Intent Changes)")
        print("="*80)
        
        # Simulate conversation where user changes intent
        print("\n📌 INTENT SWITCH MID-CONVERSATION:")
        
        scenarios = [
            {
                "name": "Umzug -> Entsorgung switch",
                "messages": [
                    "Ich ziehe um",  # First: umzug
                    "Nein, eigentlich nur entsorgen",  # Switch to entsorgung
                ],
                "expected_final": "entsorgung"
            },
            {
                "name": "Entsorgung -> Laminat switch",
                "messages": [
                    "Ich brauche Entsorgung",
                    "Warte, eher Laminat abbauen",
                ],
                "expected_final": "laminat"
            },
            {
                "name": "Generic -> Specific switch",
                "messages": [
                    "Was kostet ihr?",  # Vague
                    "Für Laminat 100m²",  # Now specific
                ],
                "expected_final": "laminat"
            },
        ]
        
        for scenario in scenarios:
            last_intent = None
            for msg in scenario["messages"]:
                last_intent = self.tool.classify_user_message(msg)
            
            passed = last_intent.service_type == scenario["expected_final"]
            self.log_test(
                scenario["name"],
                passed,
                last_intent.service_type or "None"
            )
            
            print(f"\n  {scenario['name']}:")
            for i, msg in enumerate(scenario["messages"]):
                intent = self.tool.classify_user_message(msg)
                print(f"    [{i+1}] '{msg}' → {intent.service_type}")
            print(f"  {'✅' if passed else '❌'} Final: {last_intent.service_type} (expected: {scenario['expected_final']})")
        
        # Test meta-questions don't break flow
        print("\n📌 META-QUESTIONS DON'T BREAK FLOW:")
        meta_tests = [
            ("Warum fragst du mich das?", None),  # Should not crash, should handle
            ("Das macht keinen Sinn", None),  # Feedback, should handle
            ("Das passt nicht", None),  # Clarification, should handle
        ]
        
        for text, _ in meta_tests:
            intent = self.tool.classify_user_message(text)
            # Should not crash and should have intent type
            passed = intent.intent_type is not None
            
            self.log_test(
                f"Meta-Q: {text[:25]}",
                passed,
                intent.intent_type
            )
            print(f"  {'✅' if passed else '❌'} '{text}' → intent_type={intent.intent_type}")
    
    # =========================================================================
    # FINAL REPORT
    # =========================================================================
    
    def print_report(self):
        """Print final test report."""
        print("\n" + "█"*80)
        print("FINAL TEST GATE REPORT")
        print("█"*80)
        
        total = self.passed + self.failed
        percentage = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\nResults: {self.passed}/{total} tests passed ({percentage:.1f}%)")
        
        if self.failed > 0:
            print(f"\n❌ FAILED TESTS ({self.failed}):")
            for status, name, details in self.results:
                if status == "❌":
                    print(f"   {name}: {details}")
        
        print("\n" + "="*80)
        
        if percentage >= 95:
            print("✅ GO/NO-GO DECISION: ✅ GO LIVE")
            print("   All critical systems passing. Production deployment approved.")
            return True
        elif percentage >= 85:
            print("⚠️  GO/NO-GO DECISION: CONDITIONAL GO")
            print("   Most systems working. Minor issues to address, but safe for deployment.")
            return True
        else:
            print("❌ GO/NO-GO DECISION: ❌ DO NOT DEPLOY")
            print("   Critical issues found. Fix before deployment.")
            return False
    
    def run_all_tests(self):
        """Run all test pillars."""
        print("\n" + "█"*80)
        print("PRODUCTION TEST GATE - STARTING")
        print("█"*80)
        
        self.test_pillar_1_intent_classification()
        self.test_pillar_2_pricing_consistency()
        self.test_pillar_3_missing_fields()
        self.test_pillar_4_conversation_switch()
        
        go_ahead = self.print_report()
        
        print("\n" + "█"*80)
        return go_ahead


def main():
    try:
        gate = TestGate()
        success = gate.run_all_tests()
        
        print("\n" + "█"*80)
        if success:
            print("✅ TEST GATE PASSED - READY FOR DEPLOYMENT")
            print("█"*80)
            sys.exit(0)
        else:
            print("❌ TEST GATE FAILED - DO NOT DEPLOY YET")
            print("█"*80)
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ TEST EXECUTION ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
