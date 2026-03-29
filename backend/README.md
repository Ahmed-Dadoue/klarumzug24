# Klarumzug24 – Digitale Umzugsplattform

Eine vollständig integrierte, produktionsreife Plattform für Umzugspreiskalkulationen mit KI-gestütztem Chat-Assistenten, Lead-Management und Unternehmensintegration.

## Projektbeschreibung

Klarumzug24 ist ein modernes B2B2C-System zur Umzugspreiskalkulierung und Lead-Generierung mit folgenden Kern-Funktionen:

- **Intelligentes Chat-Interface (Dode)**: KI-Assistent für natürlichsprachige Kundeninteraktion
- **Dynamische Preiskalkulation**: Regelbasierte oder ML-basierte Preisberechnung mit Unternehmens-Spezifiken
- **Lead-Management**: Automatische Lead-Verteilung an Partnerunternehmen (Round-Robin mit Budgetberücksichtigung)
- **Admin-Dashboard**: Verwaltung von Unternehmen, Preisregeln, Transaktionen und Analytics
- **Privacy-by-Design**: Begrenzte Datensichtbarkeit für unbearbeitete Leads
- **Multi-Language Support**: Deutsch und Englisch für Nutzer und API

## Technologie-Stack

| Komponente | Technologie |
|-----------|------------|
| **Backend-Framework** | FastAPI 0.115+ (Python 3.11) |
| **Datenbank** | SQLite (Entwicklung), PostgreSQL 3.1+ (Produktion) |
| **ORM** | SQLAlchemy 2.0+ |
| **AI/LLM** | OpenAI GPT-4o-mini (Dode Assistant) |
| **Server** | Uvicorn 0.30+ |
| **Containerisierung** | Docker, Docker Compose |
| **E-Mail** | SMTP (Hostinger SSL 465) |
| **Reverse Proxy** | Nginx (optional) |
| **Process Management** | Systemd (optional) |
| **Validierung** | Pydantic 2.7+, Email-Validator 2.0+ |

## Systemarchitektur

```
┌─────────────────────────────────────────────────────────┐
│               Frontend Layer (Static HTML)              │
│               docs/ (HTML/CSS/JS Assets)                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ HTTPS/CORS
                   │
┌──────────────────▼──────────────────────────────────────┐
│              FastAPI Backend (main.py)                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          API Layer (REST Endpoints)             │   │
│  │  /health, /api/chat, /api/leads, /api/companies│   │
│  └────────────────┬────────────────────────────────┘   │
│                   │                                     │
│  ┌────────────────▼────────────────────────────────┐   │
│  │  Business Logic Layer (main.py helpers)        │   │
│  │  - Price calculation                           │   │
│  │  - Lead assignment (Round-Robin)               │   │
│  │  - Company budget management                   │   │
│  └────────────────┬────────────────────────────────┘   │
│                   │                                     │
│  ┌────────────────▼────────────────────────────────┐   │
│  │  AI/LLM Integration (app/ai/)                   │   │
│  │  - Dode Chat Agent (agent.py)                  │   │
│  │  - Tool Integration (tools.py)                 │   │
│  │  - FAQ Store (faq_store.py)                    │   │
│  │  - Prompting System (prompts.py)               │   │
│  └────────────────┬────────────────────────────────┘   │
│                   │                                     │
│  ┌────────────────▼────────────────────────────────┐   │
│  │  Data Access Layer (SQLAlchemy ORM)            │   │
│  │  - Companies, Pricing Rules, Leads             │   │
│  │  - Transactions, Chat Events                   │   │
│  └────────────────┬────────────────────────────────┘   │
└───────────────────┼─────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
   ┌────▼─────┐         ┌──────▼───────┐
   │ SQLite   │         │ PostgreSQL   │
   │  (Dev)   │         │  (Prod)      │
   └──────────┘         └──────────────┘
```

## Datenbankschema

### Haupttabellen

**companies**: Partnerunternehmen
- id (Primary Key)
- name, region, services
- daily_budget_eur, max_leads_per_day
- is_active, balance_eur
- api_key (eindeutig)
- last_assigned_at, created_at

**leads**: Kundenanfragen/Leads
- id (Primary Key)
- name, phone, email
- from_city, to_city, rooms, distance_km, express
- message, photo_name
- accepted_agb, accepted_privacy
- company_id (Foreign Key zu companies)
- status (new / assigned / accepted / rejected / completed)
- assigned_price_eur
- created_at

**pricing_rules**: Dynamische Preisregeln
- id (Primary Key)
- company_id (Foreign Key, nullable für Standard-Tarife)
- base_price_eur, price_per_room_eur, price_per_km_eur
- min_price_eur, max_price_eur
- express_multiplier
- active, created_at

**transactions**: Abrechnungsverlauf
- id (Primary Key)
- lead_id, company_id (Foreign Keys)
- amount_eur, status (charged)
- created_at

## Projektstruktur

```
backend/
├── main.py                           # Hauptanwendung (FastAPI)
├── api.py                            # Veraltet (Legacy)
├── requirements.txt                  # Python Dependencies
├── .env.example                      # Environment-Template
├── docker-compose.yml                # Container-Orchestrierung
├── Dockerfile                        # Container-Definition
│
├── app/
│   ├── __init__.py
│   │
│   ├── ai/                           # AI/LLM Integration
│   │   ├── __init__.py
│   │   ├── agent.py                  # Dode Chat Agent Logik
│   │   ├── tools.py                  # Backend-Tool Integration
│   │   ├── prompts.py                # System Prompts
│   │   ├── schemas.py                # Pydantic Datenmodelle
│   │   ├── faq_store.py              # FAQ Knowledge Base
│   │   ├── logging_utils.py          # Event Logging & Analytics
│   │   └── knowledge/                # FAQ Wissensdatenbanken
│   │       └── faq_de.json
│   │
│   └── services/                     # Business Services
│       ├── __init__.py
│       └── emailer.py                # SMTP E-Mail Versand
│
├── deploy/
│   ├── nginx/
│   │   └── api.klarumzug24.de.conf   # Nginx Reverse Proxy Config
│   └── systemd/
│       └── klarumzug24-api.service   # Systemd Service File
│
└── klarumzug.db                      # SQLite DB (dev only)
```

## Installation und Setup

### Voraussetzungen

- Python 3.11+
- PostgreSQL 13+ (für Produktion) oder SQLite (für Entwicklung)
- OpenAI API Schlüssel (für Dode AI)
- Docker & Docker Compose (optional)

### 1. Umgebung vorbereiten

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/MacOS
source venv/bin/activate
```

### 2. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 3. Umgebungsvariablen konfigurieren

Kopiere `.env.example` nach `.env`:

```bash
cp .env.example .env
```

Bearbeite `.env` mit Produktionswerten:

```env
# === DATENBANK ===
DATABASE_URL=postgresql+psycopg://klaruser:STRONG_PASSWORD@localhost:5432/klarumzug24

# === SICHERHEIT ===
ADMIN_API_KEY=CHANGE_ME_SUPER_LONG_RANDOM_KEY

# === API & CORS ===
DEDUP_HOURS=6
ALLOWED_ORIGINS=https://klarumzug24.de,https://www.klarumzug24.de

# === SMTP NOTIFICATIONS ===
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USER=info@klarumzug24.de
SMTP_PASS=CHANGE_ME_EMAIL_PASSWORD
MAIL_TO=info@klarumzug24.de
MAIL_FROM=info@klarumzug24.de

# === DODE AI CHATBOT ===
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
DODE_MODEL=gpt-4o-mini
DODE_MAX_MESSAGES=12
DODE_MAX_OUTPUT_TOKENS=220
```

### 4. Datenbank initialisieren

Die Datenbank wird automatisch beim ersten Start erstellt. Für PostgreSQL:

```bash
# Database und User erstellen
psql -U postgres -c "CREATE DATABASE klarumzug24;"
psql -U postgres -c "CREATE USER klaruser WITH PASSWORD 'STRONG_PASSWORD';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE klarumzug24 TO klaruser;"
```

## Ausführung

### Lokale Entwicklung

```bash
python main.py
```

Server startet auf `http://localhost:8000`

API-Dokumentation (Swagger UI): `http://localhost:8000/docs`
Alternative Dokumentation (ReDoc): `http://localhost:8000/redoc`

### Mit Docker Compose

```bash
# Build und Start
docker-compose up --build

# Im Hintergrund
docker-compose up -d

# Logs anschauen
docker-compose logs -f backend
```

Server läuft auf `http://localhost:8000`

### REPL/Shell für Entwicklung

```bash
python -i main.py
# >>> SessionLocal
# >>> CompanyDB
```

## API Endpoints

### Health & Status

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| GET | `/health` | Health Check | - |

### Preiskalkulation (Öffentlich)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| POST | `/predict` | Quick Price Estimate (ML fallback) | - |
| POST | `/api/predict` | Alias für `/predict` | - |

### Chat & Dode AI (Öffentlich)

| Methode | Endpoint | Beschreibung | Body |
|---------|----------|-------------|------|
| POST | `/api/chat` | Chat mit Dode AI Assistant | `ChatRequestIn` |

**ChatRequestIn Schema:**
```json
{
  "messages": [
    {
      "role": "user|assistant",
      "content": "Nachricht text (1-2000 chars)"
    }
  ],
  "page": "/umzugsrechner.html",
  "lang": "de|en",
  "conversation_id": "conv_xyz..."
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Dode reply generated",
  "data": {
    "reply": "Dode's response text",
    "request_id": "req_abc123...",
    "conversation_id": "conv_xyz..."
  }
}
```

### Lead Management (Öffentlich/Privat)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| POST | `/api/leads` | Neuen Lead erstellen | - |
| GET | `/api/leads` | Alle Leads abrufen | Admin API Key |
| POST | `/contact` | Legacy Contact Form | - |

**LeadIn Schema (multipart/form-data oder JSON):**
```json
{
  "name": "Max Mustermann",
  "phone": "+49 123 456789",
  "email": "max@example.de",
  "from_city": "Berlin",
  "to_city": "München",
  "rooms": 3,
  "distance_km": 750.5,
  "express": false,
  "message": "Nachricht optional",
  "photo_name": "foto.jpg",
  "accepted_agb": true,
  "accepted_privacy": true,
  "conversation_id": "conv_xyz..."
}
```

### Unternehmens-APIs (Admin)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| POST | `/api/companies` | Unternehmen erstellen | Admin API Key |
| GET | `/api/companies` | Alle Unternehmen auflisten | Admin API Key |
| POST | `/api/companies/{id}/topup` | Kontostand aufladen | Admin API Key |

**CompanyIn Schema:**
```json
{
  "name": "Umzugs GmbH",
  "region": "Schleswig-Holstein",
  "services": "Möbeltransport, Montage, Verpackung",
  "daily_budget_eur": 500.0,
  "max_leads_per_day": 10,
  "is_active": true,
  "balance_eur": 0.0
}
```

### Preisregeln (Admin)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| POST | `/api/pricing-rules` | Neue Preisregel erstellen | Admin API Key |
| GET | `/api/pricing-rules` | Alle Preisregeln auflisten | Admin API Key |

**PricingRuleIn Schema:**
```json
{
  "company_id": 1,
  "base_price_eur": 25.0,
  "price_per_room_eur": 15.0,
  "price_per_km_eur": 0.5,
  "min_price_eur": 50.0,
  "max_price_eur": 500.0,
  "express_multiplier": 1.5,
  "active": true
}
```

### Unternehmens-APIs (Company Auth mit X-API-Key)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| GET | `/api/company/me` | Eigenes Profil abrufen | Company API Key |
| GET | `/api/company/leads` | Zugewiesene Leads abrufen | Company API Key |
| POST | `/api/leads/{id}/accept` | Lead akzeptieren | Company API Key |
| POST | `/api/leads/{id}/reject` | Lead ablehnen | Company API Key |

### Transaktionen & Analytics (Admin)

| Methode | Endpoint | Beschreibung | Auth |
|---------|----------|-------------|------|
| GET | `/api/transactions` | Alle Transaktionen auflisten | Admin API Key |
| GET | `/api/admin/invoices/summary` | Abrechnungszusammenfassung | Admin API Key |
| GET | `/api/admin/leads/export` | Leads als CSV exportieren | Admin API Key |
| GET | `/admin` | Admin-Dashboard (HTML) | Admin API Key (Cookie) |

## Authentifizierung

### Admin API Key

Alle `/api/admin/...` und `/api/companies...` Endpoints benötigen den `X-API-Key` Header mit dem Wert von `ADMIN_API_KEY` aus `.env`.

```bash
curl -H "X-API-Key: your-admin-key" https://api.klarumzug24.de/api/companies
```

### Company API Key

Unternehmen authentifizieren sich mit ihrem eindeutigen `api_key`:

```bash
curl -H "X-API-Key: kp_xxxxx..." https://api.klarumzug24.de/api/company/me
```

## Dode AI Chat Assistant

Dode ist der intelligente, mehrsprachige Chat-Assistent für Kunden:

### Funktionalität

- **Natürlichsprachige Interaktion**: Konversatives Interface ohne Formulare
- **Strukturdatenextraktion**: Erkennt Umzugsdetails aus freien Texten (Städte, Zimmer, Entfernungen)
- **Intelligent Pricing**: Ruft Backend-Preislogik auf (NICHT erfunden)
- **FAQ Integration**: Zugriff auf Wissensdatenbank
- **Multi-Language**: Deutsch und Englisch
- **Audit Trail**: Alle Interaktionen werden geloggt

### Gesprächsablauf

1. **Greeting & Datensammlung**
   - Begrüßung durch Dode
   - Fragen nach fehlenden Umzugsdetails (max 2 Fragen pro Nachricht)

2. **Preis-Kalkulierung**
   - Dode ruft `calculate_move_price` Tool auf
   - Zeigt unverbindliche Schätzung mit Erklärung

3. **Lead-Erstellung (optional)**
   - Falls Kunde Kontaktdaten bereitstellt + Intent vorhanden
   - Dode erstellt Lead über `create_lead` Tool

### System Prompt (Auszug)

```
Du bist Dode, der Website-Assistent von Klarumzug24.

Regeln:
- Antworte freundlich, klar, professionell und knapp (2-4 Sätze)
- Keine Emojis oder Markdown-Links
- Erfinde KEINE Fakten oder Preise
- Bei Preisfragen: "Das ist eine unverbindliche Schätzung"
- Stelle maximal 2 Fragen pro Nachricht

Verfügbare Tools:
- calculate_move_price(from_city, to_city, rooms, distance_km, express)
- create_lead(name, phone, email, move_details)
- get_faq(query)

Verkehrsregion: Bordesholm, Schleswig-Holstein

Kontakt: +49 163 615 7234 | info@klarumzug24.de | WhatsApp
```

## Preiskalkulierung

### Automatische Preisberechnung

Die Preisberechnung basiert auf **Preisregeln** pro Unternehmen:

```
price = base_price 
       + (rooms × price_per_room) 
       + (distance_km × price_per_km)

if express:
    price = price × express_multiplier

price = max(min_price, min(price, max_price))
```

### Fallback Logik

Wenn keine Regel definiert:
```
fallback = 35 (if cities given) or 25
         + (rooms × 2)
         + (distance × 0.3)

if express:
    fallback = fallback × 1.2
```

## Lead-Zuordnungssystem

Automatische Round-Robin Verteilung an Partnerunternehmen:

1. **Filterung**
   - Nur aktive Unternehmen
   - Tages-Budget nicht überschritten
   - max_leads_per_day nicht erreicht
   - Kontostand >= quoted_price

2. **Sortierung** (FIFO Round-Robin)
   - Unternehmen ohne Assignment zuerst
   - Dann: älteste Assignment zuerst
   - Dann: ID aufsteigend

3. **Preis-Berechnung**
   - Für jedes Unternehmen: eigene Preisregel anwenden
   - Kontostand vor Zuweisung prüfen

## Datenschutz & Lead-Sichtbarkeit

### Öffentliche Lead-Erstellung

Leadformular sichtbar für Kunden (ohne Admin-Auth):
- Nur essenzielle Felder: Name, Phone, Email
- AGB + Datenschutz Opt-ins erforderlich

### PII Masking

Unternehmen sehen Leads mit maskierten Daten:
```json
{
  "id": 123,
  "from_city": "Berlin",
  "to_city": "München",
  "name": null,
  "phone": "****6789",
  "email": "m***@example.de"
}
```

### Vollzugriff

Nur Admin-Dashboard:
- Volständige PII
- Alle Transaktionen
- Export-Funktionen

## Event Logging & Analytics

Alle Chat-Events werden geloggt:

```json
{
  "timestamp": "2026-03-28T10:30:00.123Z",
  "event_type": "chat_request_received",
  "request_id": "req_abc123...",
  "conversation_id": "conv_xyz...",
  "lang": "de",
  "last_user_message": "[sanitized]",
  "success": true,
  "duration_ms": 1234
}
```

### Verfügbare Berichte

- Chat Conversion Rate
- Lead-to-Company Assignment Erfolgsquote
- Revenue Summary (Admin)
- CSV Lead Export

## Entwicklung

### Lokale Entwicklung Setup

```bash
# 1. Virtual Env
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate

# 2. Dependencies
pip install -r requirements.txt

# 3. .env
cp .env.example .env
# Edit DATABASE_URL für SQLite oder PostgreSQL

# 4. Run
python main.py
```

### Datenbank zurücksetzen (SQLite)

```bash
rm klarumzug.db
python main.py  # Erstellt neue DB automatisch
```

### Testen von Dode

Nutze Swagger UI: `http://localhost:8000/docs`

```json
POST /api/chat
{
  "messages": [
    {"role": "user", "content": "Ich ziehe von Berlin nach München, ca. 3 Zimmer"}
  ],
  "lang": "de"
}
```

### Testen von Admin APIs

```bash
# Companies erstellen
curl -X POST http://localhost:8000/api/companies \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "TestUmzug GmbH", "region": "Berlin", "balance_eur": 1000}'
```

## Deployment

### Docker Compose (Single Container)

```bash
docker-compose up -d

# Logs
docker-compose logs -f backend

# Stop
docker-compose down
```

Container läuft auf `http://localhost:8000`

### Systemd Service (Linux Production)

```bash
# 1. ServiceFile installieren
sudo cp deploy/systemd/klarumzug24-api.service /etc/systemd/system/

# 2. Reload und Start
sudo systemctl daemon-reload
sudo systemctl enable klarumzug24-api
sudo systemctl start klarumzug24-api

# 3. Status
sudo systemctl status klarumzug24-api
sudo journalctl -u klarumzug24-api -f
```

### Nginx Reverse Proxy

```bash
sudo cp deploy/nginx/api.klarumzug24.de.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/api.klarumzug24.de.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

ProxyPass: `http://localhost:8000` → `https://api.klarumzug24.de`

### Datenbank (PostgreSQL)

```bash
# Backup
pg_dump -U klaruser klarumzug24 > backup.sql

# Restore
psql -U klaruser klarumzug24 < backup.sql
```

## Fehlerbehebung

### OpenAI API Fehler

- Überprüfe `OPENAI_API_KEY` ist gesetzt
- Teste API Key: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
- Prüfe Rate Limits

### Datenbank-Fehler

**SQLite Locked:**
```bash
rm *.db-journal
```

**PostgreSQL Connection:**
```bash
# Test Connection
psql -h localhost -U klaruser -d klarumzug24 -c "SELECT 1"
```

### CORS Fehler

```
Access-Control-Allow-Origin unauthorized
```

Lösung: `ALLOWED_ORIGINS` in `.env` aktualisieren und Service neustarten

### Email Versand schlägt fehl

```bash
# Test SMTP
python -c "
import smtplib
server = smtplib.SMTP_SSL('smtp.hostinger.com', 465)
server.login('info@klarumzug24.de', 'password')
print('OK')
"
```

## Umgebungsvariablen Referenz

| Variable | Type | Default | Beschreibung |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | `sqlite:///./klarumzug.db` | DB Connection String |
| `ADMIN_API_KEY` | string | - | **Erforderlich**: Admin Auth Token |
| `OPENAI_API_KEY` | string | - | **Erforderlich**: OpenAI API Schlüssel |
| `DODE_MODEL` | string | `gpt-4o-mini` | Welches LLM Model nutzen |
| `DODE_MAX_MESSAGES` | int | `12` | Max. Nachrichten pro Chat Session |
| `DODE_MAX_OUTPUT_TOKENS` | int | `220` | Max. Tokens pro Dode Response |
| `DEDUP_HOURS` | int | `6` | Lead Deduplizierung Fenster |
| `ALLOWED_ORIGINS` | string | `http://localhost:8080,...` | CORS Whitelist |
| `SMTP_HOST` | string | `smtp.hostinger.com` | SMTP Server Host |
| `SMTP_PORT` | int | `465` | SMTP Server Port |
| `SMTP_USER` | string | - | SMTP Benutzername |
| `SMTP_PASS` | string | - | SMTP Passwort |
| `MAIL_FROM` | string | `$SMTP_USER` | Von-Adresse |
| `MAIL_TO` | string | - | Benachrichtigungen an |

## Implementierungsstatus

### Vollständig implementiert ✅

- FastAPI Backend mit Swagger UI/ReDoc
- SQLAlchemy ORM mit Auto-Migration
- Dode AI Chat Assistant (Deutsch + Englisch)
- Dynamische Preiskalkulierung mit Regeln
- Round-Robin Lead-Zuordnung mit Budget-Tracking
- Company Management & Authentifizierung
- Admin Dashboard (HTML)
- Email Benachrichtigungen (SMTP)
- Event Logging & Analytics
- Docker Containerisierung
- Systemd Service Integration

### Experimentell / Geplant 📋

- ML-basierte Preisoptimierung (Modell existiert, Standard-Tarife bevorzugt)
- Photo Upload & Storage (Basis-Struktur vorhanden)
- Advanced Analytics & Reporting (CSV Export vorhanden)

### Veraltet ⚠️

- `backend/api.py` (deprecated. Use `main.py` stattdessen)

## Performance & Limits

- **Max Chat Messages**: 12 pro Session
- **Max Output Tokens**: 220 pro Dode Response
- **Max Photo Size**: 10 MB
- **Max Message Length**: 2000 Zeichen
- **Max Form Data**: multipart/form-data supported
- **Request Timeout**: Standard FastAPI (60s default)
- **SQLite Concurrent Writes**: Begrenzt → PostgreSQL für Produktion empfohlen

## Lizenz

Siehe [LICENSE](../LICENSE)

## Kontakt & Support

- Projektübersicht: Siehe [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)
- Geschäftsregeln: Siehe [BUSINESS_RULES.md](../BUSINESS_RULES.md)
- Tool-Spec: Siehe [TOOLS_SPEC.md](../TOOLS_SPEC.md)
- Bug Reports: Issues im Repository erstellen

---

**Projekt Status**: Aktiv in Produktion (März 2026)  
**Version**: 1.0 (Stable)  
**Last Updated**: 28.03.2026
