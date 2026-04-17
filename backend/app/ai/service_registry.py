"""Authoritative local service registry for the chat supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schemas import ChatLanguage

ServiceAvailability = Literal["offered", "manual_confirmation_required", "not_offered"]
ServiceFulfillment = Literal["internal", "partner", "manual_confirmation"]
ServicePricingSource = Literal[
    "move_backend",
    "rule_based_estimator",
    "included_in_quote",
    "direct_request_only",
    "not_available",
]
ServiceScope = Literal["core_service", "addon", "standalone_or_addon", "request_based"]


@dataclass(frozen=True)
class ServiceTruth:
    key: str
    name_de: str
    name_en: str
    availability: ServiceAvailability
    fulfillment_mode: ServiceFulfillment
    scope: ServiceScope
    pricing_source: ServicePricingSource
    extra_price_possible: bool
    standalone_available: bool
    required_details: tuple[str, ...]
    optional_details: tuple[str, ...]
    keywords_de: tuple[str, ...]
    keywords_en: tuple[str, ...]
    source_pages_de: tuple[str, ...]
    source_pages_en: tuple[str, ...]
    summary_de: str
    summary_en: str
    note_de: str | None = None
    note_en: str | None = None
    pricing_note_de: str | None = None
    pricing_note_en: str | None = None


def _normalize_text(value: str) -> str:
    return (
        " ".join((value or "").lower().strip().split())
        .replace("ae", "ae")
        .replace("oe", "oe")
        .replace("ue", "ue")
        .replace("ss", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


SERVICE_REGISTRY: dict[str, ServiceTruth] = {
    "umzug": ServiceTruth(
        key="umzug",
        name_de="Umzug",
        name_en="Moving service",
        availability="offered",
        fulfillment_mode="internal",
        scope="core_service",
        pricing_source="move_backend",
        extra_price_possible=True,
        standalone_available=True,
        required_details=("startort", "zielort"),
        optional_details=(
            "zimmer",
            "strecke",
            "etagen",
            "aufzug",
            "laufwege",
            "umzugsdatum",
            "zusatzleistungen",
        ),
        keywords_de=("umzug", "umziehen", "umzugsservice", "privatumzug", "firmenumzug"),
        keywords_en=("move", "moving", "moving service", "relocation"),
        source_pages_de=("/ueber-uns.html", "/umzugsrechner.html"),
        source_pages_en=("/ueber-uns-en.html", "/umzugsrechner-en.html"),
        summary_de="Klarumzug24 bietet Privat-, Firmen-, Nah- und Fernumzuege an.",
        summary_en="Klarumzug24 offers private, business, local and long-distance moves.",
        note_de="Die genaue Planung haengt vom Umfang, Zugang und den Zusatzleistungen ab.",
        note_en="The exact scope depends on access, volume and extra services.",
        pricing_note_de="Eine Preisangabe darf nur als unverbindliche Schaetzung aus der bestehenden Preislogik kommen.",
        pricing_note_en="Any price may only be given as a non-binding estimate from the existing pricing logic.",
    ),
    "einzeltransport": ServiceTruth(
        key="einzeltransport",
        name_de="Einzeltransport",
        name_en="Single item transport",
        availability="offered",
        fulfillment_mode="internal",
        scope="standalone_or_addon",
        pricing_source="rule_based_estimator",
        extra_price_possible=True,
        standalone_available=True,
        required_details=("startort", "transportgut"),
        optional_details=("zielort", "gewicht", "zugang"),
        keywords_de=(
            "einzeltransport",
            "transport",
            "abholung",
            "lieferung",
            "waschmaschine",
            "kuehlschrank",
            "sofa",
            "klavier",
            "safe",
        ),
        keywords_en=("single transport", "item transport", "pickup", "delivery"),
        source_pages_de=("/ueber-uns.html",),
        source_pages_en=("/ueber-uns-en.html",),
        summary_de="Klarumzug24 nennt auf der Website Umzuege und Transporte; Einzeltransporte koennen direkt angefragt werden.",
        summary_en="Klarumzug24 mentions moves and transports on the website; single-item transports can be requested directly.",
        note_de="Bei schweren oder ungewoehnlichen Gegenstaenden sind genaue Angaben wichtig.",
        note_en="Precise details are important for heavy or unusual items.",
        pricing_note_de="Eine Schaetzung ist nur moeglich, wenn Startort und Transportgut klar sind.",
        pricing_note_en="An estimate is only possible once the item and pickup location are clear.",
    ),
    "moebelmontage": ServiceTruth(
        key="moebelmontage",
        name_de="Moebelmontage und Demontage",
        name_en="Furniture assembly and disassembly",
        availability="offered",
        fulfillment_mode="internal",
        scope="standalone_or_addon",
        pricing_source="rule_based_estimator",
        extra_price_possible=True,
        standalone_available=True,
        required_details=("ort", "moebelart"),
        optional_details=("menge", "aufbau_oder_abbau"),
        keywords_de=("montage", "demontage", "moebelmontage", "aufbau", "abbau", "ikea"),
        keywords_en=("assembly", "disassembly", "furniture assembly"),
        source_pages_de=("/index.html", "/umzugsrechner.html"),
        source_pages_en=("/index-en.html", "/umzugsrechner-en.html"),
        summary_de="Montage und Demontage sind auf der Website als Leistung und Zusatzleistung genannt.",
        summary_en="Assembly and disassembly are listed on the website as services and add-ons.",
        note_de="Fuer Kuechen oder komplexe Moebel sollte der Umfang moeglichst genau beschrieben werden.",
        note_en="For kitchens or complex furniture, the scope should be described as precisely as possible.",
        pricing_note_de="Eine Schaetzung ist nur unverbindlich und haengt stark von Moebelart und Aufwand ab.",
        pricing_note_en="Any estimate is non-binding and strongly depends on the furniture type and effort.",
    ),
    "entsorgung": ServiceTruth(
        key="entsorgung",
        name_de="Entsorgung",
        name_en="Disposal",
        availability="offered",
        fulfillment_mode="internal",
        scope="standalone_or_addon",
        pricing_source="rule_based_estimator",
        extra_price_possible=True,
        standalone_available=True,
        required_details=("ort", "was_genau"),
        optional_details=("menge", "zugang", "groesse"),
        keywords_de=("entsorgung", "entruempelung", "raeumung", "alte moebel", "abholen"),
        keywords_en=("disposal", "clearance", "junk removal"),
        source_pages_de=("/umzugsrechner.html",),
        source_pages_en=("/umzugsrechner-en.html",),
        summary_de="Entsorgung alter Moebel oder Gegenstaende ist auf der Website als anfragbare Zusatzleistung genannt.",
        summary_en="Disposal of old furniture or items is listed on the website as a requestable add-on service.",
        note_de="Fuer einzelne Faelle ist auch eine direkte Anfrage sinnvoll.",
        note_en="For individual cases, a direct request is advisable.",
        pricing_note_de="Eine Schaetzung ist nur moeglich, wenn Ort und Entsorgungsumfang klar sind.",
        pricing_note_en="An estimate is only possible once the location and disposal scope are clear.",
    ),
    "verpackung": ServiceTruth(
        key="verpackung",
        name_de="Verpackungsservice und Verpackungsmaterial",
        name_en="Packing service and packing material",
        availability="offered",
        fulfillment_mode="internal",
        scope="addon",
        pricing_source="included_in_quote",
        extra_price_possible=True,
        standalone_available=False,
        required_details=("umfang",),
        optional_details=("kartons", "zerbrechliche_teile"),
        keywords_de=("verpackung", "verpackungsservice", "verpackungsmaterial", "kartons", "einpacken"),
        keywords_en=("packing", "packing service", "boxes"),
        source_pages_de=("/index.html", "/umzugsrechner.html"),
        source_pages_en=("/index-en.html", "/umzugsrechner-en.html"),
        summary_de="Verpackungsservice und Material sind auf der Website als moegliche Zusatzleistungen genannt.",
        summary_en="Packing service and packing material are listed on the website as possible add-on services.",
        note_de="Der genaue Aufwand wird zusammen mit der Umzugsanfrage geprueft.",
        note_en="The exact effort is reviewed together with the move request.",
        pricing_note_de="Kein fixer Chat-Preis; der Aufwand wird in der Anfrage oder Schaetzung mitberuecksichtigt.",
        pricing_note_en="No fixed chat price; the effort is considered in the request or estimate.",
    ),
    "auspackservice": ServiceTruth(
        key="auspackservice",
        name_de="Auspackservice",
        name_en="Unpacking service",
        availability="offered",
        fulfillment_mode="internal",
        scope="addon",
        pricing_source="included_in_quote",
        extra_price_possible=True,
        standalone_available=False,
        required_details=("umfang",),
        optional_details=("moebel", "kartons"),
        keywords_de=("auspackservice", "auspacken"),
        keywords_en=("unpacking", "unpacking service"),
        source_pages_de=("/umzugsrechner.html",),
        source_pages_en=("/umzugsrechner-en.html",),
        summary_de="Auspackservice ist im Umzugsrechner als Zusatzleistung vorgesehen.",
        summary_en="Unpacking service is available in the moving calculator as an add-on.",
        note_de="Die Verfuegbarkeit wird im Einzelfall geprueft.",
        note_en="Availability is checked case by case.",
        pricing_note_de="Kein fixer Chat-Preis; die Zusatzleistung wird in der Anfrage mitberuecksichtigt.",
        pricing_note_en="No fixed chat price; the add-on is considered in the request.",
    ),
    "express": ServiceTruth(
        key="express",
        name_de="Express-Umzug oder kurzfristige Anfrage",
        name_en="Express move or short-notice request",
        availability="offered",
        fulfillment_mode="internal",
        scope="request_based",
        pricing_source="direct_request_only",
        extra_price_possible=True,
        standalone_available=False,
        required_details=("termin", "route"),
        optional_details=("umfang",),
        keywords_de=("express", "kurzfristig", "sofort", "eilig"),
        keywords_en=("express", "short notice", "urgent"),
        source_pages_de=("/umzugsrechner.html",),
        source_pages_en=("/umzugsrechner-en.html",),
        summary_de="Express- oder kurzfristige Umzuege sind grundsaetzlich moeglich, aber immer von der Verfuegbarkeit abhaengig.",
        summary_en="Express or short-notice moves may be possible but always depend on availability.",
        note_de="Solche Faelle sollten direkt angefragt werden.",
        note_en="These cases should be requested directly.",
        pricing_note_de="Kein fixer Chat-Preis; Aufwand und Verfuegbarkeit muessen zuerst geprueft werden.",
        pricing_note_en="No fixed chat price; effort and availability must be checked first.",
    ),
    "halteverbotszone": ServiceTruth(
        key="halteverbotszone",
        name_de="Halteverbotszone",
        name_en="No-parking zone arrangement",
        availability="offered",
        fulfillment_mode="internal",
        scope="addon",
        pricing_source="direct_request_only",
        extra_price_possible=True,
        standalone_available=False,
        required_details=("ort", "termin"),
        optional_details=("dauer",),
        keywords_de=("halteverbotszone", "parkmoeglichkeit", "parken"),
        keywords_en=("no-parking zone", "parking"),
        source_pages_de=("/agb.html", "/umzugsrechner.html"),
        source_pages_en=("/agb-en.html", "/umzugsrechner-en.html"),
        summary_de="Eine Halteverbotszone kann nach vorheriger Vereinbarung organisiert werden.",
        summary_en="A no-parking zone can be arranged by prior agreement.",
        note_de="Ohne geeignete Parkmoeglichkeit koennen zusaetzliche Aufwaende entstehen.",
        note_en="Without suitable parking, additional effort may arise.",
        pricing_note_de="Keine feste Chat-Pauschale; das muss vorab abgestimmt werden.",
        pricing_note_en="No fixed chat fee; this must be coordinated in advance.",
    ),
    "laminat": ServiceTruth(
        key="laminat",
        name_de="Laminat- oder Parkett-Abbau",
        name_en="Laminate or parquet removal",
        availability="manual_confirmation_required",
        fulfillment_mode="manual_confirmation",
        scope="request_based",
        pricing_source="direct_request_only",
        extra_price_possible=True,
        standalone_available=False,
        required_details=("ort", "flaeche"),
        optional_details=("entsorgung", "zugang"),
        keywords_de=("laminat", "parkett", "bodenbelag", "boden entfernen"),
        keywords_en=("laminate", "parquet", "flooring removal"),
        source_pages_de=("/kontakt.html",),
        source_pages_en=("/kontakt-en.html",),
        summary_de="Laminat- oder Parkett-Abbau ist im aktuellen oeffentlichen Website-/FAQ-Stand nicht als klare Standardleistung bestaetigt.",
        summary_en="Laminate or parquet removal is not clearly confirmed as a standard public service in the current website/FAQ state.",
        note_de="Bitte direkt anfragen, damit geprueft werden kann, ob und wie wir den Fall uebernehmen.",
        note_en="Please contact us directly so we can check whether and how we can take on the case.",
        pricing_note_de="Kein Chat-Preis ohne manuelle Freigabe, weil die Leistung aktuell nicht als feste Standardleistung bestaetigt ist.",
        pricing_note_en="No chat price without manual confirmation because the service is not currently confirmed as a fixed standard service.",
    ),
}

SERVICE_OVERVIEW_KEYWORDS_DE = (
    "welche leistungen",
    "was bietet ihr",
    "was uebernehmt ihr",
    "welche services",
    "macht ihr alles",
)
SERVICE_OVERVIEW_KEYWORDS_EN = (
    "which services",
    "what do you offer",
    "what services do you provide",
)


def get_service_truth(key: str) -> ServiceTruth | None:
    return SERVICE_REGISTRY.get(key)


def _get_keywords(service: ServiceTruth, lang: ChatLanguage) -> tuple[str, ...]:
    return service.keywords_en if lang == "en" else service.keywords_de


def _get_pages(service: ServiceTruth, lang: ChatLanguage) -> tuple[str, ...]:
    return service.source_pages_en if lang == "en" else service.source_pages_de


def _fulfillment_label(service: ServiceTruth, lang: ChatLanguage) -> str:
    labels = {
        "de": {
            "internal": "intern durch Klarumzug24",
            "partner": "ueber einen Partner",
            "manual_confirmation": "nur nach direkter Einzelfallpruefung",
        },
        "en": {
            "internal": "handled internally by Klarumzug24",
            "partner": "handled via a partner",
            "manual_confirmation": "only after direct case-by-case confirmation",
        },
    }
    return labels["en" if lang == "en" else "de"][service.fulfillment_mode]


def _score_service_match(normalized_text: str, service: ServiceTruth, lang: ChatLanguage) -> float:
    score = 0.0
    for keyword in _get_keywords(service, lang):
        normalized_keyword = _normalize_text(keyword)
        if not normalized_keyword:
            continue
        if normalized_text == normalized_keyword:
            score += 3.0
        elif normalized_keyword in normalized_text:
            score += 1.2
    return score


def find_best_service_truth(user_text: str, lang: ChatLanguage = "de") -> dict[str, object] | None:
    normalized_text = _normalize_text(user_text)
    if not normalized_text:
        return None

    best_key: str | None = None
    best_score = 0.0
    for key, service in SERVICE_REGISTRY.items():
        score = _score_service_match(normalized_text, service, lang)
        if score > best_score:
            best_key = key
            best_score = score

    if not best_key or best_score < 1.2:
        return None

    return {
        "key": best_key,
        "score": round(best_score, 3),
        "service": SERVICE_REGISTRY[best_key],
    }


def is_service_overview_question(user_text: str, lang: ChatLanguage = "de") -> bool:
    normalized_text = _normalize_text(user_text)
    keywords = SERVICE_OVERVIEW_KEYWORDS_EN if lang == "en" else SERVICE_OVERVIEW_KEYWORDS_DE
    return any(keyword in normalized_text for keyword in keywords)


def build_service_truth_reply(
    service: ServiceTruth,
    *,
    lang: ChatLanguage = "de",
    pricing_related: bool = False,
) -> str:
    if lang == "en":
        pages = ", ".join(_get_pages(service, lang))
        if pricing_related:
            return (
                f"{service.summary_en} {service.pricing_note_en or ''} "
                f"If you want to continue, please share the missing details or contact us directly. "
                f"Relevant page: {pages}."
            ).strip()
        return (
            f"{service.summary_en} "
            f"Fulfilment: {_fulfillment_label(service, lang)}. "
            f"{service.note_en or ''} "
            f"Relevant page: {pages}."
        ).strip()

    pages = ", ".join(_get_pages(service, lang))
    if pricing_related:
        return (
            f"{service.summary_de} {service.pricing_note_de or ''} "
            f"Wenn Sie moechten, nennen Sie bitte die fehlenden Angaben oder fragen Sie direkt an. "
            f"Relevante Seite: {pages}."
        ).strip()
    return (
        f"{service.summary_de} "
        f"Abwicklung: {_fulfillment_label(service, lang)}. "
        f"{service.note_de or ''} "
        f"Relevante Seite: {pages}."
    ).strip()


def build_service_overview_reply(lang: ChatLanguage = "de") -> str:
    offered = [
        service.name_en if lang == "en" else service.name_de
        for service in SERVICE_REGISTRY.values()
        if service.availability == "offered" and service.scope != "addon"
    ]
    add_ons = [
        service.name_en if lang == "en" else service.name_de
        for service in SERVICE_REGISTRY.values()
        if service.availability == "offered" and service.scope == "addon"
    ]
    manual_only = [
        service.name_en if lang == "en" else service.name_de
        for service in SERVICE_REGISTRY.values()
        if service.availability == "manual_confirmation_required"
    ]

    if lang == "en":
        reply = (
            "Klarumzug24 mainly confirms these services locally: "
            f"{', '.join(offered)}. "
        )
        if add_ons:
            reply += f"Possible add-ons include {', '.join(add_ons)}. "
        if manual_only:
            reply += f"Services such as {', '.join(manual_only)} currently require direct confirmation. "
        reply += "Exact availability and pricing depend on the request details."
        return reply

    reply = (
        "Klarumzug24 bestaetigt lokal vor allem diese Leistungen: "
        f"{', '.join(offered)}. "
    )
    if add_ons:
        reply += f"Moegliche Zusatzleistungen sind unter anderem {', '.join(add_ons)}. "
    if manual_only:
        reply += (
            f"Leistungen wie {', '.join(manual_only)} brauchen aktuell eine direkte Einzelfallpruefung. "
        )
    reply += "Die genaue Verfuegbarkeit und Preiswirkung haengt vom Auftrag ab."
    return reply
