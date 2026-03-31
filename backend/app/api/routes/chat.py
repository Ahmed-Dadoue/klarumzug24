import logging

from fastapi import APIRouter

from app.ai import generate_dode_reply
from app.core.serialization import serialize_lead
from app.schemas import ChatRequestIn
from app.services.chat_service import dode_chat as chat_service_dode_chat
from app.services.lead_service import _create_lead as lead_service_create_lead

router = APIRouter()
LOGGER = logging.getLogger("klarumzug24")


@router.post("/api/chat")
def dode_chat(payload: ChatRequestIn):
    return chat_service_dode_chat(
        payload,
        generate_reply=generate_dode_reply,
        create_lead=lead_service_create_lead,
        serialize_lead=serialize_lead,
        logger=LOGGER,
    )
