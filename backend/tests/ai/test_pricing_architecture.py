"""
Lightweight regression script for the pricing architecture.

Exit code 0 means all checks passed.
Exit code 1 means at least one check failed.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ai import SERVICES, get_pricing_tool, identify_service_type


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def test_service_identification() -> int:
    failures = 0
    _print_header("TEST 1: SERVICE IDENTIFICATION")

    test_cases = [
        ("Ich möchte 3 Sofas entsorgen", "entsorgung"),
        ("laminat 50m² in hamburg abbauen", "laminat"),
        ("ich ziehe von kiel nach berlin", "umzug"),
        ("IKEA Regal aufbauen", "moebelmontage"),
        ("waschmaschine transportieren", "einzeltransport"),
    ]

    for text, expected in test_cases:
        result = identify_service_type(text)
        ok = result == expected
        failures += int(not ok)
        status = "OK" if ok else "FAIL"
        print(f"{status:4} '{text[:40]}' -> {result} (expected: {expected})")

    return failures


def test_intent_classification() -> int:
    failures = 0
    _print_header("TEST 2: INTENT CLASSIFICATION")

    tool = get_pricing_tool()

    test_cases = [
        ("was kostet 3 sofas entsorgen?", "pricing_inquiry", "entsorgung"),
        ("ich brauche laminat abbau", "service_details", "laminat"),
        ("preis?", "pricing_inquiry", None),
        ("eure kontakt?", "contact_request", None),
        ("danke für die info", "feedback", None),
    ]

    for text, intent_type, service_type in test_cases:
        intent = tool.classify_user_message(text)
        ok = intent.intent_type == intent_type and intent.service_type == service_type
        failures += int(not ok)
        status = "OK" if ok else "FAIL"
        print(f"{status:4} '{text[:30]}' -> intent={intent.intent_type}, service={intent.service_type}")

    return failures


def test_pricing_calculation() -> int:
    failures = 0
    _print_header("TEST 3: PRICING CALCULATION")

    tool = get_pricing_tool()

    test_cases = [
        ("entsorgung", {"item_type": "3 Sofas", "location": "Kiel"}, 120, 200),
        ("entsorgung", {"item_type": "Stickmaschine", "location": "Hamburg"}, 150, 250),
        ("laminat", {"area_m2": 50, "location": "Hamburg"}, 400, 650),
        ("moebelmontage", {"furniture_type": "IKEA Regal", "location": "Berlin"}, 100, 150),
        ("einzeltransport", {"item_description": "Waschmaschine", "location": "Munich"}, 80, 150),
    ]

    for service, details, min_exp, max_exp in test_cases:
        estimate = tool.calculate_estimated_price(service, details)
        ok = min_exp <= estimate.min_price_eur <= estimate.max_price_eur <= max_exp
        failures += int(not ok)
        status = "OK" if ok else "FAIL"
        print(
            f"{status:4} {service:15} -> "
            f"{estimate.min_price_eur}-{estimate.max_price_eur} EUR "
            f"(expected: {min_exp}-{max_exp} EUR)"
        )

    return failures


def test_response_formatting() -> int:
    failures = 0
    _print_header("TEST 4: RESPONSE FORMATTING")

    tool = get_pricing_tool()
    estimate = tool.calculate_estimated_price(
        "entsorgung",
        {"item_type": "Sofa", "location": "Kiel"},
    )
    response = tool.format_price_response(estimate)

    print(f"\nFormatted Response:\n{response}\n")

    checks = [
        (str(estimate.min_price_eur) in response, "Contains min price"),
        (str(estimate.max_price_eur) in response, "Contains max price"),
        ("unverbindlich" in response, "Says unverbindlich"),
        ("EUR" in response or "€" in response, "Has currency"),
    ]

    for check, description in checks:
        failures += int(not check)
        status = "OK" if check else "FAIL"
        print(f"{status:4} {description}")

    return failures


def test_all_services_defined() -> int:
    failures = 0
    _print_header("TEST 5: SERVICE DEFINITIONS")

    for service_key, service in SERVICES.items():
        has_required = len(service.required_fields) > 0
        has_keywords = len(service.keywords_de) > 0
        ok = has_required and has_keywords
        failures += int(not ok)
        status = "OK" if ok else "FAIL"
        print(
            f"{status:4} {service.name_de:30} "
            f"(keywords: {len(service.keywords_de)}, required: {len(service.required_fields)})"
        )

    return failures


def main() -> None:
    print("\n" + "#" * 70)
    print("TESTING PRICING ARCHITECTURE")
    print("#" * 70)

    failures = 0
    failures += test_service_identification()
    failures += test_intent_classification()
    failures += test_pricing_calculation()
    failures += test_response_formatting()
    failures += test_all_services_defined()

    print("\n" + "#" * 70)
    if failures == 0:
        print("ALL CHECKS PASSED")
        print("#" * 70 + "\n")
        sys.exit(0)

    print(f"FAILED CHECKS: {failures}")
    print("#" * 70 + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
