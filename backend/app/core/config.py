import os

from dotenv import load_dotenv

load_dotenv()

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
