"""Main pricing interface for the chat supervisor."""

from __future__ import annotations

from .intent_classifier import ClassifiedIntent, classify_intent
from .pricing_calculator import PriceEstimate, calculate_price
from .pricing_truth import get_pricing_truth
from .services import ServiceType, get_service


class PricingTool:
    """Main interface for service details and safe price estimates."""

    @staticmethod
    def classify_user_message(message: str) -> ClassifiedIntent:
        return classify_intent(message)

    @staticmethod
    def get_service_info(service_type: ServiceType):
        return get_service(service_type)

    @staticmethod
    def get_pricing_truth(service_type: str):
        return get_pricing_truth(service_type)

    @staticmethod
    def calculate_estimated_price(
        service_type: ServiceType,
        details: dict,
    ) -> PriceEstimate | None:
        truth = get_pricing_truth(service_type)
        if truth and not truth.can_quote_estimate:
            return None
        return calculate_price(service_type, details)

    @staticmethod
    def get_all_services():
        from .services import SERVICES

        return {
            key: {
                "name": service.name_de,
                "description": service.description_de,
                "required_fields": list(service.required_fields),
            }
            for key, service in SERVICES.items()
        }

    @staticmethod
    def format_price_response(estimate: PriceEstimate | None) -> str | None:
        if not estimate:
            return None

        return (
            f"Fuer {estimate.explanation} liegt die {estimate.note} "
            f"bei etwa {estimate.min_price_eur}-{estimate.max_price_eur} {estimate.currency}. "
            "Der genaue Preis kann je nach Aufwand, Region, Zugang und Zusatzleistungen abweichen. "
            "Fuer ein verbindliches Angebot bitten wir um eine direkte Anfrage."
        )


pricing_tool = PricingTool()


def get_pricing_tool() -> PricingTool:
    return pricing_tool
