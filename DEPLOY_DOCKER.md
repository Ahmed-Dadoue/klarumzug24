# Docker-Deployment fuer Klarumzug24

## Aktuelle Laufstruktur

- Backend: FastAPI in `backend/main.py`
- Uvicorn-Entrypoint: `main:app`
- Frontend: statische Seite in `docs/`
- Compose-Datei: `docker-compose.yml` im Projekt-Root
- Standard-DB im Docker-Setup: SQLite per named volume

## Warum aktuell kein PostgreSQL im Compose enthalten ist

Der aktuelle Code ist zur Laufzeit noch SQLite-spezifisch:

- `backend/app/core/database.py` setzt immer `check_same_thread`
- `ensure_schema()` verwendet `PRAGMA table_info(...)`

Dadurch ist PostgreSQL im jetzigen Stand nicht sauber produktionsreif verdrahtet. Das neue Docker-Setup haelt deshalb die bestehende Logik intakt und nutzt zunaechst SQLite mit persistentem Volume.

## Dateien

- Backend Dockerfile: `backend/Dockerfile`
- Frontend Dockerfile: `docs/Dockerfile`
- Frontend Nginx Config: `docs/nginx.conf`
- Compose: `docker-compose.yml`
- Env Template: `.env.example`

## Vorbereitung

1. Root-Env-Datei anlegen:

```bash
cp .env.example .env
```

2. Werte in `.env` setzen:

- `ADMIN_API_KEY`
- `OPENAI_API_KEY`
- SMTP-Werte, falls Lead-Mails versendet werden sollen
- `ALLOWED_ORIGINS` mit Ihrer echten Domain

## Start lokal oder auf dem VPS

```bash
docker compose up --build -d
```

Logs pruefen:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

Status pruefen:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/health
```

## Wichtige Netzwerkinfo

Im Compose-Setup laeuft das Frontend ueber Nginx und leitet `/api/*` intern an den Backend-Service `backend:8000` weiter. Dadurch funktionieren die vorhandenen relativen Frontend-Requests wie `/api/leads` und `/api/chat` ohne Codeaenderung.

## VPS-Empfehlung

- Port `8080` nur intern oder testweise offenlegen
- In Produktion idealerweise einen vorgeschalteten Host-Nginx oder Traefik fuer HTTPS verwenden
- Die Domain auf den Frontend-Container routen
- Regelmaessige Backups fuer das Docker-Volume `backend_data` einrichten

## Deployment-Befehle auf Ubuntu VPS

```bash
git clone <repo-url> klarumzug24
cd klarumzug24
cp .env.example .env
nano .env
docker compose up --build -d
docker compose ps
docker compose logs -f
```

## Spaetere PostgreSQL-Umstellung

Vor einer PostgreSQL-Umstellung sollte zuerst die DB-Schicht angepasst werden, damit:

- SQLite-spezifische `connect_args` nur fuer SQLite gesetzt werden
- `PRAGMA`-Migrationen nicht fuer PostgreSQL ausgefuehrt werden
- das Schema sauber datenbankunabhaengig initialisiert oder migriert wird
