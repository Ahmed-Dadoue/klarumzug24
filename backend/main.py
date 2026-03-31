import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)
from app.api.routes.admin import router as admin_router
from app.api.routes.chat import router as chat_router
from app.api.routes.companies import router as companies_router
from app.api.routes.company_portal import router as company_portal_router
from app.api.routes.health import router as health_router
from app.api.routes.leads import router as leads_router
from app.api.routes.pricing import router as pricing_router
from app.api.routes.transactions import router as transactions_router
from app.core.config import ALLOWED_ORIGINS, DODE_MAX_MESSAGES, OPENAI_API_KEY
from app.core.database import ensure_schema
from app.schemas import ChatMessageIn

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

ensure_schema()


app = FastAPI(title="Klarumzug24 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(leads_router)
app.include_router(pricing_router)
app.include_router(companies_router)
app.include_router(company_portal_router)
app.include_router(transactions_router)
app.include_router(admin_router)


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception_wrapper(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return await handle_http_exception(_, exc)


@app.exception_handler(RequestValidationError)
async def handle_validation_error_wrapper(_: Request, exc: RequestValidationError) -> JSONResponse:
    return await handle_validation_error(_, exc)


@app.exception_handler(Exception)
async def handle_unexpected_error_wrapper(_: Request, exc: Exception) -> JSONResponse:
    return await handle_unexpected_error(_, exc, logger=LOGGER)


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
