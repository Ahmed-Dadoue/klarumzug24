# Dode Pricing Architecture v2.0

## Overview

This is a **Production-Ready Pricing System** for Klarumzug24's Dode chatbot. It replaces template-based logic with a modular, maintainable architecture.

**Key Principle:** Intent → Required Fields → Price Calculation → Formatted Response

---

## Architecture Layers

### 1. Service Definition Layer (`services.py`)

**Purpose:** Define what services exist and what they require.

```python
SERVICES = {
    "umzug": ServiceDefinition(
        key="umzug",
        name_de="Umzug",
        keywords_de=["umzug", "umziehen", ...],
        required_fields=["from_city", "to_city"],
        optional_fields=["rooms", "floor_from", ...],
        description_de="..."
    ),
    "entsorgung": ServiceDefinition(...),
    "laminat": ServiceDefinition(...),
    "moebelmontage": ServiceDefinition(...),
    "einzeltransport": ServiceDefinition(...)
}
```

**Key Function:** `identify_service_type(user_text)` → Returns the service type (or None)

**Why This Matters:**
- No more hardcoded if/else chains
- Easy to add new services
- Self-documenting: what fields does Entsorgung need? Check the definition!

---

### 2. Intent Classification Layer (`intent_classifier.py`)

**Purpose:** Understand WHAT the user is asking about.

```python
intent = classify_intent("ich möchte 3 sofas entsorgen was kostet")
# Returns:
# ClassifiedIntent(
#     intent_type="pricing_inquiry",
#     service_type="entsorgung",
#     confidence=0.95,
#     reasoning="Pricing inquiry for entsorgung service"
# )
```

**Intent Types:**
- `PRICING_INQUIRY` - User asking for a price
- `SERVICE_DETAILS` - Providing details about a service
- `CONTACT_REQUEST` - Want to contact/call
- `GENERAL_QUESTION` - About services/regions
- `FEEDBACK` - Complaining or asking clarification
- `CLARIFICATION` - Asking for clarification

**Why This Matters:**
- Bot knows WHAT to talk about before routing
- No more guessing or defaults
- Intent is pre-classified before reaching agent

---

### 3. Pricing Calculator Layer (`pricing_calculator.py`)

**Purpose:** Calculate accurate price estimates for each service.

```python
# Example: Calculate entsorgung price
estimate = calculate_entsorgung_price(
    item_type="3 sofas",
    location="Kiel",
    quantity=3
)
# Returns:
# PriceEstimate(
#     service_type="entsorgung",
#     min_price_eur=120,
#     max_price_eur=180,
#     explanation="Entsorgung: 3 sofas"
# )
```

**Service-Specific Functions:**
- `calculate_umzug_price()` - Moving service
- `calculate_entsorgung_price()` - Junk removal
- `calculate_laminat_price()` - Floor removal
- `calculate_moebelmontage_price()` - Furniture assembly
- `calculate_einzeltransport_price()` - Single item transport

**Why This Matters:**
- Prices are consistent and logic-based (not random)
- Easy to update: change one function, all queries updated
- Testable: you can unit test each pricing function
- Flexible: can add region factors, seasonal discounts later

---

### 4. Pricing Tool Interface (`pricing_tool.py`)

**Purpose:** Single entry point combining all layers.

```python
from app.ai.pricing_tool import get_pricing_tool

tool = get_pricing_tool()

# Step 1: Classify the intent
intent = tool.classify_user_message("ich möchte laminat abbau")
# → ClassifiedIntent(intent_type="pricing_inquiry", service_type="laminat")

# Step 2: Get service requirements
service = tool.get_service_info(intent.service_type)
# → ServiceDefinition with required/optional fields

# Step 3: Calculate price (when user provides details)
estimate = tool.calculate_estimated_price(
    service_type="laminat",
    details={"area_m2": 50, "location": "Hamburg", "entsorgung_included": True}
)
# → PriceEstimate(min=400, max=650)

# Step 4: Format for user
response = tool.format_price_response(estimate)
# → "Für ... liegt die unverbindliche Schätzung bei etwa 400–650 EUR..."
```

---

### 5. Bot System Prompt (`prompts_v2.py`)

**Key Changes:**
1. Bot knows the service is pre-classified
2. Bot doesn't ask wrong questions (e.g., "von welcher Stadt" for entsorgung)
3. Bot collects REQUIRED fields, not random data
4. Bot doesn't invent prices

```python
# Old (broken):
"Aus welcher Stadt ziehen Sie um?" (even if user said "entsorgung")

# New (smart):
"Was möchten Sie entsorgen?" (because system identified entsorgung)
```

---

## Integration with Agent

### Current Flow (High-Level)

```
User Message
    ↓
[agent.py] generate_dode_reply()
    ↓
Check if template handling needed
    ↓
[pricing_tool] classify_intent()
    ↓
Intent classified → Collect required fields
    ↓
[pricing_tool] calculate_price()
    ↓
[pricing_tool] format_price_response()
    ↓
Bot Response to User
```

### What Changes in agent.py

**Instead of:**
```python
if _has_estimate_intent(messages):
    if estimate_reply_idx >= 0:
        # ... complicated template logic
```

**Use:**
```python
from app.ai.pricing_tool import get_pricing_tool

tool = get_pricing_tool()
intent = tool.classify_user_message(last_user_message)

if intent.intent_type == "pricing_inquiry":
    service_info = tool.get_service_info(intent.service_type)
    # Collect required fields from conversation
    price_estimate = tool.calculate_price(intent.service_type, collected_details)
    response = tool.format_price_response(price_estimate)
```

---

## Adding a New Service

Suppose you want to add "Wohnungsreinigung" (apartment cleaning):

### Step 1: Add to services.py
```python
"reinigung": ServiceDefinition(
    key="reinigung",
    name_de="Wohnungsreinigung",
    keywords_de=["reinigung", "putzen", "säubern", "cleaning"],
    required_fields=["location", "room_count"],
    optional_fields=["square_meters"],
    description_de="Professionelle Wohnungsreinigung"
)
```

### Step 2: Add pricing function in pricing_calculator.py
```python
def calculate_reinigung_price(location: str, room_count: int, 
                              square_meters: Optional[float] = None):
    base = 150
    per_room = room_count * 50
    min_price = base + per_room
    max_price = int(min_price * 1.2)
    return PriceEstimate(...)
```

### Step 3: Add to calculate_price() router
```python
elif service_type == "reinigung":
    return calculate_reinigung_price(**details)
```

**Done.** Bot can now handle cleaning inquiries immediately.

---

## Benefits of This Architecture

| Aspect | Before | After |
|--------|--------|-------|
| **Adding Service** | Change template logic, potentially break others | Add one definition + one function |
| **Price Update** | Hunt through prompt and template code | Change one pricing function |
| **Consistency** | Prices might differ per run | Deterministic calculation |
| **Testing** | Hard to test template logic | Easy unit testing |
| **Scalability** | Hardcoded if/else chaos | Modular, extensible |
| **Time to Production** | Days (lots of testing needed) | Hours (logic is simple) |

---

## Migration Path

### Phase 1: Deploy Pricing Tool (Current)
- ✅ services.py
- ✅ pricing_calculator.py
- ✅ intent_classifier.py
- ✅ pricing_tool.py
- ✅ prompts_v2.py

### Phase 2: Update Agent (Next)
- Update `agent.py` to use pricing_tool
- Test with real conversations
- Remove old template logic gradually

### Phase 3: Enhance (Future)
- Add regional pricing factors
- Connect to database (pricing_rules table)
- Add seasonal adjustments
- Support custom company pricing

---

## Testing the New System

```python
from app.ai.pricing_tool import get_pricing_tool

tool = get_pricing_tool()

# Test 1: Classify intent
intent = tool.classify_user_message("Ich brauche Hilfe beim Entrümpeln")
assert intent.service_type == "entsorgung"
assert intent.intent_type == "pricing_inquiry"

# Test 2: Calculate price
estimate = tool.calculate_estimated_price(
    "entsorgung",
    {"item_type": "3 Sofas", "location": "Berlin"}
)
assert 120 <= estimate.min_price_eur <= estimate.max_price_eur <= 200

# Test 3: Format response
response = tool.format_price_response(estimate)
assert "120" in response and "200" in response
```

---

## Next Steps

1. **Review this architecture** - Feedback?
2. **Integrate with agent.py** - Update main routing
3. **Test with real queries** - Make sure it works
4. **Remove old template logic** - Clean up technical debt
5. **Document in user guide** - How to add services

---

**Status:** Ready for Integration 🚀
