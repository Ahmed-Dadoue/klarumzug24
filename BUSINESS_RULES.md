# Klarumzug24 – Business Rules

## Required Data for Price Estimation

To calculate a rough estimate, the system should ideally have:

- from_city
- to_city
- move_size (rooms or m²)
- floor_from
- floor_to
- elevator_from (true/false)
- elevator_to (true/false)
- move_date (optional but recommended)

## Missing Data Handling

If required data is missing:
- The AI must ask follow-up questions
- Do NOT guess values
- Ask maximum 1–2 questions at a time

## Price Estimation Rules

- All prices are "unverbindliche Schätzung"
- Price must come from backend logic (NOT from AI)
- Output should be:
  - price_min
  - price_max
  - short explanation

## Lead Creation Rules

Create a lead ONLY if:
- User has provided sufficient move details
- User shows intent (e.g. “I want an offer”)
- Contact data is available (name, phone, or email)

## Escalation Rules

Escalate to human if:
- Customer asks for binding/legal guarantee
- Complex or large-scale move (e.g. company relocation)
- Tool/API fails
- Customer insists on exact fixed price

## Language Rules

- All customer responses MUST be in German
- Internal logic can be English

## Forbidden Behavior

- No hallucinated pricing
- No fake company data
- No promises without backend confirmation
