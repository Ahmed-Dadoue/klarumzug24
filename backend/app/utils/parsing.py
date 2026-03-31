import mimetypes
import os
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.schemas import LeadIn
from app.utils.normalization import normalize_form_value


def build_lead_payload(data: dict[str, Any]) -> LeadIn:
    try:
        return LeadIn.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


async def read_photo_attachment(
    photo: UploadFile | None,
    *,
    max_photo_bytes: int,
) -> dict[str, Any] | None:
    if photo is None or not getattr(photo, "filename", ""):
        return None

    filename = os.path.basename((photo.filename or "").strip())
    if not filename:
        return None

    content = await photo.read()
    if not content:
        return None
    if len(content) > max_photo_bytes:
        raise HTTPException(status_code=413, detail="photo is too large")

    content_type = (photo.content_type or "").strip().lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="photo must be an image")
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(filename)
        content_type = guessed_type or "application/octet-stream"

    return {
        "filename": filename,
        "content": content,
        "content_type": content_type,
    }


async def parse_lead_request(
    request: Request,
    *,
    max_photo_bytes: int,
) -> tuple[LeadIn, dict[str, Any] | None]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        photo = form.get("photo")
        photo_attachment = (
            await read_photo_attachment(photo, max_photo_bytes=max_photo_bytes)
            if isinstance(photo, UploadFile)
            else None
        )
        payload_data = {
            "name": normalize_form_value(form.get("name")),
            "phone": normalize_form_value(form.get("phone")),
            "email": normalize_form_value(form.get("email")),
            "conversation_id": normalize_form_value(form.get("conversation_id")),
            "from_city": normalize_form_value(form.get("from_city")),
            "to_city": normalize_form_value(form.get("to_city")),
            "rooms": normalize_form_value(form.get("rooms")),
            "distance_km": normalize_form_value(form.get("distance_km")),
            "express": normalize_form_value(form.get("express")) or False,
            "message": normalize_form_value(form.get("message")),
            "photo_name": (
                photo_attachment["filename"]
                if photo_attachment
                else normalize_form_value(form.get("photo_name"))
            ),
            "accepted_agb": normalize_form_value(form.get("accepted_agb")) or False,
            "accepted_privacy": normalize_form_value(form.get("accepted_privacy")) or False,
        }
        return build_lead_payload(payload_data), photo_attachment

    return build_lead_payload(await request.json()), None
