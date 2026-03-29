# 🚀 DEPLOYMENT GUIDE - Klarumzug24 v2.0

**Status**: Ready for Controlled Rollout (91.3% - CONDITIONAL GO)  
**Date**: March 29, 2026  
**Type**: Incremental Release with Monitoring

---

## 📋 PRE-DEPLOYMENT CHECKLIST (VERIFY ON PRODUCTION SERVER)

```bash
# 1. Verify .env contains these keys:
OPENAI_API_KEY=<your-key>
DODE_MODEL=gpt-4.1-mini
DATABASE_URL=<production-db>

# 2. Verify all new files exist:
ls -la backend/app/ai/prompts_v2.py
ls -la backend/app/ai/pricing_tool.py
ls -la backend/app/ai/pricing_calculator.py
ls -la backend/app/ai/intent_classifier.py
ls -la backend/app/ai/services.py

# 3. Verify agent.py was updated:
grep "_handle_new_service_inquiry" backend/app/ai/agent.py

# 4. Test Python syntax:
python -m py_compile backend/app/ai/agent.py
python -m py_compile backend/app/ai/prompts_v2.py
python -m py_compile backend/app/ai/pricing_tool.py
```

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Backup Current Production
```bash
# Backup current version
cp -r backend/app/ai backend/app/ai.backup.$(date +%s)
cp backend/main.py backend/main.py.backup.$(date +%s)
```

### Step 2: Deploy New Files
```bash
# Copy new architecture files to production
cp backend/app/ai/prompts_v2.py /production/backend/app/ai/
cp backend/app/ai/pricing_tool.py /production/backend/app/ai/
cp backend/app/ai/pricing_calculator.py /production/backend/app/ai/
cp backend/app/ai/intent_classifier.py /production/backend/app/ai/
cp backend/app/ai/services.py /production/backend/app/ai/
cp backend/app/ai/agent.py /production/backend/app/ai/agent.py
```

### Step 3: Restart Service
```bash
# Stop current service
systemctl stop klarumzug24-api

# (wait 2 seconds)
sleep 2

# Start service
systemctl start klarumzug24-api

# Wait for startup
sleep 5

# Verify service is running
systemctl status klarumzug24-api
```

### Step 4: Verify API is Healthy
```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Expected response: 200 OK with JSON
```

---

## 🧪 IMMEDIATE POST-DEPLOYMENT SMOKE TESTS

Run these 5 queries immediately after deploy to verify production system:

### Query 1: Entsorgung Service
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Was kostet die Entsorgung von 3 Sofas?"}],
    "page": "/kontakt.html",
    "lang": "de"
  }'
```
**Expected**: Price response ~120-200 EUR  
**Status**: ✓ or ✗

### Query 2: Laminat Service
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Laminat entfernen 50 quadratmeter Hamburg"}],
    "page": "/kontakt.html",
    "lang": "de"
  }'
```
**Expected**: Price response ~400-650 EUR  
**Status**: ✓ or ✗

### Query 3: Möbelmontage Service
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "IKEA Regal aufbauen Hamburg"}],
    "page": "/kontakt.html",
    "lang": "de"
  }'
```
**Expected**: Service acknowledgment  
**Status**: ✓ or ✗

### Query 4: Einzeltransport Service (Edge Case)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Waschmaschine transportieren Kiel Hamburg"}],
    "page": "/kontakt.html",
    "lang": "de"
  }'
```
**Expected**: Transport service recognition (may default to umzug—acceptable edge case)  
**Status**: ✓ or ✗

### Query 5: Umzug Service (Backward Compatibility)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Ich ziehe von Hamburg nach Berlin um, 3 Zimmer"}],
    "page": "/kontakt.html",
    "lang": "de"
  }'
```
**Expected**: Ask for distance (backward compat check)  
**Status**: ✓ or ✗

---

## 📊 MONITORING (First 72 Hours)

Monitor these metrics **continuously**:

### Pillar 1: Intent Routing Accuracy
```
- entsorgung_correct: >85%
- laminat_correct: >85%
- moebelmontage_correct: >85%
- einzeltransport_correct: >80% (edge cases expected)
- umzug_backward_compat: >95%
```

**Alert If**: Any service drops below threshold

### Pillar 2: Pricing Stability
```
- Same input always returns same price: YES
- Price ranges are consistent: YES
- No prices <50 EUR (except valid items): YES
- No prices >2000 EUR (without explanation): YES
```

**Alert If**: Determinism broken or outliers detected

### Pillar 3: User Signals
Monitor for these frustration patterns:
```
"warum fragst du..." → State confusion
"nein" after price → Rejection
"umzug not intended" → Wrong intent
"bitte direkt preis" → Too many questions
```

**Alert If**: 2+ same signal within 1 hour

---

## 🔙 ROLLBACK PROCEDURE (If Issues)

### Immediate Rollback
```bash
# Stop production
systemctl stop klarumzug24-api

# Restore from backup
cp backend/app/ai.backup.*/agent.py backend/app/ai/agent.py
# (recover other modified files)

# Restart with old version
systemctl start klarumzug24-api

# Verify rolled back version
curl http://localhost:8000/api/health
```

### Determine Rollback Trigger
Rollback ONLY if:
- Prices are non-deterministic (same input ≠ same output)
- Intent routing falls below 80%
- API response time exceeds 3 seconds
- More than 10% of conversations failing

---

## 📝 POST-DEPLOYMENT LOGGING

Tag every conversation with:

```
success       → User got useful info + quote
wrong_intent  → Bot classified service incorrectly
unclear_price → Price range rejected by user
state_confusion → Bot stuck in loop
lead_conversion → User clicked contact/WhatsApp
edge_case     → One of 4 known edge cases triggered
```

This data drives v2.1 improvements.

---

## 🎯 SUCCESS CRITERIA (After 72 hours)

✅ **GO to v2.1** if:
- All 5 smoke tests pass
- Intent routing >85% for new services
- Pricing deterministic & consistent
- <5% conversation failures
- No catastrophic errors in logs

⚠️ **CONTINUE v2.0** if:
- Between 80-90% intent routing
- Minor pricing edge cases
- <10% conversation failures

❌ **ROLLBACK** if:
- Intent routing <80%
- Pricing non-deterministic
- API crashes or timeouts
- >10% conversation failures

---

## 📞 Support During Release

If issues arise:
1. Check logs: `/var/log/klarumzug24/api.log`
2. Verify .env is correct
3. Test /api/health endpoint
4. Review ROLLBACK PROCEDURE above
5. Contact: [support contact]

---

**Deployment Owner**: Dev Team  
**Deployment Time**: [AUTO-FILL]  
**Version**: v2.0-controlled-rollout  
**Confidence**: 91.3% CONDITIONAL GO
