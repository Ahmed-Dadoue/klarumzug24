from __future__ import annotations

from typing import Iterable

from .models import PersonaProfile


ALLOWED_SERVICES = [
    "umzug",
    "hausumzug",
    "firmenumzug",
    "teilumzug",
    "einzeltransport",
    "entruempelung",
    "hausaufloesung",
    "wohnungsaufloesung",
    "moebelmontage",
    "moebeldemontage",
    "kuechenmontage",
    "kuechendemontage",
    "entsorgung",
    "halteverbotszone",
    "verpackungsmaterial",
    "tragehilfe",
    "schwere gegenstaende",
    "klaviertransport",
    "tresortransport",
    "lagerung",
    "zwischenlagerung",
    "umzugsversicherung",
    "reinigung",
]

ALLOWED_FOCUS_AREAS = [
    "preise",
    "zuschlaege",
    "etage_aufzug_trageweg",
    "entfernung",
    "wochenende_feiertag",
    "versicherung",
    "verpackung",
    "montage_demontage",
    "kuechenmontage",
    "entsorgung",
    "hausaufloesung",
    "entruempelung",
    "lagerung",
    "sondertransporte",
    "halteverbotszone",
    "rechnung",
    "buchung",
    "termin",
    "stornierung",
    "verfuegbarkeit",
    "partnerleistungen",
    "beschwerden",
    "qualitaetsprobleme",
    "notfall_umzug",
    "privat_vs_firma",
    "leistungsabgrenzung",
    "versteckte_kosten",
    "preisverhandlung",
    "ablauf_organisation",
    "dauer",
    "helferanzahl",
    "lkw_groesse",
    "typische_missverstaendnisse",
]

ALLOWED_TURN_KINDS = {
    "probe_question",
    "scenario_reply",
    "challenge",
    "clarification",
    "booking_push",
    "complaint_follow_up",
    "stop",
}

ALLOWED_QUESTION_TYPES = {
    "price_question",
    "service_question",
    "faq_question",
    "booking_question",
    "complaint",
    "objection",
    "policy_probe",
    "contradiction_probe",
    "edge_case",
    "expert_follow_up",
    "process_question",
    "quality_question",
    "special_case_transport_question",
    "differentiation_question",
}

DOMAIN_KEYWORDS = [
    "umzug",
    "transport",
    "einzeltransport",
    "entruempelung",
    "hausaufloesung",
    "wohnungsaufloesung",
    "moebelmontage",
    "kuechenmontage",
    "kuechendemontage",
    "entsorgung",
    "halteverbotszone",
    "verpackung",
    "kartons",
    "tragehilfe",
    "klavier",
    "tresor",
    "lagerung",
    "zwischenlagerung",
    "versicherung",
    "reinigung",
    "zuschlag",
    "stockwerk",
    "aufzug",
    "trageweg",
    "feiertag",
    "wochenende",
    "rechnung",
    "buchung",
    "stornierung",
    "angebot",
    "preis",
    "kosten",
    "helfer",
    "lkw",
]

OFFTOPIC_HINTS = [
    "python",
    "javascript",
    "react",
    "politics",
    "weather",
    "restaurant",
    "hotel",
    "bitcoin",
    "crypto",
    "visa",
    "krankheit",
    "medikament",
    "fussball",
    "nba",
]

PERSONA_LIBRARY: dict[str, PersonaProfile] = {
    "private_customer": PersonaProfile(
        label="private_customer",
        role="Privatkunde mit echtem Umzugsbedarf",
        tone="freundlich, konkret, aufmerksam",
        expertise="kennt typische Umzugsfragen, aber ist kein Jurist",
        intent_style="fragt realistisch, detailnah und servicebezogen",
        pressure_style="fragt nach, wenn Antworten vage oder unvollstaendig sind",
    ),
    "business_customer": PersonaProfile(
        label="business_customer",
        role="Firmenkunde mit professionellem Umzugs- oder Transportbedarf",
        tone="sachlich, strukturiert, zeitsensibel",
        expertise="achtet auf Organisation, Ausfallzeiten, Rechnung und Verlaesslichkeit",
        intent_style="fragt nach Prozess, SLA-artiger Verbindlichkeit und Kapazitaet",
        pressure_style="testet Professionalitaet, Fristen und Leistungsgrenzen",
    ),
    "price_hawk": PersonaProfile(
        label="price_hawk",
        role="preisbewusster Kunde mit Fokus auf Zuschlaege und versteckte Kosten",
        tone="kritisch, aber professionell",
        expertise="kennt typische Preishebel im Transportbereich",
        intent_style="vergleicht Leistungen, Zuschlaege und Ausnahmen",
        pressure_style="geht bei unklaren Preisen oder Versprechen hart nach",
    ),
    "complaint_probe": PersonaProfile(
        label="complaint_probe",
        role="Kunde mit Beschwerde- oder Problemfokus",
        tone="nuechtern, insistierend",
        expertise="kennt typische Servicefehler und Eskalationsmuster",
        intent_style="stellt Vorwuerfe, Reklamationen und Qualitaetsfragen",
        pressure_style="testet Stabilitaet von Policy und Serviceversprechen",
    ),
    "expert_auditor": PersonaProfile(
        label="expert_auditor",
        role="fachkundiger Tester fuer Umzugs- und Transportdienste",
        tone="praezise, professionell, belastbar",
        expertise="denkt wie ein Branchenexperte fuer Umzug, Sondertransport und Servicequalitaet",
        intent_style="stellt Grenzfaelle, Differenzierungsfragen und Widerspruchsproben",
        pressure_style="enthaelt inkonsistente Policy, Halluzinationen und starre Preisflows",
    ),
}

DOMAIN_SYSTEM_GUARDRAIL = (
    "Du bist ein Test-Questioner fuer Umzug, Transport und umzugsnahe Dienstleistungen. "
    "Bleibe strikt im Bereich Umzug, Firmenumzug, Teilumzug, Einzeltransport, Entruempelung, "
    "Hausaufloesung, Wohnungsaufloesung, Moebelmontage, Moebeldemontage, Kuechenmontage, "
    "Kuechendemontage, Entsorgung, Halteverbotszone, Verpackungsmaterial, Tragehilfe, "
    "schwere Gegenstaende, Klaviertransport, Tresortransport, Lagerung, Zwischenlagerung, "
    "Umzugsversicherung und Reinigung nur in direktem Zusammenhang mit Transport oder Raeumung. "
    "Keine Offtopic-Themen. Keine Technik-, Politik-, Medizin-, Wetter- oder sonstige Allgemeinthemen."
)


def normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def domain_score(text: str) -> int:
    normalized = normalize_text(text)
    score = sum(1 for keyword in DOMAIN_KEYWORDS if keyword in normalized)
    score -= sum(2 for keyword in OFFTOPIC_HINTS if keyword in normalized)
    return score


def is_domain_safe(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if any(keyword in normalized for keyword in OFFTOPIC_HINTS):
        return False
    return domain_score(normalized) > 0


def ensure_domain_safe_message(
    text: str,
    *,
    service_hints: Iterable[str],
    focus_area: str,
) -> str:
    if is_domain_safe(text):
        return text.strip()
    services = ", ".join(service_hints) or "Umzug"
    focus = focus_area or "Leistungsumfang"
    return (
        f"Koennen Sie mir bitte konkreter erklaeren, wie Sie bei {services} mit dem Thema "
        f"{focus} umgehen?"
    )


def load_persona(label: str) -> PersonaProfile:
    return PERSONA_LIBRARY.get(label, PERSONA_LIBRARY["expert_auditor"])
