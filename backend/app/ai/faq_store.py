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


def _normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(_normalize_text(text)))


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
        combined_text = " ".join([*variants, " ".join(item.get("keywords", []))])
        entries.append(
            {
                **item,
                "_variants": [_normalize_text(variant) for variant in variants],
                "_tokens": _tokenize(combined_text),
            }
        )
    return entries


def _score_entry(user_text: str, user_tokens: set[str], entry: dict[str, Any]) -> float:
    if not user_text:
        return 0.0

    exact_bonus = 0.0
    contains_bonus = 0.0
    best_variant_overlap = 0.0

    for variant in entry.get("_variants", []):
        if user_text == variant:
            exact_bonus = 2.5
        elif user_text in variant or variant in user_text:
            contains_bonus = max(contains_bonus, 1.0)

        variant_tokens = _tokenize(variant)
        if variant_tokens:
            overlap = len(user_tokens & variant_tokens) / max(len(variant_tokens), 1)
            best_variant_overlap = max(best_variant_overlap, overlap)

    entry_tokens = entry.get("_tokens", set())
    token_overlap = 0.0
    if entry_tokens and user_tokens:
        token_overlap = len(user_tokens & entry_tokens) / max(len(user_tokens), 1)

    return exact_bonus + contains_bonus + best_variant_overlap + token_overlap


def find_best_faq_match(
    user_question: str,
    *,
    lang: ChatLanguage = "de",
    min_score: float = 1.05,
) -> dict[str, Any] | None:
    normalized_question = _normalize_text(user_question)
    user_tokens = _tokenize(normalized_question)
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
