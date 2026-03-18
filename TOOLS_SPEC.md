# Klarumzug24 – Tools Specification

## Tool: calculate_move_price

### Description
Calculate a rough moving price based on structured input.

### Input
- from_city: string
- to_city: string
- rooms: integer (optional)
- area_m2: integer (optional)
- floor_from: integer
- floor_to: integer
- elevator_from: boolean
- elevator_to: boolean
- move_date: string (optional)

### Output
- price_min: number
- price_max: number
- explanation: string
- confidence: string (low / medium / high)

### Rules
- Must call backend logic or ML model
- Must NOT be calculated by LLM

---

## Tool: create_lead

### Description
Create a new customer lead.

### Input
- name: string
- phone: string
- email: string
- move_details: object

### Output
- lead_id: string
- status: string

---

## Tool: get_matching_companies

### Description
Return suitable moving companies for the request.

### Input
- city_from
- city_to
- move_size

### Output
- list of companies

---

## Tool Usage Rules

- Tools must be used only when enough data is available
- AI should explain results AFTER tool execution
- Never simulate tool output
