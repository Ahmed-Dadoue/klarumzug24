# Klarumzug24 with Dode AI (v1)

## 1. Project Overview
Klarumzug24 is a digital moving platform that combines a traditional pricing backend with an AI-powered chat assistant (Dode).

The system allows users to estimate moving costs in a guided conversational flow while ensuring that all prices are calculated deterministically in the backend (no AI-generated pricing).

Dode v1 focuses on correctness, predictable pricing, and stable frontend-backend integration.

## 2. Features
- Chat-based move price estimation via POST /api/chat
- Deterministic pricing logic (AI never invents prices)
- Step-by-step collection of required move details (city, rooms, distance)
- Sanity checks for unrealistic inputs (for example very high room counts)
- Robust short-input handling (e.g. "4", "100", "vier", "100 km")
- General chat support (contact, WhatsApp, services)
- Frontend fallback replies if backend calls fail

## 3. Design Principles
- Deterministic pricing: AI never generates prices on its own
- Minimal AI responsibility: AI handles interaction, backend handles business logic
- Safe fallback behavior: frontend fallback exists, but backend responses are the source of truth
- Incremental UX: guided step-by-step collection instead of large forms

## 4. Architecture

### Frontend (docs/)
- Static pages and assets live under docs/
- Chat widget is implemented in docs/assets/dode-chat.js
- Widget sends conversation context to /api/chat and renders responses

### Backend (FastAPI)
- Main API app is in backend/main.py
- Key routes: /health, /api/chat, /api/predict, plus lead/admin endpoints
- SQLAlchemy persistence for companies, pricing rules, leads, and transactions

### AI Layer (backend/app/ai)
- agent.py: intent detection, extraction, follow-up logic, reset/reuse behavior
- tools.py: deterministic price tool adapter to existing backend logic
- schemas.py: typed chat and move detail models
- prompts.py: system and task prompts for general chat

### Request Flow (Simplified)
```
User
  -> Frontend (dode-chat.js)
  -> POST /api/chat
  -> AI Agent
      -> Pricing Tool (deterministic)
      -> OpenAI (general chat)
  -> Response
  -> Frontend
```

## 5. Setup Instructions

### Backend
1. Open terminal in backend
   - cd backend
2. Create virtual environment
   - py -m venv .venv
3. Activate environment (PowerShell)
   - .\.venv\Scripts\Activate.ps1
4. Install dependencies
   - pip install -r requirements.txt
5. Run server with env file
   - .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --env-file .env

Health check:
- http://127.0.0.1:8000/health

### Frontend
1. Open terminal in docs
   - cd docs
2. Start static server
   - py -m http.server 8080
3. Open in browser
   - http://localhost:8080

## 6. Environment Variables
Create backend/.env and define required values.

Required for AI chat:
- OPENAI_API_KEY

Common variables:
- DATABASE_URL
- ALLOWED_ORIGINS
- OPENAI_API_KEY
- DODE_MODEL
- DODE_MAX_MESSAGES
- DODE_MAX_OUTPUT_TOKENS
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASS
- MAIL_TO
- MAIL_FROM

Security notes:
- Never commit real secrets to Git.
- Keep .env excluded via .gitignore.
- Do not expose API keys in frontend code or public repositories.
- Always use environment variables for secrets.
- Rotate exposed keys immediately.

## 7. API Documentation

### POST /api/chat
The endpoint routes requests into:
- estimate flow (deterministic pricing path), or
- general chat flow (OpenAI-backed response)

Request example:
{
  "messages": [
    {"role": "user", "content": "Ich ziehe von Kiel nach Hamburg, 4 Zimmer, 100 km"}
  ],
  "page": "/index.html"
}

Current response shape:
{
  "ok": true,
  "message": "Dode reply generated",
  "data": {
    "reply": "Fuer Ihren Umzug ... unverbindliche Schaetzung ..."
  },
  "reply": "Fuer Ihren Umzug ... unverbindliche Schaetzung ..."
}

Contract note:
- Use data.reply as the primary reply field.
- Top-level reply currently exists for legacy compatibility.
- Note: The duplicated reply field is kept temporarily for backward compatibility and will be simplified in future versions.

### GET /health
Simple service health endpoint.

## 8. Testing Notes
- Always inspect /api/chat calls in browser Network tab (Fetch/XHR)
- Run backend on 127.0.0.1:8000 and frontend on 8080 during local dev
- Frontend fallback can hide backend errors if Network is not checked

## 9. Known Limitations (v1)
- Intent detection is primarily keyword/regex based
- No persistent long-term memory across sessions
- Limited flexibility for highly ambiguous or mixed-language input
- No automatic distance calculation; user currently provides distance in km
- Frontend fallback can mask backend outages if diagnostics are skipped

## 10. Future Improvements (v2 roadmap)
1. Improve estimate phrasing when min equals max (for example ca. 82 EUR)
2. Add optional distance assistance when km is missing
3. Make follow-up tone more natural with less repetition
4. Add a clearer post-estimate CTA (request submission path)
5. Improve page-aware general chat precision
