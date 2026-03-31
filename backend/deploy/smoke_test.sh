#!/bin/bash
echo "== HEALTH LOCAL =="
curl -sS -m 5 http://127.0.0.1:8000/health
echo

echo "== HEALTH PUBLIC =="
curl -sS -m 8 https://klarumzug24.de/health
echo

echo "== API COMPANIES (expect 401) =="
curl -sS -m 5 -o /dev/null -w "HTTP %{http_code}" https://klarumzug24.de/api/companies
echo

echo "== HOMEPAGE =="
curl -sS -m 5 -o /dev/null -w "HTTP %{http_code}" https://klarumzug24.de/
echo

echo "== CHAT TEST =="
curl -sS -m 15 -X POST https://klarumzug24.de/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hallo"}],"lang":"de"}'
echo

echo "== DONE =="
