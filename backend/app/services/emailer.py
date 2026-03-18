import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value if value else default


def _as_text(value: object | None) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"


def send_lead_notification(
    lead: dict,
    photo_attachment: dict | None = None,
) -> None:
    """
    Send one email notification for a created/updated lead.
    Uses SMTP over SSL (Hostinger: smtp.hostinger.com:465).
    """

    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "465") or "465")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    sender = _env("MAIL_FROM") or _env("SMTP_FROM", user)
    recipient = _env("MAIL_TO") or _env("NOTIFY_TO", user)

    missing = [
        key
        for key, current in {
            "SMTP_HOST": host,
            "SMTP_USER": user,
            "SMTP_PASS": password,
            "MAIL_FROM": sender,
            "MAIL_TO": recipient,
        }.items()
        if not current
    ]
    if missing:
        raise RuntimeError(f"Missing SMTP config in environment: {', '.join(missing)}")

    created_at = lead.get("created_at") or datetime.now(timezone.utc).isoformat()

    msg = EmailMessage()
    msg["Subject"] = f"[Klarumzug24] New lead: {_as_text(lead.get('name'))}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        "\n".join(
            [
                "New lead created",
                "=================",
                f"Created: {_as_text(created_at)}",
                f"Lead ID: {_as_text(lead.get('id'))}",
                f"Name: {_as_text(lead.get('name'))}",
                f"Phone: {_as_text(lead.get('phone'))}",
                f"Email: {_as_text(lead.get('email'))}",
                f"From city: {_as_text(lead.get('from_city'))}",
                f"To city: {_as_text(lead.get('to_city'))}",
                f"Rooms: {_as_text(lead.get('rooms'))}",
                f"Distance (km): {_as_text(lead.get('distance_km'))}",
                f"Express: {_as_text(lead.get('express'))}",
                f"Photo name: {_as_text(lead.get('photo_name'))}",
                f"AGB accepted: {_as_text(lead.get('accepted_agb'))}",
                f"Privacy accepted: {_as_text(lead.get('accepted_privacy'))}",
                "",
                "Message:",
                _as_text(lead.get("message")),
                "",
                "This lead is already stored in your DB.",
            ]
        )
    )

    if photo_attachment:
        content = photo_attachment.get("content")
        filename = _as_text(photo_attachment.get("filename"))
        content_type = str(photo_attachment.get("content_type") or "application/octet-stream")
        maintype, subtype = (
            content_type.split("/", 1)
            if "/" in content_type
            else ("application", "octet-stream")
        )
        if isinstance(content, bytes) and content and filename != "-":
            msg.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

    with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
