
import csv
import io
import logging
import mimetypes
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai import generate_dode_reply
from app.ai.logging_utils import log_chat_event
from app.ai.schemas import ChatLanguage
from app.services.emailer import send_lead_notification

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./klarumzug.db")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
DEDUP_HOURS = int(os.getenv("DEDUP_HOURS", "6"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,https://klarumzug24.de,https://www.klarumzug24.de",
    ).split(",")
    if origin.strip()
]
MAX_PHOTO_BYTES = 10 * 1024 * 1024
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DODE_MODEL = os.getenv("DODE_MODEL", "gpt-4.1-mini").strip()
DODE_MAX_MESSAGES = int(os.getenv("DODE_MAX_MESSAGES", "12"))
DODE_MAX_OUTPUT_TOKENS = int(os.getenv("DODE_MAX_OUTPUT_TOKENS", "220"))

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
LOGGER = logging.getLogger("klarumzug24")
LOGGER.setLevel(logging.INFO)
CHAT_LOG_PATH = Path(__file__).resolve().parent / "chat-events.log"

if not any(
    isinstance(handler, logging.FileHandler)
    and Path(getattr(handler, "baseFilename", "")) == CHAT_LOG_PATH
    for handler in LOGGER.handlers
):
    chat_file_handler = logging.FileHandler(CHAT_LOG_PATH, encoding="utf-8")
    chat_file_handler.setLevel(logging.INFO)
    chat_file_handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(chat_file_handler)


class CompanyDB(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    region = Column(String(120), nullable=True)
    services = Column(String(300), nullable=True)
    daily_budget_eur = Column(Float, nullable=True)
    max_leads_per_day = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_assigned_at = Column(DateTime, nullable=True)
    balance_eur = Column(Float, nullable=False, default=0)
    api_key = Column(String(120), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PricingRuleDB(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    base_price_eur = Column(Float, nullable=False, default=20)
    price_per_room_eur = Column(Float, nullable=False, default=3)
    price_per_km_eur = Column(Float, nullable=False, default=0.5)
    min_price_eur = Column(Float, nullable=False, default=25)
    max_price_eur = Column(Float, nullable=False, default=120)
    express_multiplier = Column(Float, nullable=False, default=1.25)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadDB(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40), nullable=False)
    email = Column(String(200), nullable=False)
    from_city = Column(String(120), nullable=True)
    to_city = Column(String(120), nullable=True)
    rooms = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    express = Column(Boolean, nullable=False, default=False)
    message = Column(String(5000), nullable=True)
    photo_name = Column(String(255), nullable=True)
    accepted_agb = Column(Boolean, nullable=False, default=False)
    accepted_privacy = Column(Boolean, nullable=False, default=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="new")
    assigned_price_eur = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    amount_eur = Column(Integer, nullable=False)
    status = Column(String(40), nullable=False, default="charged")
    created_at = Column(DateTime, default=datetime.utcnow)


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        lead_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(leads)"))}
        if "company_id" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN company_id INTEGER"))
        if "status" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN status VARCHAR(40) DEFAULT 'new'"))
        if "assigned_price_eur" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN assigned_price_eur INTEGER"))
        if "rooms" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN rooms INTEGER"))
        if "distance_km" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN distance_km FLOAT"))
        if "express" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN express BOOLEAN DEFAULT 0"))
        if "message" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN message VARCHAR(5000)"))
        if "photo_name" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN photo_name VARCHAR(255)"))
        if "accepted_agb" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN accepted_agb BOOLEAN DEFAULT 0"))
        if "accepted_privacy" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN accepted_privacy BOOLEAN DEFAULT 0"))
        conn.execute(text("UPDATE leads SET status = 'new' WHERE status IS NULL OR status = ''"))
        conn.execute(text("UPDATE leads SET express = 0 WHERE express IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_agb = 0 WHERE accepted_agb IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_privacy = 0 WHERE accepted_privacy IS NULL"))

        company_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(companies)"))
        }
        if "last_assigned_at" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN last_assigned_at DATETIME"))
        if "balance_eur" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN balance_eur FLOAT DEFAULT 0"))
        if "api_key" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN api_key VARCHAR(120)"))
        conn.execute(text("UPDATE companies SET balance_eur = 0 WHERE balance_eur IS NULL"))


ensure_schema()


class LeadIn(BaseModel):
    name: str
    phone: str
    email: EmailStr
    conversation_id: str | None = None
    from_city: str | None = None
    to_city: str | None = None
    rooms: int | None = None
    distance_km: float | None = None
    express: bool = False
    message: str | None = None
    photo_name: str | None = None
    accepted_agb: bool = False
    accepted_privacy: bool = False


class CompanyIn(BaseModel):
    name: str
    region: str | None = None
    services: str | None = None
    daily_budget_eur: float | None = None
    max_leads_per_day: int | None = None
    is_active: bool = True
    balance_eur: float = 0


class CompanyTopUpIn(BaseModel):
    amount_eur: float


class PricingRuleIn(BaseModel):
    company_id: int | None = None
    base_price_eur: float = 20
    price_per_room_eur: float = 3
    price_per_km_eur: float = 0.5
    min_price_eur: float = 25
    max_price_eur: float = 120
    express_multiplier: float = 1.25
    active: bool = True


class PredictIn(BaseModel):
    qm: int = Field(ge=0, le=10000)
    kartons: int = Field(ge=0, le=5000)
    fahrstuhl: int = Field(ge=0, le=1)
    stockwerk: int = Field(ge=0, le=200)
    distanz_meter: int = Field(ge=0, le=200000)
    schraenke: int = Field(ge=0, le=500)
    waschmaschine: int = Field(ge=0, le=100)
    fernseher: int = Field(ge=0, le=100)
    montage: int = Field(ge=0, le=1)


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=20)
    page: str | None = Field(default=None, max_length=200)
    lang: ChatLanguage = "de"
    conversation_id: str | None = Field(default=None, max_length=80)


app = FastAPI(title="Klarumzug24 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ERROR_CODES_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def success_response(
    message: str,
    data: dict[str, Any] | list[Any] | None = None,
    legacy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "message": message,
        "data": data if data is not None else {},
    }
    if legacy:
        payload.update(legacy)
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


def _status_to_error_code(status_code: int) -> str:
    return ERROR_CODES_BY_STATUS.get(status_code, "request_error")


def _extract_error_message(detail: Any) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        for key in ("message", "detail", "error"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Request failed"


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        error=_status_to_error_code(exc.status_code),
        message=_extract_error_message(exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = "Invalid request payload"
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = ".".join(str(item) for item in first.get("loc", ()) if item != "body")
        reason = first.get("msg", "invalid value")
        message = f"{field}: {reason}" if field else reason

    return error_response(
        status_code=422,
        error="validation_error",
        message=message,
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled exception while processing request: %s", exc)
    return error_response(
        status_code=500,
        error="internal_error",
        message="Internal server error",
    )


def normalize_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


EMAIL_LOG_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_LOG_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)")


def sanitize_chat_log_text(value: str | None, max_length: int = 160) -> str:
    text = " ".join((value or "").split()).strip()
    if not text:
        return ""
    text = EMAIL_LOG_PATTERN.sub("[redacted-email]", text)
    text = PHONE_LOG_PATTERN.sub("[redacted-phone]", text)
    if len(text) > max_length:
        return text[:max_length].rstrip() + "..."
    return text


CONTACT_INTENT_KEYWORDS = {
    "de": ("kontakt", "telefon", "anrufen", "email", "e-mail", "whatsapp"),
    "en": ("contact", "phone", "call", "email", "whatsapp"),
}


def is_contact_intent(text: str | None, lang: ChatLanguage) -> bool:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return False
    keywords = CONTACT_INTENT_KEYWORDS.get(lang, CONTACT_INTENT_KEYWORDS["de"])
    return any(keyword in normalized for keyword in keywords)


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=422, detail="phone is required")

    national_number = ""
    if digits.startswith("0049"):
        national_number = digits[4:]
    elif digits.startswith("49"):
        national_number = digits[2:]
    elif digits.startswith("0"):
        national_number = digits[1:]
    else:
        raise HTTPException(
            status_code=422,
            detail="phone must start with 0, 49, +49 or 0049",
        )

    if national_number.startswith("0"):
        national_number = national_number[1:]

    if not national_number.isdigit() or len(national_number) < 6 or len(national_number) > 13:
        raise HTTPException(status_code=422, detail="phone is invalid")

    return f"+49{national_number}"


def validate_non_negative_int(label: str, value: int | None) -> None:
    if value is not None and value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be >= 0")


def validate_non_negative_float(label: str, value: float | None) -> None:
    if value is not None and value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be >= 0")


def parse_iso_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {field_name} format") from exc


def _normalize_form_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        return cleaned
    return value


def _build_lead_payload(data: dict[str, Any]) -> LeadIn:
    try:
        return LeadIn.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


async def _read_photo_attachment(photo: UploadFile | None) -> dict[str, Any] | None:
    if photo is None or not getattr(photo, "filename", ""):
        return None

    filename = os.path.basename((photo.filename or "").strip())
    if not filename:
        return None

    content = await photo.read()
    if not content:
        return None
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="photo is too large")

    content_type = (photo.content_type or "").strip().lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="photo must be an image")
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(filename)
        content_type = guessed_type or "application/octet-stream"

    return {
        "filename": filename,
        "content": content,
        "content_type": content_type,
    }


async def _parse_lead_request(request: Request) -> tuple[LeadIn, dict[str, Any] | None]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        photo = form.get("photo")
        photo_attachment = (
            await _read_photo_attachment(photo)
            if isinstance(photo, UploadFile)
            else None
        )
        payload_data = {
            "name": _normalize_form_value(form.get("name")),
            "phone": _normalize_form_value(form.get("phone")),
            "email": _normalize_form_value(form.get("email")),
            "conversation_id": _normalize_form_value(form.get("conversation_id")),
            "from_city": _normalize_form_value(form.get("from_city")),
            "to_city": _normalize_form_value(form.get("to_city")),
            "rooms": _normalize_form_value(form.get("rooms")),
            "distance_km": _normalize_form_value(form.get("distance_km")),
            "express": _normalize_form_value(form.get("express")) or False,
            "message": _normalize_form_value(form.get("message")),
            "photo_name": (
                photo_attachment["filename"]
                if photo_attachment
                else _normalize_form_value(form.get("photo_name"))
            ),
            "accepted_agb": _normalize_form_value(form.get("accepted_agb")) or False,
            "accepted_privacy": _normalize_form_value(form.get("accepted_privacy")) or False,
        }
        return _build_lead_payload(payload_data), photo_attachment

    return _build_lead_payload(await request.json()), None


def calculate_estimated_price(payload: PredictIn) -> float:
    estimate = (
        payload.qm * 4.2
        + payload.kartons * 1.7
        + payload.stockwerk * 12
        + (0 if payload.fahrstuhl else 65)
        + payload.distanz_meter * 0.45
        + payload.schraenke * 17
        + payload.waschmaschine * 28
        + payload.fernseher * 11
        + (95 if payload.montage else 0)
    )
    return round(max(0.0, float(estimate)), 2)


def get_dode_client():
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Dode AI ist noch nicht konfiguriert.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenAI client library is not installed.",
        ) from exc

    return OpenAI(api_key=OPENAI_API_KEY)


def build_dode_system_prompt(page: str | None) -> str:
    page_hint = page or "-"
    return (
        "Du bist Dode, der Website-Assistent von Klarumzug24. "
        "Antworte freundlich, klar, professionell und knapp. "
        "Antworte meistens in 2 bis 4 kurzen Saetzen. "
        "Keine Emojis. Keine langen Listen, ausser wenn der Nutzer es ausdruecklich will. "
        "Keine HTML-Tags und kein Markdown-Linkformat ausgeben. "
        "Hilf bei Preisfragen, Kontakt, WhatsApp, Leistungen, Regionen, Fotos, Terminwunsch und allgemeinen Fragen zum Umzug. "
        "Wenn es um einen konkreten oder verbindlichen Preis geht, verweise auf den Umzugsrechner oder eine direkte Anfrage. "
        "Erfinde keine Fakten. Wenn etwas nicht sicher ist, sage das offen und verweise auf Kontakt oder WhatsApp. "
        "Klarumzug24 arbeitet in Bordesholm, Schleswig-Holstein und der Region. "
        "Kontakt: Telefon +49 163 615 7234, E-Mail info@klarumzug24.de, WhatsApp. "
        "Wichtige Seiten sind /umzugsrechner.html, /kontakt.html, /ueber-uns.html, /agb.html, /datenschutz.html und /impressum.html. "
        "Nutze moeglichst Seitennamen oder Pfade wie /kontakt.html und /umzugsrechner.html statt rohe URLs. "
        "Wenn du WhatsApp empfiehlst, nenne einfach WhatsApp und keinen langen Link. "
        "Antworte in der Sprache des Nutzers. "
        "Aktuelle Seite: " + page_hint
    )


def build_dode_transcript(messages: list[ChatMessageIn]) -> str:
    transcript_lines: list[str] = []
    for message in messages[-DODE_MAX_MESSAGES:]:
        role_name = "Kunde" if message.role == "user" else "Dode"
        content = " ".join(message.content.split())
        if len(content) > 1200:
            content = content[:1200].rstrip() + "..."
        transcript_lines.append(f"{role_name}: {content}")
    return "\n".join(transcript_lines)


def generate_api_key() -> str:
    return "kp_" + secrets.token_urlsafe(32)


def require_admin_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not x_api_key or not ADMIN_API_KEY or not secrets.compare_digest(x_api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="invalid admin api key")


def require_company_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing company api key")

    db = SessionLocal()
    try:
        company = (
            db.query(CompanyDB)
            .filter(CompanyDB.api_key == x_api_key, CompanyDB.is_active.is_(True))
            .first()
        )
        if not company:
            raise HTTPException(status_code=401, detail="invalid company api key")
        return {
            "id": company.id,
            "name": company.name,
            "api_key": company.api_key,
        }
    finally:
        db.close()


def get_active_pricing_rule(db, company_id: int | None) -> PricingRuleDB | None:
    if company_id is not None:
        company_rule = (
            db.query(PricingRuleDB)
            .filter(
                PricingRuleDB.active.is_(True),
                PricingRuleDB.company_id == company_id,
            )
            .order_by(PricingRuleDB.id.desc())
            .first()
        )
        if company_rule:
            return company_rule

    return (
        db.query(PricingRuleDB)
        .filter(
            PricingRuleDB.active.is_(True),
            PricingRuleDB.company_id.is_(None),
        )
        .order_by(PricingRuleDB.id.desc())
        .first()
    )


def calculate_assigned_price(
    db,
    company_id: int,
    from_city: str | None,
    to_city: str | None,
    rooms: int | None,
    distance_km: float | None,
    express: bool,
) -> int:
    rule = get_active_pricing_rule(db, company_id)
    safe_rooms = max(0, int(rooms or 0))
    safe_km = max(0.0, float(distance_km or 0.0))

    if rule:
        price = (
            rule.base_price_eur
            + safe_rooms * rule.price_per_room_eur
            + safe_km * rule.price_per_km_eur
        )
        if express:
            price *= rule.express_multiplier

        min_price = rule.min_price_eur
        max_price = rule.max_price_eur
        if max_price < min_price:
            max_price = min_price

        price = max(min_price, min(max_price, price))
        return int(round(price))

    fallback = 35 if from_city and to_city else 25
    fallback += int(round(safe_rooms * 2 + safe_km * 0.3))
    if express:
        fallback = int(round(fallback * 1.2))
    return fallback


def pick_company_for_lead(
    db,
    from_city: str | None,
    to_city: str | None,
    rooms: int | None,
    distance_km: float | None,
    express: bool,
    excluded_company_ids: set[int] | None = None,
) -> tuple[CompanyDB | None, int | None]:
    excluded_company_ids = excluded_company_ids or set()

    query = db.query(CompanyDB).filter(CompanyDB.is_active.is_(True))
    if excluded_company_ids:
        query = query.filter(~CompanyDB.id.in_(excluded_company_ids))

    companies = (
        query.order_by(
            CompanyDB.last_assigned_at.is_(None).desc(),
            CompanyDB.last_assigned_at.asc(),
            CompanyDB.id.asc(),
        ).all()
    )

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for company in companies:
        max_daily = company.max_leads_per_day or 0
        if max_daily > 0:
            lead_count_today = (
                db.query(LeadDB)
                .filter(LeadDB.company_id == company.id, LeadDB.created_at >= day_start)
                .count()
            )
            if lead_count_today >= max_daily:
                continue

        quoted_price = calculate_assigned_price(
            db,
            company_id=company.id,
            from_city=from_city,
            to_city=to_city,
            rooms=rooms,
            distance_km=distance_km,
            express=express,
        )

        if float(company.balance_eur or 0) < quoted_price:
            continue

        return company, quoted_price

    return None, None


def assign_lead_to_company(
    db,
    lead: LeadDB,
    excluded_company_ids: set[int] | None = None,
) -> bool:
    company, quoted_price = pick_company_for_lead(
        db,
        from_city=lead.from_city,
        to_city=lead.to_city,
        rooms=lead.rooms,
        distance_km=lead.distance_km,
        express=bool(lead.express),
        excluded_company_ids=excluded_company_ids,
    )

    if not company:
        lead.company_id = None
        lead.status = "new"
        lead.assigned_price_eur = None
        return False

    lead.company_id = company.id
    lead.status = "assigned"
    lead.assigned_price_eur = int(quoted_price or 0)
    company.last_assigned_at = datetime.utcnow()
    return True

def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        hidden_name = "*" * len(name)
    else:
        hidden_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
    return f"{hidden_name}@{domain}"


def serialize_company(row: CompanyDB, include_api_key: bool = False) -> dict:
    payload = {
        "id": row.id,
        "name": row.name,
        "region": row.region,
        "services": row.services,
        "daily_budget_eur": row.daily_budget_eur,
        "max_leads_per_day": row.max_leads_per_day,
        "is_active": bool(row.is_active),
        "balance_eur": float(row.balance_eur or 0),
        "last_assigned_at": row.last_assigned_at.isoformat()
        if row.last_assigned_at
        else None,
        "created_at": row.created_at.isoformat(),
    }
    if include_api_key:
        payload["api_key"] = row.api_key
    return payload


def serialize_rule(row: PricingRuleDB) -> dict:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "base_price_eur": row.base_price_eur,
        "price_per_room_eur": row.price_per_room_eur,
        "price_per_km_eur": row.price_per_km_eur,
        "min_price_eur": row.min_price_eur,
        "max_price_eur": row.max_price_eur,
        "express_multiplier": row.express_multiplier,
        "active": bool(row.active),
        "created_at": row.created_at.isoformat(),
    }


def serialize_lead(row: LeadDB, include_pii: bool = True) -> dict:
    data = {
        "id": row.id,
        "from_city": row.from_city,
        "to_city": row.to_city,
        "rooms": row.rooms,
        "distance_km": row.distance_km,
        "express": bool(row.express),
        "company_id": row.company_id,
        "status": row.status,
        "assigned_price_eur": row.assigned_price_eur,
        "created_at": row.created_at.isoformat(),
    }

    if include_pii:
        data["name"] = row.name
        data["phone"] = row.phone
        data["email"] = row.email
        data["message"] = row.message
        data["photo_name"] = row.photo_name
        data["accepted_agb"] = bool(row.accepted_agb)
        data["accepted_privacy"] = bool(row.accepted_privacy)
    else:
        data["name"] = None
        data["phone"] = mask_phone(row.phone)
        data["email"] = mask_email(row.email)
        data["message"] = None
        data["photo_name"] = None
        data["accepted_agb"] = None
        data["accepted_privacy"] = None

    return data


def serialize_transaction(row: TransactionDB) -> dict:
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "company_id": row.company_id,
        "amount_eur": row.amount_eur,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


@app.get("/health")
def health():
    return success_response(
        "Service is healthy",
        data={"status": "ok"},
        legacy={"status": "ok"},
    )


@app.post("/predict")
@app.post("/api/predict")
def predict_price(payload: PredictIn):
    estimated_price = calculate_estimated_price(payload)
    result = {"estimated_price_eur": estimated_price}
    return success_response(
        "Price estimate calculated",
        data=result,
        legacy=result,
    )


@app.post("/api/chat")
def dode_chat(payload: ChatRequestIn):
    started_at = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    conversation_id = normalize_text(payload.conversation_id) or f"conv_{uuid.uuid4().hex[:12]}"
    page = normalize_text(payload.page)
    last_user_message = next(
        (
            " ".join(message.content.split())
            for message in reversed(payload.messages)
            if message.role == "user"
        ),
        "",
    )
    sanitized_last_user_message = sanitize_chat_log_text(last_user_message)
    user_message_count = sum(1 for message in payload.messages if message.role == "user")
    log_chat_event(
        LOGGER,
        "chat_request_received",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=payload.lang,
        page=page or "-",
        last_user_message=sanitized_last_user_message,
        success=None,
    )
    if user_message_count == 1:
        log_chat_event(
            LOGGER,
            "chat_conversion",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            conversion_step="chat_started",
            success=True,
        )
    if is_contact_intent(last_user_message, payload.lang):
        log_chat_event(
            LOGGER,
            "chat_conversion",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            conversion_step="contact_intent",
            success=True,
        )
    try:
        reply = generate_dode_reply(
            messages=payload.messages,
            page=page,
            lang=payload.lang,
            session_factory=SessionLocal,
            assigned_price_calculator=calculate_assigned_price,
            logger=LOGGER,
            request_id=request_id,
            conversation_id=conversation_id,
        )
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_chat_event(
            LOGGER,
            "chat_request_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            lang=payload.lang,
            page=page or "-",
            duration_ms=duration_ms,
            last_user_message=sanitized_last_user_message,
            success=False,
        )
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_chat_event(
        LOGGER,
        "chat_request_completed",
        request_id=request_id,
        conversation_id=conversation_id,
        lang=payload.lang,
        page=page or "-",
        duration_ms=duration_ms,
        response_length=len(reply or ""),
        success=True,
    )

    reply_data = {
        "reply": reply,
        "request_id": request_id,
        "conversation_id": conversation_id,
    }
    return success_response(
        "Dode reply generated",
        data=reply_data,
        legacy=reply_data,
    )


@app.post("/api/companies")
def create_company(
    payload: CompanyIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="company name is required")

        validate_non_negative_float("daily_budget_eur", payload.daily_budget_eur)
        validate_non_negative_int("max_leads_per_day", payload.max_leads_per_day)
        validate_non_negative_float("balance_eur", payload.balance_eur)

        company = CompanyDB(
            name=name,
            region=normalize_text(payload.region),
            services=normalize_text(payload.services),
            daily_budget_eur=payload.daily_budget_eur,
            max_leads_per_day=payload.max_leads_per_day,
            is_active=bool(payload.is_active),
            balance_eur=float(payload.balance_eur),
            api_key=generate_api_key(),
        )

        db.add(company)
        db.commit()
        db.refresh(company)

        serialized_company = serialize_company(company, include_api_key=True)
        return success_response(
            "Company created",
            data={"company": serialized_company},
            legacy={"company": serialized_company},
        )
    finally:
        db.close()


@app.get("/api/companies")
def list_companies(_admin: None = Depends(require_admin_api_key)):
    db = SessionLocal()
    try:
        rows = db.query(CompanyDB).order_by(CompanyDB.id.desc()).all()
        companies = [serialize_company(r, include_api_key=True) for r in rows]
        return success_response(
            "Companies loaded",
            data={"companies": companies},
            legacy={"companies": companies},
        )
    finally:
        db.close()


@app.post("/api/companies/{company_id}/topup")
def topup_company_balance(
    company_id: int,
    payload: CompanyTopUpIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        validate_non_negative_float("amount_eur", payload.amount_eur)
        if payload.amount_eur <= 0:
            raise HTTPException(status_code=422, detail="amount_eur must be > 0")

        company = db.query(CompanyDB).filter(CompanyDB.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")

        company.balance_eur = float(company.balance_eur or 0) + float(payload.amount_eur)
        db.commit()
        db.refresh(company)

        topup_data = {
            "company_id": company.id,
            "balance_eur": float(company.balance_eur),
        }
        return success_response(
            "Company balance updated",
            data=topup_data,
            legacy=topup_data,
        )
    finally:
        db.close()


@app.post("/api/pricing-rules")
def create_pricing_rule(
    payload: PricingRuleIn,
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        if payload.company_id is not None:
            company = db.query(CompanyDB).filter(CompanyDB.id == payload.company_id).first()
            if not company:
                raise HTTPException(status_code=404, detail="company not found")

        validate_non_negative_float("base_price_eur", payload.base_price_eur)
        validate_non_negative_float("price_per_room_eur", payload.price_per_room_eur)
        validate_non_negative_float("price_per_km_eur", payload.price_per_km_eur)
        validate_non_negative_float("min_price_eur", payload.min_price_eur)
        validate_non_negative_float("max_price_eur", payload.max_price_eur)

        if payload.express_multiplier <= 0:
            raise HTTPException(status_code=422, detail="express_multiplier must be > 0")
        if payload.max_price_eur < payload.min_price_eur:
            raise HTTPException(status_code=422, detail="max_price_eur must be >= min_price_eur")

        rule = PricingRuleDB(
            company_id=payload.company_id,
            base_price_eur=payload.base_price_eur,
            price_per_room_eur=payload.price_per_room_eur,
            price_per_km_eur=payload.price_per_km_eur,
            min_price_eur=payload.min_price_eur,
            max_price_eur=payload.max_price_eur,
            express_multiplier=payload.express_multiplier,
            active=bool(payload.active),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

        pricing_rule = serialize_rule(rule)
        return success_response(
            "Pricing rule created",
            data={"pricing_rule": pricing_rule},
            legacy={"pricing_rule": pricing_rule},
        )
    finally:
        db.close()


@app.get("/api/pricing-rules")
def list_pricing_rules(
    company_id: int | None = Query(default=None),
    active: bool | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(PricingRuleDB)
        if company_id is not None:
            query = query.filter(PricingRuleDB.company_id == company_id)
        if active is not None:
            query = query.filter(PricingRuleDB.active.is_(active))

        rows = query.order_by(PricingRuleDB.id.desc()).all()
        pricing_rules = [serialize_rule(r) for r in rows]
        return success_response(
            "Pricing rules loaded",
            data={"pricing_rules": pricing_rules},
            legacy={"pricing_rules": pricing_rules},
        )
    finally:
        db.close()

def _create_lead(
    payload: LeadIn,
    photo_attachment: dict[str, Any] | None = None,
    source: str = "lead_form",
):
    db = SessionLocal()
    try:
        name = (payload.name or "").strip()
        phone = normalize_phone(payload.phone or "")
        email = str(payload.email).strip().lower()
        from_city = normalize_text(payload.from_city)
        to_city = normalize_text(payload.to_city)
        rooms = payload.rooms
        distance_km = payload.distance_km
        express = bool(payload.express)
        conversation_id = normalize_text(payload.conversation_id)
        message = normalize_text(payload.message)
        photo_name = normalize_text(payload.photo_name)
        accepted_agb = bool(payload.accepted_agb)
        accepted_privacy = bool(payload.accepted_privacy)

        if not name:
            raise HTTPException(status_code=422, detail="name is required")
        if not accepted_agb or not accepted_privacy:
            raise HTTPException(
                status_code=422,
                detail="Bitte AGB und Datenschutzerklärung akzeptieren.",
            )
        validate_non_negative_int("rooms", rooms)
        validate_non_negative_float("distance_km", distance_km)

        dedup_from = datetime.utcnow() - timedelta(hours=DEDUP_HOURS)
        duplicate = (
            db.query(LeadDB)
            .filter(LeadDB.phone == phone, LeadDB.created_at >= dedup_from)
            .order_by(LeadDB.created_at.desc())
            .first()
        )

        if duplicate:
            duplicate.name = name
            duplicate.email = email
            if from_city:
                duplicate.from_city = from_city
            if to_city:
                duplicate.to_city = to_city
            if rooms is not None:
                duplicate.rooms = rooms
            if distance_km is not None:
                duplicate.distance_km = distance_km
            if express:
                duplicate.express = True
            if message:
                duplicate.message = message
            if photo_name:
                duplicate.photo_name = photo_name
            duplicate.accepted_agb = accepted_agb
            duplicate.accepted_privacy = accepted_privacy

            if duplicate.company_id is None:
                assign_lead_to_company(db, duplicate)

            db.commit()
            db.refresh(duplicate)
            try:
                send_lead_notification(
                    serialize_lead(duplicate, include_pii=True),
                    photo_attachment=photo_attachment,
                )
            except Exception:
                LOGGER.exception(
                    "Email notify failed (lead saved anyway): lead_id=%s",
                    duplicate.id,
                )
            lead_result = {
                "deduplicated": True,
                "lead_id": duplicate.id,
                "company_id": duplicate.company_id,
                "status": duplicate.status,
                "assigned_price_eur": duplicate.assigned_price_eur,
            }
            log_chat_event(
                LOGGER,
                "chat_conversion",
                conversation_id=conversation_id,
                lead_id=duplicate.id,
                source=source,
                conversion_step="lead_created",
                success=True,
            )
            return success_response(
                "Lead updated (deduplicated)",
                data=lead_result,
                legacy=lead_result,
            )

        lead = LeadDB(
            name=name,
            phone=phone,
            email=email,
            from_city=from_city,
            to_city=to_city,
            rooms=rooms,
            distance_km=distance_km,
            express=express,
            message=message,
            photo_name=photo_name,
            accepted_agb=accepted_agb,
            accepted_privacy=accepted_privacy,
            status="new",
        )

        db.add(lead)
        db.flush()
        assign_lead_to_company(db, lead)

        db.commit()
        db.refresh(lead)
        try:
            send_lead_notification(
                serialize_lead(lead, include_pii=True),
                photo_attachment=photo_attachment,
            )
        except Exception:
            LOGGER.exception(
                "Email notify failed (lead saved anyway): lead_id=%s",
                lead.id,
            )
        lead_result = {
            "deduplicated": False,
            "lead_id": lead.id,
            "company_id": lead.company_id,
            "status": lead.status,
            "assigned_price_eur": lead.assigned_price_eur,
        }
        log_chat_event(
            LOGGER,
            "chat_conversion",
            conversation_id=conversation_id,
            lead_id=lead.id,
            source=source,
            conversion_step="lead_created",
            success=True,
        )
        return success_response(
            "Lead created",
            data=lead_result,
            legacy=lead_result,
        )
    finally:
        db.close()


@app.post("/contact")
async def submit_contact(request: Request):
    payload, photo_attachment = await _parse_lead_request(request)
    return _create_lead(payload, photo_attachment=photo_attachment, source="contact")


@app.post("/api/leads")
async def create_lead(request: Request):
    payload, photo_attachment = await _parse_lead_request(request)
    return _create_lead(payload, photo_attachment=photo_attachment, source="api_leads")


@app.get("/api/leads")
def list_leads(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(LeadDB)
        if status:
            query = query.filter(LeadDB.status == status)
        if company_id is not None:
            query = query.filter(LeadDB.company_id == company_id)

        dt_from = parse_iso_datetime(created_from, "created_from")
        dt_to = parse_iso_datetime(created_to, "created_to")
        if dt_from is not None:
            query = query.filter(LeadDB.created_at >= dt_from)
        if dt_to is not None:
            query = query.filter(LeadDB.created_at <= dt_to)

        rows = query.order_by(LeadDB.id.desc()).all()
        leads = [serialize_lead(r, include_pii=True) for r in rows]
        return success_response(
            "Leads loaded",
            data={"leads": leads},
            legacy={"leads": leads},
        )
    finally:
        db.close()


@app.get("/api/company/me")
def company_me(company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        company = db.query(CompanyDB).filter(CompanyDB.id == company_auth["id"]).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")
        serialized_company = serialize_company(company, include_api_key=False)
        return success_response(
            "Company profile loaded",
            data={"company": serialized_company},
            legacy={"company": serialized_company},
        )
    finally:
        db.close()


@app.get("/api/company/leads")
def list_company_leads(company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        rows = (
            db.query(LeadDB)
            .filter(LeadDB.company_id == company_auth["id"])
            .order_by(LeadDB.id.desc())
            .all()
        )

        result = []
        for row in rows:
            include_pii = row.status == "accepted"
            result.append(serialize_lead(row, include_pii=include_pii))

        return success_response(
            "Company leads loaded",
            data={"leads": result},
            legacy={"leads": result},
        )
    finally:
        db.close()


@app.post("/api/leads/{lead_id}/accept")
def accept_lead(lead_id: int, company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        lead = db.query(LeadDB).filter(LeadDB.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="lead not found")

        if lead.company_id != company_auth["id"]:
            raise HTTPException(status_code=403, detail="lead does not belong to this company")

        if lead.status == "accepted":
            accept_data = {
                "already_accepted": True,
                "lead": serialize_lead(lead, include_pii=True),
            }
            return success_response(
                "Lead already accepted",
                data=accept_data,
                legacy=accept_data,
            )

        company = db.query(CompanyDB).filter(CompanyDB.id == company_auth["id"]).first()
        if not company:
            raise HTTPException(status_code=404, detail="company not found")

        amount = int(lead.assigned_price_eur or 0)
        if amount <= 0:
            amount = calculate_assigned_price(
                db,
                company_id=company.id,
                from_city=lead.from_city,
                to_city=lead.to_city,
                rooms=lead.rooms,
                distance_km=lead.distance_km,
                express=bool(lead.express),
            )
            lead.assigned_price_eur = amount

        if float(company.balance_eur or 0) < amount:
            raise HTTPException(
                status_code=402,
                detail="insufficient company balance, top-up required",
            )

        existing_charge = (
            db.query(TransactionDB)
            .filter(
                TransactionDB.lead_id == lead.id,
                TransactionDB.company_id == company.id,
                TransactionDB.status == "charged",
            )
            .first()
        )
        if not existing_charge:
            txn = TransactionDB(
                lead_id=lead.id,
                company_id=company.id,
                amount_eur=amount,
                status="charged",
            )
            db.add(txn)
            company.balance_eur = float(company.balance_eur or 0) - amount

        lead.status = "accepted"
        db.commit()
        db.refresh(lead)

        accept_data = {
            "already_accepted": False,
            "lead": serialize_lead(lead, include_pii=True),
            "company_balance_eur": float(company.balance_eur or 0),
        }
        return success_response(
            "Lead accepted",
            data=accept_data,
            legacy=accept_data,
        )
    finally:
        db.close()


@app.post("/api/leads/{lead_id}/reject")
def reject_lead(lead_id: int, company_auth: dict = Depends(require_company_auth)):
    db = SessionLocal()
    try:
        lead = db.query(LeadDB).filter(LeadDB.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="lead not found")

        if lead.company_id != company_auth["id"]:
            raise HTTPException(status_code=403, detail="lead does not belong to this company")

        previous_company_id = lead.company_id
        lead.status = "rejected"
        reassigned = assign_lead_to_company(
            db,
            lead,
            excluded_company_ids={company_auth["id"]},
        )

        db.commit()
        db.refresh(lead)

        reject_data = {
            "previous_company_id": previous_company_id,
            "reassigned": reassigned,
            "lead": serialize_lead(lead, include_pii=False),
        }
        return success_response(
            "Lead rejected",
            data=reject_data,
            legacy=reject_data,
        )
    finally:
        db.close()

@app.get("/api/transactions")
def list_transactions(
    company_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(TransactionDB)
        if company_id is not None:
            query = query.filter(TransactionDB.company_id == company_id)
        if status:
            query = query.filter(TransactionDB.status == status)

        rows = query.order_by(TransactionDB.id.desc()).all()
        transactions = [serialize_transaction(r) for r in rows]
        return success_response(
            "Transactions loaded",
            data={"transactions": transactions},
            legacy={"transactions": transactions},
        )
    finally:
        db.close()


@app.get("/api/admin/invoices/summary")
def invoices_summary(_admin: None = Depends(require_admin_api_key)):
    db = SessionLocal()
    try:
        companies = db.query(CompanyDB).order_by(CompanyDB.id.asc()).all()
        result = []
        for company in companies:
            txns = (
                db.query(TransactionDB)
                .filter(
                    TransactionDB.company_id == company.id,
                    TransactionDB.status == "charged",
                )
                .all()
            )
            charged_total = int(sum(t.amount_eur for t in txns))
            result.append(
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "charged_count": len(txns),
                    "charged_total_eur": charged_total,
                    "balance_eur": float(company.balance_eur or 0),
                }
            )
        return success_response(
            "Invoice summary loaded",
            data={"invoices": result},
            legacy={"invoices": result},
        )
    finally:
        db.close()


@app.get("/api/admin/leads/export")
def export_leads_csv(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(LeadDB)
        if status:
            query = query.filter(LeadDB.status == status)
        if company_id is not None:
            query = query.filter(LeadDB.company_id == company_id)

        rows = query.order_by(LeadDB.id.desc()).all()

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "name",
                "phone",
                "email",
                "from_city",
                "to_city",
                "rooms",
                "distance_km",
                "express",
                "company_id",
                "status",
                "assigned_price_eur",
                "accepted_agb",
                "accepted_privacy",
                "created_at",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(serialize_lead(row, include_pii=True))

        csv_bytes = output.getvalue().encode("utf-8")
        filename = f"klarumzug24-leads-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        db.close()

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard_page():
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Klarumzug24 Admin</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    input, select, button { padding: 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; }
    th, td { border: 1px solid #ddd; padding: 8px; font-size: 14px; }
    th { background: #f5f5f5; }
    .small { font-size: 12px; color: #555; }
  </style>
</head>
<body>
  <h1>Klarumzug24 Admin</h1>
  <div class=\"row\">
    <input id=\"apiKey\" placeholder=\"Admin API key\" style=\"min-width:320px\" />
    <button onclick=\"loadData()\">Load</button>
    <button onclick=\"downloadCsv()\">Export CSV</button>
  </div>
  <div class=\"row\">
    <select id=\"status\">
      <option value=\"\">all status</option>
      <option value=\"new\">new</option>
      <option value=\"assigned\">assigned</option>
      <option value=\"accepted\">accepted</option>
      <option value=\"rejected\">rejected</option>
    </select>
    <input id=\"companyId\" type=\"number\" placeholder=\"company id\" />
  </div>
  <div class=\"small\" id=\"summary\">-</div>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Status</th><th>Company</th><th>Price</th><th>Name</th><th>Phone</th><th>Email</th><th>Created</th>
      </tr>
    </thead>
    <tbody id=\"rows\"></tbody>
  </table>

<script>
async function api(url) {
  const key = document.getElementById('apiKey').value.trim();
  const res = await fetch(url, { headers: { 'X-API-Key': key } });
  let payload = null;
  try {
    payload = await res.json();
  } catch (_) {
    payload = null;
  }
  if (!res.ok) {
    throw new Error(payload?.message || ('HTTP ' + res.status));
  }
  if (payload && payload.ok === false) {
    throw new Error(payload.message || 'API error');
  }
  return payload;
}

function buildQuery() {
  const status = document.getElementById('status').value;
  const companyId = document.getElementById('companyId').value;
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (companyId) params.set('company_id', companyId);
  const q = params.toString();
  return q ? ('?' + q) : '';
}

async function loadData() {
  try {
    const q = buildQuery();
    const leadsPayload = await api('/api/leads' + q);
    const invoicesPayload = await api('/api/admin/invoices/summary');
    const leads = Array.isArray(leadsPayload)
      ? leadsPayload
      : (leadsPayload?.data?.leads ?? leadsPayload?.leads ?? []);
    const invoices = Array.isArray(invoicesPayload)
      ? invoicesPayload
      : (invoicesPayload?.data?.invoices ?? invoicesPayload?.invoices ?? []);

    document.getElementById('summary').textContent =
      'Leads: ' + leads.length + ' | Companies: ' + invoices.length;

    const rows = document.getElementById('rows');
    rows.innerHTML = leads.map(l => `
      <tr>
        <td>${l.id}</td>
        <td>${l.status ?? ''}</td>
        <td>${l.company_id ?? ''}</td>
        <td>${l.assigned_price_eur ?? ''}</td>
        <td>${l.name ?? ''}</td>
        <td>${l.phone ?? ''}</td>
        <td>${l.email ?? ''}</td>
        <td>${l.created_at ?? ''}</td>
      </tr>
    `).join('');
  } catch (e) {
    alert('Load failed: ' + e.message);
  }
}

async function downloadCsv() {
  try {
    const key = document.getElementById('apiKey').value.trim();
    const q = buildQuery();
    const res = await fetch('/api/admin/leads/export' + q, {
      headers: { 'X-API-Key': key }
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'leads.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('CSV export failed: ' + e.message);
  }
}
</script>
</body>
</html>
"""

