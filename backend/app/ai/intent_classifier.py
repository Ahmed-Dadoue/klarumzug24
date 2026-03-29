"""
Intent classification for chat requests.
Determines the user's intent and the service they're inquiring about.
"""
from typing import Optional
from .services import ServiceType, identify_service_type

class IntentType:
    """Intent types."""
    PRICING_INQUIRY = "pricing_inquiry"  # User asking for price
    GENERAL_QUESTION = "general_question"  # About services/regions/contact
    SERVICE_DETAILS = "service_details"  # Providing details about service
    CONTACT_REQUEST = "contact_request"  # Want to contact/call
    FEEDBACK = "feedback"  # Complaining or praising
    CLARIFICATION = "clarification"  # Asking for clarification


class ClassifiedIntent:
    """Result of intent classification."""
    def __init__(
        self,
        intent_type: str,
        service_type: Optional[ServiceType] = None,
        confidence: float = 0.0,
        reasoning: str = "",
    ):
        self.intent_type = intent_type
        self.service_type = service_type
        self.confidence = confidence
        self.reasoning = reasoning

    def __repr__(self):
        return f"Intent({self.intent_type}, service={self.service_type}, conf={self.confidence:.2f})"


def classify_intent(user_message: str, lang: str = "de") -> ClassifiedIntent:
    """
    Classify user intent from their message.
    Returns: ClassifiedIntent with type, service, confidence.
    """
    text_lower = user_message.lower().strip()
    
    # Detect intent type
    
    # 1. Pricing inquiry
    pricing_keywords = [
        "preis", "kostet", "kosten", "wie viel", "wieviel",
        "angebot", "schätzung", "schatzung", "günstig", "gunstig",
        "teuer", "zu teuer", "bezahlbar", "euro", "€"
    ]
    is_pricing = any(kw in text_lower for kw in pricing_keywords)
    
    # 2. Contact request
    contact_keywords = [
        "anrufen", "telefonieren", "whatsapp", "email", "kontakt",
        "beraterr", "sprechen", "termin", "besuch", "vor ort",
        "kommt vorbei"
    ]
    is_contact = any(kw in text_lower for kw in contact_keywords)
    
    # 3. Feedback
    feedback_keywords = [
        "danke", "super", "gut", "schlecht", "furchtbar", "awesome",
        "warum", "wieso", "macht keinen sinn", "passt nicht"
    ]
    is_feedback = any(kw in text_lower for kw in feedback_keywords)
    
    # 4. General question
    general_keywords = [
        "was", "wie", "welche", "leistungen", "regionen", "gehört",
        "angebote", "services", "ihr"
    ]
    is_general = any(kw in text_lower for kw in general_keywords)
    
    # Try to identify service
    service_type = identify_service_type(text_lower)
    
    # Determine primary intent
    if is_pricing and service_type:
        return ClassifiedIntent(
            intent_type=IntentType.PRICING_INQUIRY,
            service_type=service_type,
            confidence=0.95,
            reasoning=f"Pricing inquiry for {service_type} service"
        )
    elif is_pricing:
        return ClassifiedIntent(
            intent_type=IntentType.PRICING_INQUIRY,
            service_type=None,
            confidence=0.85,
            reasoning="Pricing inquiry but service not clear"
        )
    elif is_contact:
        return ClassifiedIntent(
            intent_type=IntentType.CONTACT_REQUEST,
            service_type=service_type,
            confidence=0.9,
            reasoning="User wants to contact or meet"
        )
    elif is_feedback:
        return ClassifiedIntent(
            intent_type=IntentType.FEEDBACK,
            service_type=service_type,
            confidence=0.8,
            reasoning="User providing feedback or clarification"
        )
    elif service_type:
        return ClassifiedIntent(
            intent_type=IntentType.SERVICE_DETAILS,
            service_type=service_type,
            confidence=0.9,
            reasoning=f"Details about {service_type} service"
        )
    elif is_general:
        return ClassifiedIntent(
            intent_type=IntentType.GENERAL_QUESTION,
            service_type=None,
            confidence=0.7,
            reasoning="General question about services"
        )
    else:
        return ClassifiedIntent(
            intent_type=IntentType.GENERAL_QUESTION,
            service_type=None,
            confidence=0.3,
            reasoning="Unclear intent"
        )
