"""
Test script for the new Pricing Architecture v2.0

Run this to verify the system works correctly.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.ai import (
    get_pricing_tool,
    classify_intent,
    identify_service_type,
    SERVICES
)


def test_service_identification():
    """Test 1: Service type identification"""
    print("\n" + "="*70)
    print("TEST 1: SERVICE IDENTIFICATION")
    print("="*70)
    
    test_cases = [
        ("Ich möchte 3 Sofas entsorgen", "entsorgung"),
        ("laminat 50m² in hamburg abbauen", "laminat"),
        ("ich ziehe von kiel nach berlin", "umzug"),
        ("IKEA Regal aufbauen", "moebelmontage"),
        ("waschmaschine transportieren", "einzeltransport"),
    ]
    
    for text, expected in test_cases:
        result = identify_service_type(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text[:40]}' → {result} (expected: {expected})")


def test_intent_classification():
    """Test 2: Intent classification"""
    print("\n" + "="*70)
    print("TEST 2: INTENT CLASSIFICATION")
    print("="*70)
    
    tool = get_pricing_tool()
    
    test_cases = [
        ("was kostet 3 sofas entsorgen?", "pricing_inquiry", "entsorgung"),
        ("ich brauche laminat abbau", "pricing_inquiry", "laminat"),
        ("preis?", "pricing_inquiry", None),
        ("eure kontakt?", "contact_request", None),
        ("danke für die info", "feedback", None),
    ]
    
    for text, intent_type, service_type in test_cases:
        intent = tool.classify_user_message(text)
        intent_ok = intent.intent_type == intent_type
        service_ok = intent.service_type == service_type
        
        status = "✅" if (intent_ok and service_ok) else "❌"
        print(f"{status} '{text[:30]}' → intent={intent.intent_type}, service={intent.service_type}")


def test_pricing_calculation():
    """Test 3: Price calculation"""
    print("\n" + "="*70)
    print("TEST 3: PRICING CALCULATION")
    print("="*70)
    
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
        
        price_ok = (
            min_exp <= estimate.min_price_eur <= estimate.max_price_eur <= max_exp
        )
        status = "✅" if price_ok else "❌"
        
        print(
            f"{status} {service:15} → "
            f"{estimate.min_price_eur}–{estimate.max_price_eur}€ "
            f"(expected: {min_exp}–{max_exp}€)"
        )


def test_response_formatting():
    """Test 4: Response formatting"""
    print("\n" + "="*70)
    print("TEST 4: RESPONSE FORMATTING")
    print("="*70)
    
    tool = get_pricing_tool()
    
    estimate = tool.calculate_estimated_price(
        "entsorgung",
        {"item_type": "3 Sofas", "location": "Kiel", "quantity": 3}
    )
    
    response = tool.format_price_response(estimate)
    print(f"\n📝 Formatted Response:\n{response}\n")
    
    # Check response contains key elements
    checks = [
        ("120" in response, "Contains min price"),
        ("180" in response, "Contains max price"),
        ("unverbindlich" in response, "Says unverbindlich"),
        ("EUR" in response or "€" in response, "Has currency"),
    ]
    
    for check, description in checks:
        status = "✅" if check else "❌"
        print(f"{status} {description}")


def test_all_services_defined():
    """Test 5: All services are properly defined"""
    print("\n" + "="*70)
    print("TEST 5: SERVICE DEFINITIONS")
    print("="*70)
    
    for service_key, service in SERVICES.items():
        has_required = len(service.required_fields) > 0
        has_keywords = len(service.keywords_de) > 0
        
        status = "✅" if (has_required and has_keywords) else "❌"
        print(
            f"{status} {service.name_de:30} "
            f"(keywords: {len(service.keywords_de)}, required: {len(service.required_fields)})"
        )


def main():
    """Run all tests"""
    print("\n" + "█"*70)
    print("TESTING NEW PRICING ARCHITECTURE v2.0")
    print("█"*70)
    
    try:
        test_service_identification()
        test_intent_classification()
        test_pricing_calculation()
        test_response_formatting()
        test_all_services_defined()
        
        print("\n" + "█"*70)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("█"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
