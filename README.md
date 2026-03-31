# Klarumzug24 – Digitale Umzugsplattform

> **Intelligente Umzugspreiskalkulation mit KI-Chat-Assistent, Lead-Management und Unternehmensintegration.**

---

## Überblick

Klarumzug24 ist eine moderne B2B2C-Plattform, die Privatkunden bei der Umzugsplanung unterstützt und sie automatisiert mit passenden Umzugsunternehmen verbindet. Das System umfasst einen KI-gesteuerten Chat-Assistenten (**Dode**), dynamische Preiskalkulation und automatische Lead-Verteilung.

### Kernfunktionen

- **KI-Chat-Assistent (Dode)** – Natürlichsprachige Kundeninteraktion auf Deutsch & Englisch
- **Dynamische Preiskalkulation** – Regelbasierte Preisberechnung mit Unternehmens-Spezifiken
- **Lead-Management** – Automatische Round-Robin-Verteilung an Partnerunternehmen
- **Admin-Dashboard** – Verwaltung von Unternehmen, Preisregeln, Transaktionen & Analytics
- **Privacy-by-Design** – PII-Maskierung für nicht akzeptierte Leads
- **E-Mail-Benachrichtigungen** – Automatische Alerts bei neuen Leads

---

## Technologie-Stack

| Komponente | Technologie |
|---|---|
| **Backend** | FastAPI 0.115+ (Python 3.11) |
| **Datenbank** | SQLite (Entwicklung) / PostgreSQL 3.1+ (Produktion) |
| **ORM** | SQLAlchemy 2.0+ |
| **KI/LLM** | OpenAI GPT-4.1-mini (Dode Chat-Assistent) |
| **Frontend** | Statisches HTML/CSS/JS (Nginx) |
| **Containerisierung** | Docker & Docker Compose |
| **E-Mail** | SMTP (Hostinger SSL 465) |
| **Validierung** | Pydantic 2.7+ |

---

## Projektstruktur

```
klarumzug24/
├── backend/                    # FastAPI Backend
│   ├── main.py                 # Hauptanwendung & API-Startpunkt
│   ├── requirements.txt        # Python Dependencies
│   ├── Dockerfile              # Backend Container
│   ├── docker-compose.yml      # Backend-Only Compose
│   │
│   ├── app/
│   │   ├── ai/                 # KI-Layer (Dode)
│   │   │   ├── agent.py        # Chat-Agent Orchestrierung
│   │   │   ├── tools.py        # Backend-Tool Integration
│   │   │   ├── prompts.py      # System Prompts
│   │   │   ├── pricing_calculator.py  # Preisberechnung
│   │   │   ├── intent_classifier.py   # Intent-Erkennung
│   │   │   ├── schemas.py      # KI-Datenmodelle
│   │   │   └── knowledge/      # FAQ Wissensdatenbank
│   │   │
│   │   ├── api/routes/         # REST API Endpoints
│   │   ├── models/             # SQLAlchemy ORM Modelle
│   │   ├── schemas/            # Pydantic Validierung
│   │   ├── services/           # Business-Logik Services
│   │   ├── core/               # Konfiguration & Sicherheit
│   │   └── utils/              # Hilfsfunktionen
│   │
│   └── deploy/                 # Deployment-Dateien
│       ├── nginx/              # Reverse Proxy Config
│       └── systemd/            # Service-Dateien
│
├── docs/                       # Frontend (Static HTML)
│   ├── index.html              # Startseite
│   ├── umzugsrechner.html      # Umzugsrechner mit Chat
│   ├── kontakt.html            # Kontaktformular
│   ├── agb.html                # AGB
│   ├── datenschutz.html        # Datenschutzerklärung
│   ├── impressum.html          # Impressum
│   ├── ueber-uns.html          # Über uns
│   ├── Dockerfile              # Frontend Container (Nginx)
│   └── assets/
│       ├── dode-chat.js        # Chat-Widget
│       ├── dode-chat.css       # Chat-Styling
│       └── site.css            # Seiten-Styling
│
├── docker-compose.yml          # Gesamtplattform Compose
├── BUSINESS_RULES.md           # Geschäftsregeln
├── TOOLS_SPEC.md               # KI-Tool Spezifikation
├── DEPLOYMENT_GUIDE.md         # Deployment-Anleitung
└── LICENSE                     # MIT Lizenz
```

---

## Schnellstart

### Voraussetzungen

- Python 3.11+
- OpenAI API Key
- Docker & Docker Compose (optional)

### Option 1: Lokale Entwicklung

```bash
# 1. Repository klonen
git clone <repo-url>
cd klarumzug24

# 2. Backend vorbereiten
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen setzen
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# .env bearbeiten: OPENAI_API_KEY und ADMIN_API_KEY setzen

# 5. Server starten
python main.py
```

Server läuft auf: `http://localhost:8000`
API-Dokumentation: `http://localhost:8000/docs`

### Option 2: Docker Compose

```bash
# .env Datei im Root erstellen (siehe .env.example)

# Build & Start
docker-compose up --build -d

# Logs prüfen
docker-compose logs -f
```

Plattform erreichbar auf: `http://localhost:8080`

---

## API Endpoints

### Öffentlich

| Methode | Endpoint | Beschreibung |
|---|---|---|
| `GET` | `/health` | Health Check |
| `POST` | `/api/chat` | Chat mit Dode KI-Assistent |
| `POST` | `/api/leads` | Neuen Lead erstellen |
| `POST` | `/api/predict` | Preisschätzung |
| `POST` | `/contact` | Kontaktformular |

### Unternehmen (X-API-Key)

| Methode | Endpoint | Beschreibung |
|---|---|---|
| `GET` | `/api/company/me` | Eigenes Profil |
| `GET` | `/api/company/leads` | Zugewiesene Leads |
| `POST` | `/api/leads/{id}/accept` | Lead akzeptieren |
| `POST` | `/api/leads/{id}/reject` | Lead ablehnen |

### Admin (X-API-Key)

| Methode | Endpoint | Beschreibung |
|---|---|---|
| `GET` | `/api/companies` | Alle Unternehmen |
| `POST` | `/api/companies` | Unternehmen erstellen |
| `POST` | `/api/companies/{id}/topup` | Guthaben aufladen |
| `GET/POST` | `/api/pricing-rules` | Preisregeln verwalten |
| `GET` | `/api/transactions` | Transaktionen |
| `GET` | `/api/admin/invoices/summary` | Abrechnungsübersicht |
| `GET` | `/api/admin/leads/export` | Leads als CSV exportieren |
| `GET` | `/admin` | Admin-Dashboard |

---

## Dode – KI-Chat-Assistent

Dode ist der integrierte Chat-Assistent auf der Umzugsrechner-Seite:

### Gesprächsablauf

```
Kunde: "Ich ziehe von Hamburg nach Kiel, 3 Zimmer"
  ↓
Dode erkennt: from=Hamburg, to=Kiel, rooms=3
  ↓
Dode ruft calculate_move_price auf
  ↓
Dode: "Für Ihren Umzug von Hamburg nach Kiel (3 Zimmer, ~90 km)
       schätzen wir ca. 450–620 €. Das ist eine unverbindliche
       Schätzung. Möchten Sie ein konkretes Angebot?"
```

### KI-Tools

| Tool | Funktion |
|---|---|
| `calculate_move_price` | Preisberechnung basierend auf Umzugsdetails |
| `create_lead` | Lead-Erstellung mit Kontaktdaten |
| `get_matching_companies` | Passende Unternehmen finden |

### Sicherheitsregeln

- Preise werden **immer** vom Backend berechnet – nie vom LLM erfunden
- Alle Preise als **unverbindliche Schätzung** gekennzeichnet
- Fehlende Daten werden erfragt, nie angenommen
- Max. 2 Fragen pro Nachricht

---

## Preiskalkulation

```
Preis = Basispreis + (Zimmer × Preis/Zimmer) + (Entfernung × Preis/km)

Bei Express-Umzug:
  Preis = Preis × Express-Multiplikator

Preis = max(Mindestpreis, min(Preis, Höchstpreis))
```

Jedes Partnerunternehmen kann eigene Preisregeln definieren. Bei fehlenden Regeln greift eine Standard-Fallback-Logik.

---

## Lead-Verteilung

Automatische Round-Robin-Zuordnung:

1. **Filterung** – Nur aktive Unternehmen mit Budget & Kapazität
2. **Sortierung** – FIFO nach letzter Zuweisung
3. **Prüfung** – Kontostand muss ausreichen
4. **Zuweisung** – Lead wird zugewiesen, Transaktion erstellt

### Datenschutz

- Leads enthalten **maskierte PII** (Telefonnummer, E-Mail) bis zur Akzeptierung
- Vollzugriff nur über Admin-Dashboard

---

## Umgebungsvariablen

| Variable | Erforderlich | Beschreibung |
|---|---|---|
| `OPENAI_API_KEY` | Ja | OpenAI API Schlüssel |
| `ADMIN_API_KEY` | Ja | Admin-Authentifizierung |
| `DATABASE_URL` | Nein | DB Connection String (Default: SQLite) |
| `DODE_MODEL` | Nein | LLM Modell (Default: `gpt-4.1-mini`) |
| `ALLOWED_ORIGINS` | Nein | CORS Whitelist |
| `SMTP_HOST` | Nein | SMTP Server für E-Mail |
| `SMTP_PORT` | Nein | SMTP Port (Default: 465) |
| `SMTP_USER` | Nein | SMTP Benutzername |
| `SMTP_PASS` | Nein | SMTP Passwort |

---

## Deployment

### Warum systemd + Nginx statt Docker in Produktion?

Klarumzug24 besteht aus einem einzelnen FastAPI-Backend und statischen HTML-Dateien. Für dieses Setup ist Bare-Metal-Deployment mit systemd + Nginx die beste Wahl:

- **Einfacher**: Kein Container-Layer zwischen Anwendung und OS
- **Schneller**: Kein Docker-Overhead, direkter Zugriff auf System-Ressourcen
- **Debugbar**: `journalctl`, `systemctl status`, direkte Log-Dateien
- **Stabil**: systemd überwacht den Prozess und startet ihn bei Absturz automatisch neu
- **SSL nativ**: Let's Encrypt + certbot integiert sich direkt mit Nginx

Docker bleibt im Repository für lokale Entwicklung verfügbar, wird aber **nicht** für Produktion verwendet.

### Architektur (Produktion)

```
GitHub (main branch)
  │
  │  push → GitHub Actions
  │
  ▼
┌──────────────────────────────────────────┐
│  Ubuntu VPS                              │
│                                          │
│  Nginx (:443 SSL)                        │
│  ├─ klarumzug24.de → /var/www/html       │
│  └─ /api/* → proxy 127.0.0.1:8000       │
│                                          │
│  systemd: klarumzug24-api                │
│  └─ uvicorn main:app (:8000, 3 workers)  │
│                                          │
│  /opt/klarumzug24/       ← Git Repo      │
│  /opt/klarumzug24/backend/.env  ← lokal  │
│  /var/www/html/          ← Frontend      │
└──────────────────────────────────────────┘
```

### Deployment-Ablauf

Push auf `main` → GitHub Actions verbindet per SSH → führt `deploy.sh` aus:

1. **Backup** – Aktueller Stand wird gesichert (commit hash + app-Dateien)
2. **Git Pull** – Neuester Code wird geholt (`git reset --hard origin/main`)
3. **Dependencies** – Nur aktualisiert wenn `requirements.txt` sich ändert
4. **Frontend** – Nur synchronisiert wenn `docs/` sich ändert
5. **Restart** – `systemctl restart klarumzug24-api`
6. **Health Check** – Wartet auf HTTP 200 von `/health` (max. 30s)
7. **Auto-Rollback** – Bei fehlgeschlagenem Health Check wird automatisch auf vorherigen Commit zurückgerollt
8. **Nginx Reload** – Nur wenn Nginx-Configs oder Frontend-Dateien sich geändert haben

### GitHub Secrets (erforderlich)

| Secret | Beschreibung | Beispiel |
|---|---|---|
| `SERVER_HOST` | VPS IP-Adresse oder Hostname | `123.45.67.89` |
| `SERVER_USER` | SSH-Benutzer | `root` |
| `SERVER_SSH_KEY` | Privater SSH-Schlüssel (vollständiger Inhalt) | `-----BEGIN OPENSSH...` |
| `SERVER_PORT` | SSH-Port (optional, Standard: 22) | `22` |

Einrichtung: GitHub Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

> **Hinweis:** SSH nutzt `StrictHostKeyChecking=no` — kein Fingerprint-Secret erforderlich.

### Server erstmalig einrichten

```bash
# 1. Git installieren (falls nicht vorhanden)
apt update && apt install -y git rsync curl

# 2. Repository klonen
git clone git@github.com:DEIN-USER/klarumzug24.git /opt/klarumzug24

# 3. Python Umgebung erstellen
cd /opt/klarumzug24/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. .env erstellen (Server-lokal, wird nie committed)
cp .env.example .env
nano .env   # Alle Werte mit echten Produktionsdaten füllen

# 5. Frontend deployen
rsync -a --delete --exclude='Dockerfile' --exclude='nginx.conf' \
    /opt/klarumzug24/docs/ /var/www/html/

# 6. Systemd Service installieren
cp /opt/klarumzug24/backend/deploy/systemd/klarumzug24-api.service \
   /etc/systemd/system/
systemctl daemon-reload
systemctl enable klarumzug24-api
systemctl start klarumzug24-api

# 7. Deploy-Script ausführbar machen
chmod +x /opt/klarumzug24/deploy.sh

# 8. Backup-Verzeichnis erstellen
mkdir -p /opt/klarumzug24/backups

# 9. Prüfen ob alles läuft
systemctl status klarumzug24-api
curl -s http://127.0.0.1:8000/health
```

### Manuelles Deployment (ohne GitHub Actions)

```bash
ssh root@DEIN-SERVER "cd /opt/klarumzug24 && bash deploy.sh"
```

### Verifikation nach Deployment

```bash
# Service-Status
systemctl status klarumzug24-api

# Health Check (lokal auf dem Server)
curl -s http://127.0.0.1:8000/health

# Health Check (öffentlich)
curl -s https://klarumzug24.de/health

# Nginx Status
systemctl status nginx

# Aktueller Commit
cd /opt/klarumzug24 && git log --oneline -1

# Letzte Logs
journalctl -u klarumzug24-api --since "5 min ago" --no-pager
```

### Rollback

```bash
# AUTOMATISCH: deploy.sh rollt bei Health-Check-Fehler selbst zurück

# MANUELL auf bestimmten Commit:
ssh root@DEIN-SERVER
cd /opt/klarumzug24
git log --oneline -5                          # Commits anzeigen
git reset --hard <COMMIT-HASH>                # Zurücksetzen
systemctl restart klarumzug24-api             # Neustarten
curl -s http://127.0.0.1:8000/health          # Verifizieren

# NOTFALL: Backup wiederherstellen
ls /opt/klarumzug24/backups/                  # Verfügbare Backups
cp -r /opt/klarumzug24/backups/YYYYMMDD_HHMMSS/app \
      /opt/klarumzug24/backend/app
systemctl restart klarumzug24-api
```

---

## Weiterführende Dokumentation

| Dokument | Inhalt |
|---|---|
| [backend/README.md](backend/README.md) | Ausführliche Backend-Dokumentation & API-Referenz |
| [BUSINESS_RULES.md](BUSINESS_RULES.md) | Geschäftsregeln & Preislogik |
| [TOOLS_SPEC.md](TOOLS_SPEC.md) | KI-Tool Spezifikation |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Schritt-für-Schritt Deployment |
| [DEPLOY_DOCKER.md](DEPLOY_DOCKER.md) | Docker-Setup Anleitung |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Projektübersicht |

---

## Lizenz

MIT License – Copyright (c) 2026 Ahmed Dadoue

Siehe [LICENSE](LICENSE) für Details.

---

## Kontakt

- **E-Mail**: info@klarumzug24.de
- **Telefon**: +49 163 615 7234
- **WhatsApp**: +49 163 615 7234
- **Standort**: Bordesholm, Schleswig-Holstein
