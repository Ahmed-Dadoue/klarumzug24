from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schemas import ChatLanguage

BASE_DIR = Path(__file__).resolve().parent
FAQ_PATHS: dict[ChatLanguage, Path] = {
    "de": BASE_DIR / "knowledge" / "faq_de.json",
    "en": BASE_DIR / "knowledge" / "faq_en.json",
}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS: dict[ChatLanguage, set[str]] = {
    "de": {
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "und",
        "oder",
        "ich",
        "ihr",
        "wir",
        "ist",
        "sind",
        "auch",
        "bei",
        "mit",
        "fuer",
        "von",
        "zu",
        "am",
        "an",
        "im",
        "in",
        "was",
        "wie",
        "wann",
        "kann",
        "man",
        "wenn",
        "koennt",
        "noch",
        "spaeter",
        "etwas",
        "mehr",
        "direkt",
        "bitte",
        "anfrage",
        "macht",
        "bietet",
        "gibt",
        "mir",
        "meine",
    },
    "en": {
        "the",
        "a",
        "an",
        "and",
        "or",
        "is",
        "are",
        "do",
        "does",
        "can",
        "you",
        "your",
        "i",
        "me",
        "my",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "what",
        "how",
        "when",
    },
}
CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "rechtliches": ("agb", "datenschutz", "versicherung", "storn", "absag", "zahlung", "haftung"),
    "preise": ("preis", "kosten", "schaetzung", "festpreis", "rabatt"),
    "service": ("service", "leistung", "montage", "entsorgung", "transport", "umzug"),
    "kontakt": ("kontakt", "telefon", "email", "whatsapp"),
}


def _normalize_text(text: str) -> str:
    return (
        " ".join((text or "").lower().split())
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _tokenize(text: str, lang: ChatLanguage) -> set[str]:
    tokens = set(TOKEN_PATTERN.findall(_normalize_text(text)))
    return {token for token in tokens if token not in STOPWORDS.get(lang, set())}


def _resolve_faq_path(lang: ChatLanguage) -> Path:
    return FAQ_PATHS.get(lang, FAQ_PATHS["de"])


def get_faq_filename(lang: ChatLanguage) -> str:
    return _resolve_faq_path(lang).name


@lru_cache(maxsize=8)
def load_faq_entries(lang: ChatLanguage = "de") -> list[dict[str, Any]]:
    faq_path = _resolve_faq_path(lang)
    if not faq_path.exists():
        return []

    with faq_path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    entries: list[dict[str, Any]] = []
    for item in data:
        variants = [variant for variant in item.get("question_variants", []) if variant]
        normalized_variants = [_normalize_text(variant) for variant in variants]
        keyword_list = [keyword for keyword in item.get("keywords", []) if keyword]
        keyword_tokens = _tokenize(" ".join(keyword_list), lang)
        combined_text = " ".join([*variants, " ".join(keyword_list)])
        entries.append(
            {
                **item,
                "_variants": normalized_variants,
                "_variant_tokens": [_tokenize(variant, lang) for variant in normalized_variants],
                "_tokens": _tokenize(combined_text, lang),
                "_keyword_tokens": keyword_tokens,
                "_source_page_tokens": _tokenize(item.get("source_page", ""), lang),
            }
        )
    return entries


def _category_bonus(user_text: str, entry: dict[str, Any]) -> float:
    category = str(entry.get("category") or "").lower()
    for category_key, hints in CATEGORY_HINTS.items():
        if category != category_key:
            continue
        if any(hint in user_text for hint in hints):
            return 0.35
    return 0.0


def _score_entry(
    user_text: str,
    user_tokens: set[str],
    entry: dict[str, Any],
) -> float:
    if not user_text:
        return 0.0

    exact_bonus = 0.0
    contains_bonus = 0.0
    best_variant_overlap = 0.0
    best_keyword_overlap = 0.0
    best_shared_variant_tokens = 0

    for variant, variant_tokens in zip(entry.get("_variants", []), entry.get("_variant_tokens", [])):
        if user_text == variant:
            exact_bonus = 3.2
        elif user_text in variant or variant in user_text:
            contains_bonus = max(contains_bonus, 1.3)

        if variant_tokens:
            shared_token_count = len(user_tokens & variant_tokens)
            best_shared_variant_tokens = max(best_shared_variant_tokens, shared_token_count)
            overlap = len(user_tokens & variant_tokens) / max(len(variant_tokens), 1)
            best_variant_overlap = max(best_variant_overlap, overlap)

    entry_tokens = entry.get("_tokens", set())
    keyword_tokens = entry.get("_keyword_tokens", set())
    source_page_tokens = entry.get("_source_page_tokens", set())

    token_overlap = 0.0
    if entry_tokens and user_tokens:
        token_overlap = len(user_tokens & entry_tokens) / max(len(user_tokens), 1)

    if keyword_tokens and user_tokens:
        best_keyword_overlap = len(user_tokens & keyword_tokens) / max(len(keyword_tokens), 1)

    source_page_bonus = 0.15 if source_page_tokens and user_tokens & source_page_tokens else 0.0

    return (
        exact_bonus
        + contains_bonus
        + best_variant_overlap
        + token_overlap
        + best_keyword_overlap
        + min(best_shared_variant_tokens, 2) * 0.35
        + _category_bonus(user_text, entry)
        + source_page_bonus
    )


def find_best_faq_match(
    user_question: str,
    *,
    lang: ChatLanguage = "de",
    min_score: float = 1.0,
) -> dict[str, Any] | None:
    normalized_question = _normalize_text(user_question)
    user_tokens = _tokenize(normalized_question, lang)
    if not normalized_question or not user_tokens:
        return None

    best_entry: dict[str, Any] | None = None
    best_score = 0.0

    for entry in load_faq_entries(lang):
        score = _score_entry(normalized_question, user_tokens, entry)
        if score > best_score:
            best_score = score
            best_entry = entry

    if not best_entry or best_score < min_score:
        return None

    return {
        "score": round(best_score, 3),
        "item": {
            "id": best_entry.get("id"),
            "category": best_entry.get("category"),
            "answer": best_entry.get("answer"),
            "source_page": best_entry.get("source_page"),
        },
    }
