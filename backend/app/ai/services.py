"""
Service definitions and requirements.
Each service type is defined with its required fields for pricing calculation.
"""
from dataclasses import dataclass
from typing import Literal

ServiceType = Literal[
    "umzug",
    "entsorgung", 
    "laminat",
    "moebelmontage",
    "einzeltransport"
]

@dataclass
class ServiceDefinition:
    """Defines a service type and its requirements."""
    key: ServiceType
    name_de: str
    keywords_de: list[str]
    required_fields: list[str]
    optional_fields: list[str]
    description_de: str

# Service Type Definitions
SERVICES = {
    "umzug": ServiceDefinition(
        key="umzug",
        name_de="Umzug",
        keywords_de=["umzug", "umziehen", "umzugs", "ziehe", "ziehen um", "moving", "move", "zimmer", "von", "nach", "transport"],
        required_fields=["from_city", "to_city"],
        optional_fields=["rooms", "floor_from", "floor_to", "has_elevator_from", "has_elevator_to"],
        description_de="Kompletter Umzugsservice mit Transport von Möbeln und Gegenständen"
    ),
    "entsorgung": ServiceDefinition(
        key="entsorgung",
        name_de="Entsorgung / Räumung",
        keywords_de=["entsorgung", "entsorgen", "entrümpelung", "entrümplung", "räumung", "disposal", "junk", "stickmaschine", "möbel weg", "wegschmeissen", "abholen", "möbel entsorgen"],
        required_fields=["location", "item_type"],
        optional_fields=["quantity", "size_description", "access_difficulty"],
        description_de="Entsorgung, Entrümpelung, Räumung von Gegenständen und Möbeln"
    ),
    "laminat": ServiceDefinition(
        key="laminat",
        name_de="Laminat / Parkett Abbau & Entsorgung",
        keywords_de=["laminat", "parkett", "flooring", "bodenbelag", "abbau", "disposal floor", "entfernen boden"],
        required_fields=["location", "area_m2"],
        optional_fields=["abbau_only", "entsorgung_included", "floor"],
        description_de="Abbau und Entsorgung von Laminat, Parkett oder anderen Bodenbelägen"
    ),
    "moebelmontage": ServiceDefinition(
        key="moebelmontage",
        name_de="Möbelmontage / Abbau",
        keywords_de=["montage", "aufbau", "abbau", "assembly", "ikea", "regal", "schrank", "küche"],
        required_fields=["location", "furniture_type"],
        optional_fields=["quantity", "aufbau_or_abbau"],
        description_de="Montage oder Abbau von Möbeln, Küchen, Regalen, etc."
    ),
    "einzeltransport": ServiceDefinition(
        key="einzeltransport",
        name_de="Einzeltransport",
        keywords_de=["transport", "waschmaschine", "kühlschrank", "sofa", "einzeln", "item", "kleintransport", "von nach", "klavier", "piano", "clavinova", "safe", "transport lassen"],
        required_fields=["location", "item_description"],
        optional_fields=["destination", "weight_estimate"],
        description_de="Transport von einzelnen Gegenständen oder Möbelstücken"
    )
}

def identify_service_type(user_text: str) -> ServiceType | None:
    """
    Identify the most likely service type from user text.
    Returns the service key if found, None otherwise.
    """
    user_text_lower = user_text.lower()
    user_words = set(" ".join(user_text_lower.split()).split())
    
    best_match = None
    best_score = 0
    
    for service_key, service in SERVICES.items():
        match_count = sum(1 for keyword in service.keywords_de if keyword in user_text_lower)
        if match_count > best_score:
            best_score = match_count
            best_match = service_key
    
    return best_match if best_score > 0 else None

def get_service(service_type: ServiceType) -> ServiceDefinition:
    """Get service definition by type."""
    return SERVICES[service_type]
