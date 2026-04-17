"""Authoritative local policy facts for the chat supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schemas import ChatLanguage

PolicyStatus = Literal["confirmed", "manual_confirmation_required"]


@dataclass(frozen=True)
class PolicyTruth:
    key: str
    status: PolicyStatus
    keywords_de: tuple[str, ...]
    keywords_en: tuple[str, ...]
    answer_de: str
    answer_en: str
    source_pages_de: tuple[str, ...]
    source_pages_en: tuple[str, ...]


def _normalize_text(value: str) -> str:
    return (
        " ".join((value or "").lower().strip().split())
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


POLICY_REGISTRY: dict[str, PolicyTruth] = {
    "stornierung": PolicyTruth(
        key="stornierung",
        status="confirmed",
        keywords_de=("stornierung", "stornieren", "absagen", "termin absagen"),
        keywords_en=("cancel", "cancellation"),
        answer_de=(
            "Laut AGB ist eine kostenfreie Stornierung bis spaetestens 48 Stunden vor dem vereinbarten Umzugstermin moeglich. "
            "Bei spaeteren Stornierungen kann eine angemessene Ausfallpauschale berechnet werden."
        ),
        answer_en=(
            "According to the terms, cancellation is free up to 48 hours before the agreed moving date. "
            "Later cancellations may lead to an appropriate cancellation fee."
        ),
        source_pages_de=("/agb.html",),
        source_pages_en=("/agb-en.html",),
    ),
    "versicherung": PolicyTruth(
        key="versicherung",
        status="confirmed",
        keywords_de=("versicherung", "transportversicherung", "versichert"),
        keywords_en=("insurance", "insured", "transport insurance"),
        answer_de=(
            "Laut AGB sind transportierte Gueter im Rahmen der gesetzlichen Haftungsvorschriften versichert. "
            "Eine weitergehende Transportversicherung kann auf Wunsch gegen gesonderte Kosten abgeschlossen werden."
        ),
        answer_en=(
            "According to the terms, transported goods are insured within the scope of the statutory liability rules. "
            "Additional transport insurance may be requested for an extra charge."
        ),
        source_pages_de=("/agb.html",),
        source_pages_en=("/agb-en.html",),
    ),
    "zahlung": PolicyTruth(
        key="zahlung",
        status="confirmed",
        keywords_de=("zahlung", "zahlen", "zahlungsarten", "barzahlung", "ueberweisung"),
        keywords_en=("payment", "pay", "bank transfer", "cash"),
        answer_de=(
            "Laut AGB erfolgt die Zahlung grundsaetzlich unmittelbar nach Abschluss der Dienstleistung, sofern nichts anderes vereinbart wurde. "
            "Genannt werden Barzahlung, Ueberweisung oder andere individuell vereinbarte Zahlungsmethoden."
        ),
        answer_en=(
            "According to the terms, payment is generally due immediately after completion of the service unless something else was agreed. "
            "The listed methods include cash, bank transfer or other individually agreed payment methods."
        ),
        source_pages_de=("/agb.html",),
        source_pages_en=("/agb-en.html",),
    ),
    "anzahlung": PolicyTruth(
        key="anzahlung",
        status="confirmed",
        keywords_de=("anzahlung", "vorauszahlung"),
        keywords_en=("deposit", "advance payment"),
        answer_de="Laut AGB kann bei groesseren Umzuegen eine angemessene Anzahlung verlangt werden.",
        answer_en="According to the terms, an appropriate deposit may be required for larger moves.",
        source_pages_de=("/agb.html",),
        source_pages_en=("/agb-en.html",),
    ),
    "rechnung": PolicyTruth(
        key="rechnung",
        status="manual_confirmation_required",
        keywords_de=("rechnung", "rechnungsstellung", "quittung"),
        keywords_en=("invoice", "receipt"),
        answer_de=(
            "Eine ausdrueckliche Rechnungsregel ist in den aktuell veroeffentlichten AGB und FAQ nicht sauber als Standardfall dokumentiert. "
            "Wenn Sie eine Rechnung oder einen besonderen Rechnungswunsch brauchen, geben Sie das bitte direkt in der Anfrage an."
        ),
        answer_en=(
            "An explicit invoice rule is not clearly documented as a standard case in the currently published terms and FAQ. "
            "If you need an invoice or special billing setup, please mention that directly in your request."
        ),
        source_pages_de=("/kontakt.html", "/agb.html"),
        source_pages_en=("/kontakt-en.html", "/agb-en.html"),
    ),
    "wochenende_feiertag": PolicyTruth(
        key="wochenende_feiertag",
        status="manual_confirmation_required",
        keywords_de=("wochenende", "samstag", "sonntag", "feiertag", "zuschlag"),
        keywords_en=("weekend", "holiday", "surcharge"),
        answer_de=(
            "Ein fester Wochenend- oder Feiertagszuschlag ist in den aktuell veroeffentlichten FAQ und AGB nicht als starre Standardregel hinterlegt. "
            "Wunschtermine, Verfuegbarkeit und moegliche Mehrkosten sollten deshalb direkt angefragt werden."
        ),
        answer_en=(
            "A fixed weekend or holiday surcharge is not documented as a rigid standard rule in the currently published FAQ and terms. "
            "Preferred dates, availability and any additional costs should therefore be requested directly."
        ),
        source_pages_de=("/agb.html", "/umzugsrechner.html"),
        source_pages_en=("/agb-en.html", "/umzugsrechner-en.html"),
    ),
    "verfuegbarkeit": PolicyTruth(
        key="verfuegbarkeit",
        status="confirmed",
        keywords_de=("verfuegbar", "verfuegbarkeit", "wunschtermin", "kurzfristig", "express"),
        keywords_en=("available", "availability", "date", "short notice", "express"),
        answer_de=(
            "Ob ein Wunschtermin verfuegbar ist, haengt von Planung und Auslastung ab. "
            "Kurzfristige oder Express-Anfragen sind grundsaetzlich moeglich, muessen aber direkt geprueft werden."
        ),
        answer_en=(
            "Whether a requested date is available depends on planning and capacity. "
            "Short-notice or express requests may be possible but must be checked directly."
        ),
        source_pages_de=("/umzugsrechner.html", "/agb.html"),
        source_pages_en=("/umzugsrechner-en.html", "/agb-en.html"),
    ),
    "datenschutz": PolicyTruth(
        key="datenschutz",
        status="confirmed",
        keywords_de=("datenschutz", "daten", "dsgvo", "daten loeschen", "daten speichern"),
        keywords_en=("privacy", "data protection", "data", "gdpr"),
        answer_de=(
            "Laut Datenschutzerklaerung werden personenbezogene Daten fuer die Bearbeitung der Anfrage, fuer ein moegliches Angebot und fuer die Auftragsabwicklung verwendet. "
            "Rechte wie Auskunft, Berichtigung, Loeschung, Einschraenkung, Datenuebertragbarkeit und Widerspruch werden dort ebenfalls genannt."
        ),
        answer_en=(
            "According to the privacy policy, personal data is used for processing your request, preparing a possible quote and handling a potential order. "
            "Rights such as access, correction, deletion, restriction, data portability and objection are also listed there."
        ),
        source_pages_de=("/datenschutz.html",),
        source_pages_en=("/datenschutz-en.html",),
    ),
    "kontakt": PolicyTruth(
        key="kontakt",
        status="confirmed",
        keywords_de=("kontakt", "telefon", "anrufen", "whatsapp", "email", "e-mail"),
        keywords_en=("contact", "phone", "call", "whatsapp", "email"),
        answer_de="Sie erreichen Klarumzug24 unter +49 163 615 7234, per E-Mail an info@klarumzug24.de oder ueber das Kontaktformular /kontakt.html.",
        answer_en="You can reach Klarumzug24 via +49 163 615 7234, by e-mail at info@klarumzug24.de or via the contact form /kontakt-en.html.",
        source_pages_de=("/kontakt.html",),
        source_pages_en=("/kontakt-en.html",),
    ),
}


def get_policy_truth(key: str) -> PolicyTruth | None:
    return POLICY_REGISTRY.get(key)


def find_best_policy_truth(user_text: str, lang: ChatLanguage = "de") -> dict[str, object] | None:
    normalized_text = _normalize_text(user_text)
    if not normalized_text:
        return None

    best_key: str | None = None
    best_score = 0.0
    for key, fact in POLICY_REGISTRY.items():
        keywords = fact.keywords_en if lang == "en" else fact.keywords_de
        score = 0.0
        for keyword in keywords:
            normalized_keyword = _normalize_text(keyword)
            if not normalized_keyword:
                continue
            if normalized_text == normalized_keyword:
                score += 3.0
            elif normalized_keyword in normalized_text:
                score += 1.3
        if score > best_score:
            best_key = key
            best_score = score

    if not best_key or best_score < 1.3:
        return None

    fact = POLICY_REGISTRY[best_key]
    pages = fact.source_pages_en if lang == "en" else fact.source_pages_de
    reply = fact.answer_en if lang == "en" else fact.answer_de
    if pages:
        page_suffix = f" Relevante Seite: {', '.join(pages)}." if lang == "de" else f" Relevant page: {', '.join(pages)}."
        reply = f"{reply} {page_suffix}".strip()
    return {
        "key": best_key,
        "score": round(best_score, 3),
        "policy": fact,
        "reply": reply,
    }
