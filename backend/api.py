"""
Deprecated legacy API module.

This file is kept temporarily to avoid breaking older local workflows, but
`backend/main.py` is the only active API entrypoint that should be used going
forward.
"""

import json
import os
import smtplib
import warnings
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import joblib
import numpy as np
from starlette.exceptions import HTTPException as StarletteHTTPException

warnings.warn(
    "backend.api is deprecated. Use backend.main:app as the active API entrypoint.",
    DeprecationWarning,
    stacklevel=2,
)

app = FastAPI(title="Klarumzug24 Deprecated API")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,https://klarumzug24.de,https://www.klarumzug24.de",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "umzug_preis_model.pkl"
CONTACT_LOG_PATH = BASE_DIR / "contact_requests.jsonl"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_TO = os.getenv("MAIL_TO", "")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USER)

model = joblib.load(MODEL_PATH)

class UmzugRequest(BaseModel):
    qm: int = Field(ge=0, le=10000)
    kartons: int = Field(ge=0, le=5000)
    fahrstuhl: int = Field(ge=0, le=1)
    stockwerk: int = Field(ge=0, le=200)
    distanz_meter: int = Field(ge=0, le=200000)
    schraenke: int = Field(ge=0, le=500)
    waschmaschine: int = Field(ge=0, le=100)
    fernseher: int = Field(ge=0, le=100)
    montage: int = Field(ge=0, le=1)


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=4, max_length=40)
    message: str = Field(default="", max_length=5000)
    photo_name: Optional[str] = Field(default=None, max_length=255)


def success_response(message: str, data: dict) -> dict:
    payload = {
        "ok": True,
        "message": message,
        "data": data,
    }
    payload.update(data)
    return payload


def error_response(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": error,
            "message": message,
        },
    )


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=422, detail="phone is required")

    if digits.startswith("0049"):
        national_number = digits[4:]
    elif digits.startswith("49"):
        national_number = digits[2:]
    elif digits.startswith("0"):
        national_number = digits[1:]
    else:
        raise HTTPException(status_code=422, detail="phone must start with 0, 49, +49 or 0049")

    if national_number.startswith("0"):
        national_number = national_number[1:]

    if not national_number.isdigit() or len(national_number) < 6 or len(national_number) > 13:
        raise HTTPException(status_code=422, detail="phone is invalid")

    return f"+49{national_number}"


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(exc.status_code, "request_error", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {"msg": "Invalid request payload"}
    field = ".".join(str(item) for item in first.get("loc", ()) if item != "body")
    message = f"{field}: {first.get('msg')}" if field else first.get("msg", "Invalid request payload")
    return error_response(422, "validation_error", message)


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, __: Exception) -> JSONResponse:
    return error_response(500, "internal_error", "Internal server error")


def _append_contact_log(contact_data: dict) -> None:
    entry = {
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        **contact_data,
    }
    with CONTACT_LOG_PATH.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_contact_email(contact_data: dict) -> None:
    if not SMTP_USER or not SMTP_PASS or not MAIL_TO:
        raise HTTPException(
            status_code=500,
            detail="E-Mail-Konfiguration fehlt auf dem Server.",
        )

    msg = EmailMessage()
    msg["Subject"] = f"Neue Kontaktanfrage von {contact_data['name']}"
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO

    body = f"""
Neue Kontaktanfrage von der Website

Name: {contact_data['name']}
E-Mail: {contact_data['email']}
Telefon: {contact_data['phone']}
Foto: {contact_data.get('photo_name', '')}

Nachricht:
{contact_data['message']}
"""
    msg.set_content(body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

@app.post("/predict")
def predict_price(req: UmzugRequest):
    x = np.array([[req.qm, req.kartons, req.fahrstuhl, req.stockwerk,
                   req.distanz_meter, req.schraenke, req.waschmaschine,
                   req.fernseher, req.montage]])
    preis = model.predict(x)[0]
    result = {"estimated_price_eur": round(float(preis), 2)}
    return success_response("Price estimate calculated.", result)


@app.post("/contact")
def submit_contact(req: ContactRequest):
    cleaned = {
        "name": req.name.strip(),
        "email": req.email.strip(),
        "phone": normalize_phone(req.phone),
        "message": req.message.strip(),
        "photo_name": (req.photo_name or "").strip(),
    }

    if not cleaned["name"] or not cleaned["email"] or not cleaned["phone"]:
        raise HTTPException(status_code=422, detail="Name, E-Mail und Telefon sind erforderlich.")

    try:
        _append_contact_log(cleaned)
        send_contact_email(cleaned)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="Kontaktanfrage konnte nicht gespeichert werden.",
        ) from error
    except smtplib.SMTPException as error:
        raise HTTPException(
            status_code=500,
            detail="E-Mail konnte nicht gesendet werden.",
        ) from error

    return {
        **success_response("Kontaktanfrage erhalten.", cleaned),
    }
