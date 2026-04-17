# Transport Questioner

Dieses Paket ist ein eigenstaendiger Black-Box-Tester fuer externe Chatbots von Umzugs- und Transportfirmen.

Wichtig:

- Keine interne Kopplung an Website- oder Chatbot-Code
- Zugriff auf das Zielsystem nur per API
- OpenAI ist der echte Questioner-Engine
- Domain strikt begrenzt auf Umzug, Transport und umzugsnahe Dienstleistungen

## Vorher

Die vorhandenen Harness-Skripte im Repository waren vor allem:

- interne Routing-/Regression-Checks
- stark auf bestehende Projektlogik bezogen
- nicht als professioneller externer Branchen-Questioner gedacht

Sie konnten nicht sauber als realistischer, lernfaehiger Black-Box-Tester fuer andere Firmen-Chatbots dienen.

## Jetzt

Der neue Questioner arbeitet mit klaren Schichten:

1. `scenario state`
   Haltet Route, Etagen, Aufzug, Sondergueter, Zusatzleistungen und Service-Mix stabil ueber den ganzen Dialog.

2. `persona`
   Testet als Privatkunde, Firmenkunde, Preis-Hawk, Beschwerde-Fall oder Expert-Auditor.

3. `test objective`
   Steuert Fokus auf Preise, Policies, Widersprueche, Edge Cases, Buchung, Qualitaet oder Leistungsabgrenzung.

4. `local memory + script memory`
   Nutzt lokale Audit-/Review-Artefakte als Rohmaterial und speichert neue Failure-Cases sowie gute Probe-Muster.

5. `OpenAI questioner engine`
   Generiert die naechste Nutzeraktion intelligent:
   - neue Frage
   - Challenge
   - Widerspruchsprobe
   - Klarstellung
   - oder scenario-basierte Antwort auf Rueckfragen des Bots

6. `evaluation`
   Bewertet jede Bot-Antwort auf:
   - echte Frage beantwortet?
   - Kontext verloren?
   - starrer Preisflow?
   - verdaechtiger Preis?
   - Policy unstabil?
   - Services vermischt?
   - ungesicherte Zusage?

## OpenAI als echter Engine

OpenAI wird in drei Rollen verwendet:

1. `plan_next_turn`
   Erzeugt die naechste Nutzeraktion aus Persona, Ziel, Szenario, Memory, letzter Bot-Antwort und offener Coverage.

2. `evaluate_answer`
   Prueft die letzte Bot-Antwort als hybrider Evaluator zusammen mit Heuristiken.

3. `auto_reply`
   Formuliert natuerliche, aber faktengebundene Szenario-Antworten, wenn der Bot fehlende Angaben erfragt.

Wichtig:

- OpenAI darf keine Offtopic-Fragen erzeugen
- OpenAI darf keine Szenario-Fakten erfinden
- Domain-Guardrails werden im Prompt und per lokaler Validierung erzwungen

## Memory-Anbindung

Als Input werden gelesen:

- `local_knowledge_memory/logs/conversation_audit.jsonl`
- `local_knowledge_memory/review_queue/pending/*.json`
- `local_knowledge_memory/review_queue/approved/*.json`

Als neues Skript-Wissen werden geschrieben:

- `scripts/transport_questioner_data/failure_cases.jsonl`
- `scripts/transport_questioner_data/good_probes.jsonl`
- `scripts/transport_questioner_data/run_logs/*.json`

## Beispiel

```powershell
python scripts\run_transport_questioner.py `
  --api-url "https://example.com/api/chat" `
  --scenario-file "scripts/transport_questioner/sample_scenario.json" `
  --objective-file "scripts/transport_questioner/sample_objective.json" `
  --persona expert_auditor `
  --response-path "data.reply"
```

Optional:

- `--request-mode messages`
- `--extra-headers-json "{\"X-Client\":\"questioner\"}"`
- `--extra-payload-json "{\"lang\":\"de\"}"`

## Was noch spaeter verbessert werden kann

- feinere Claim-Extraktion fuer Widerspruchserkennung
- tiefere Preisplausibilitaet je Leistungskombination
- Replay-/Batch-Laeufe ueber mehrere Personas automatisch
- Coverage-Matrix mit expliziten Servicefamilien
- Aggregations-Reports ueber viele Black-Box-Runs
