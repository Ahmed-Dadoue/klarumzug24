"""
Pricing Tool: Main interface for price calculation and service details.
This is what the bot and agent will use to get pricing information.
"""
from typing import Optional
from dataclasses import asdict

from .services import ServiceType, identify_service_type, get_service
from .pricing_calculator import calculate_price, PriceEstimate
from .intent_classifier import classify_intent, ClassifiedIntent


class PricingTool:
    """Main interface for pricing and service information."""
    
    @staticmethod
    def classify_user_message(message: str) -> ClassifiedIntent:
        """Classify what the user is asking about."""
        return classify_intent(message)
    
    @staticmethod
    def get_service_info(service_type: ServiceType):
        """Get service definition and required fields."""
        return get_service(service_type)
    
    @staticmethod
    def calculate_estimated_price(
        service_type: ServiceType,
        details: dict,
    ) -> PriceEstimate | None:
        """
        Calculate estimated price for a service.
        
        Args:
            service_type: Type of service
            details: Dict with service-specific details
        
        Returns:
            PriceEstimate or None if calculation fails
        """
        return calculate_price(service_type, details)
    
    @staticmethod
    def get_all_services():
        """Get list of all available services for bot to display."""
        from .services import SERVICES
        return {
            key: {
                "name": service.name_de,
                "description": service.description_de,
            }
            for key, service in SERVICES.items()
        }
    
    @staticmethod
    def format_price_response(estimate: PriceEstimate) -> str:
        """
        Format a price estimate into a natural German response.
        
        Example output:
        "Für die Entsorgung von 3 Sofas liegt die unverbindliche Schätzung
         bei etwa 120–180 €. Der genaue Preis hängt vom Aufwand und der Region ab."
        """
        if not estimate:
            return None
        
        response = (
            f"Für {estimate.explanation} liegt die {estimate.note} "
            f"bei etwa {estimate.min_price_eur}–{estimate.max_price_eur} {estimate.currency}."
        )
        
        # Add context about price variations
        response += (
            " Der genaue Preis kann je nach Aufwand, Region und Abtransport variieren. "
            "Für ein verbindliches Angebot können Sie uns gerne kontaktieren oder WhatsApp nutzen."
        )
        
        return response


# Singleton instance
pricing_tool = PricingTool()


def get_pricing_tool() -> PricingTool:
    """Get the pricing tool instance."""
    return pricing_tool
