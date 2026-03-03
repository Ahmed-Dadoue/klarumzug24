# Klarumzug24 Production Deployment (Hostinger VPS - Ubuntu)

## 0) Prerequisites
- VPS OS: Ubuntu 22.04 or 24.04
- DNS A record: `api.klarumzug24.de` -> VPS IP
- This backend code is on VPS under: `/opt/klarumzug24/backend`

## 1) Server bootstrap

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx python3 python3-venv python3-pip git ufw postgresql postgresql-contrib certbot python3-certbot-nginx

sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status
```

## 2) App files

Option A (Git):

```bash
cd /opt
sudo git clone YOUR_REPO_URL klarumzug24
sudo chown -R $USER:$USER /opt/klarumzug24
```

Option B (SFTP/WinSCP):
- Upload project to `/opt/klarumzug24`

## 3) Python environment

```bash
cd /opt/klarumzug24/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE klarumzug24;
CREATE USER klaruser WITH PASSWORD 'STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE klarumzug24 TO klaruser;
\q
```

## 5) Environment config

```bash
cd /opt/klarumzug24/backend
cp .env.example .env
nano .env
```

Set real values:

```dotenv
DATABASE_URL=postgresql+psycopg://klaruser:STRONG_PASSWORD@localhost:5432/klarumzug24
ADMIN_API_KEY=CHANGE_ME_SUPER_LONG_RANDOM_KEY
ALLOWED_ORIGINS=https://klarumzug24.de,https://www.klarumzug24.de
DEDUP_HOURS=6
```

Note:
- This app uses `psycopg` (from `requirements.txt`), so URL must be `postgresql+psycopg://...`

## 6) Local service smoke test

```bash
cd /opt/klarumzug24/backend
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Stop with `Ctrl + C`.

## 7) systemd (always-on API)

```bash
cd /opt/klarumzug24/backend
sudo cp deploy/systemd/klarumzug24-api.service /etc/systemd/system/klarumzug24-api.service
sudo systemctl daemon-reload
sudo systemctl enable klarumzug24-api
sudo systemctl start klarumzug24-api
sudo systemctl status klarumzug24-api --no-pager

curl http://127.0.0.1:8000/health
```

## 8) Nginx reverse proxy

```bash
cd /opt/klarumzug24/backend
sudo cp deploy/nginx/api.klarumzug24.de.conf /etc/nginx/sites-available/api.klarumzug24.de
sudo ln -s /etc/nginx/sites-available/api.klarumzug24.de /etc/nginx/sites-enabled/api.klarumzug24.de
sudo nginx -t
sudo systemctl reload nginx
```

## 9) HTTPS (Let's Encrypt)

```bash
sudo certbot --nginx -d api.klarumzug24.de
```

## 10) Final tests

```bash
curl https://api.klarumzug24.de/health
curl -H "X-API-Key: YOUR_ADMIN_API_KEY" https://api.klarumzug24.de/api/companies
```

Expected:
- `/health` -> 200
- `/api/companies` without key -> 401
- `/api/companies` with admin key -> 200

## 11) Frontend integration
Update the form submit URL in frontend to:
- `https://api.klarumzug24.de/api/leads`

## 12) Operations (recommended)

```bash
sudo journalctl -u klarumzug24-api -f
```

Simple daily DB backup:

```bash
pg_dump "postgresql://klaruser:STRONG_PASSWORD@localhost:5432/klarumzug24" > /opt/klarumzug24/backup-$(date +%F).sql
```
