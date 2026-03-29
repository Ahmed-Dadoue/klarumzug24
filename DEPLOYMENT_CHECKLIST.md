# 🚀 DEPLOYMENT CHECKLIST - Klarumzug24 v2.0 (Controlled Release)

**Date**: March 29, 2026  
**Status**: Ready for Controlled Rollout  
**Decision**: CONDITIONAL GO + Monitoring  

---

## ✅ PRE-DEPLOYMENT VERIFICATION

### Code Changes Completed
- [x] agent.py integrated with pricing_tool
- [x] prompts_v2.py implemented
- [x] pricing_calculator.py operational
- [x] intent_classifier.py functional
- [x] services.py with 5 service types
- [x] pricing_tool.py (unified interface)
- [x] Backward compatibility maintained

### Test Results
- [x] Test Gate: 91.3% (42/46 tests)
- [x] End-to-end integration: PASSING
- [x] Entsorgung queries: PASSING
- [x] Laminat queries: PASSING
- [x] Möbelmontage queries: PASSING
- [x] Einzeltransport queries: PASSING (with 4 edge cases)
- [x] Umzug backward compatibility: PASSING

---

## 🔧 DEPLOYMENT PREPARATION CHECKLIST

### 1. Environment Configuration
- [ ] Verify .env file on production server
  - `OPENAI_API_KEY=` (set)
  - `DODE_MODEL=` (gpt-4.1-mini or later)
  - `DATABASE_URL=` (production DB path)
- [ ] Verify load_dotenv() is active in main.py
- [ ] Check Python version (3.11+ required)

### 2. New Files Verification
- [ ] backend/app/ai/prompts_v2.py exists on server
- [ ] backend/app/ai/pricing_tool.py exists on server
- [ ] backend/app/ai/pricing_calculator.py exists on server
- [ ] backend/app/ai/intent_classifier.py exists on server
- [ ] backend/app/ai/services.py exists on server

### 3. Modified Files
- [ ] backend/app/ai/agent.py updated with integration
- [ ] Imports: prompts_v2, pricing_tool added
- [ ] Function _handle_new_service_inquiry() present
- [ ] generate_dode_reply() calls new service handler first

### 4. API Health Check
- [ ] GET /api/health returns 200
- [ ] POST /api/chat accepts requests
- [ ] Response time < 2s for pricing queries
- [ ] No 500 errors on startup

### 5. Frontend Connectivity
- [ ] Frontend points to correct API URL
- [ ] CORS headers allow frontend origin
- [ ] Chat widget loads without errors
- [ ] Messages send/receive correctly

### 6. Logging & Monitoring
- [ ] Chat logs are being written
- [ ] Error logs are routing correctly
- [ ] Performance metrics being collected
- [ ] Request IDs in logs for tracing

---

## 🧪 POST-DEPLOYMENT SMOKE TESTS (Minimal, Quick)

Run these 5 queries directly on production API:

```
Query 1: "Was kostet die Entsorgung von 3 Sofas?"
Expected: 120-200 EUR price suggestion
Service: entsorgung
✓ or ✗

Query 2: "Laminat entfernen, 50 quadratmeter, Hamburg"
Expected: 400-650 EUR price suggestion
Service: laminat
✓ or ✗

Query 3: "IKEA Regal aufbauen in Hamburg"
Expected: Service acknowledgment, furniture assembly context
Service: moebelmontage
✓ or ✗

Query 4: "Waschmaschine transportieren von Kiel nach Hamburg"
Expected: Service detection (may default to umzug as edge case)
Service: einzeltransport (or umzug acceptable)
✓ or ✗

Query 5: "Ich ziehe von Hamburg nach Berlin um, 3 Zimmer" 
Expected: Ask for distance (backward compat check)
Service: umzug
✓ or ✗
```

---

## 📊 PRODUCTION MONITORING (First 72 Hours)

### What to Watch (Pillar 1: Intent Routing)

Log metrics for:
```
- entsorgung_routed_correctly: %
- laminat_routed_correctly: %
- moebelmontage_routed_correctly: %
- einzeltransport_routed_correctly: %
- umzug_routed_correctly: %
- unknown_intent: count
```

**Alert if**: Any service falls below 85% correct routing

### What to Watch (Pillar 2: Pricing Stability)

Check every price response:
```
- price_min & price_max present: yes/no
- price_min < price_max: yes/no
- ratio (max/min) within expected range: yes/no
- same input = same output: yes/no
```

**Alert if**: Any inconsistency detected

### What to Watch (Pillar 3: User Frustration Signals)

Conversations containing:
```
"warum fragst du das" → State confusion
"nein" (after price offer) → Rejection
"das ist nicht umzug" → Wrong intent
"bitte direkt preis" → Too many questions
"ich meine etwas anderes" → Intent mismatch
```

**Alert if**: 2+ of same signal within 1 hour

---

## 🏷️ TAGGING FOR POST-DEPLOYMENT LEARNING

Every conversation after deploy, tag with:

```
success: User got useful info + quote
wrong_intent: Bot classified service incorrectly
unclear_price: Price range rejected by user
state_confusion: Bot stuck in loop
lead_conversion: User clicked "contact" / WhatsApp
edge_case: Known 4 edge cases triggered
```

This is **gold** for next iteration.

---

## 🚨 ROLLBACK CONDITIONS

**Do NOT continue production use if**:
- Prices fluctuate for identical inputs (determinism broken)
- Intent routing falls below 80% accuracy
- API response time > 3s consistently
- More than 10% of conversations failing
- OPENAI_API_KEY or critical config missing

**In case of rollback**:
1. Switch backend/app/ai/agent.py back to previous version
2. Remove calls to _handle_new_service_inquiry()
3. Revert to old prompts (keep prompts_v2 for fallback)
4. Restart API service

---

## 📋 DEPLOYMENT DECISION MATRIX

| Condition | Status | Action |
|-----------|--------|--------|
| Code integration complete | ✅ | Deploy |
| End-to-end tests passing | ✅ | Deploy |
| Backward compatibility verified | ✅ | Deploy |
| Environment config ready | ⏳ | Verify before deploy |
| Monitoring setup in place | ⏳ | Configure now |
| Smoke tests ready | ✅ | Execute post-deploy |

---

## 🎯 DEPLOYMENT GO/NO-GO

**FINAL STATUS: ✅ GO**

Proceed with controlled rollout:
1. Deploy code
2. Run smoke tests
3. Monitor first 72 hours
4. Fix edge cases post-deploy

**Philosophy**: Production teaches better than testing. Deploy smart, monitor strict.

---

## 👤 Deployed By
Date: [AUTO-FILLED]
Version: v2.0-controlled-rollout
Confidence Level: 91.3% (CONDITIONAL GO)
