from datetime import datetime

from fastapi import HTTPException


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=422, detail="phone is required")

    if digits.startswith("0049"):
        national_number = digits[4:]
    elif digits.startswith("49"):
        national_number = digits[2:]
    elif digits.startswith("0"):
        national_number = digits[1:]
    else:
        raise HTTPException(
            status_code=422,
            detail="phone must start with 0, 49, +49 or 0049",
        )

    if national_number.startswith("0"):
        national_number = national_number[1:]

    if not national_number.isdigit() or len(national_number) < 6 or len(national_number) > 13:
        raise HTTPException(status_code=422, detail="phone is invalid")

    return f"+49{national_number}"


def validate_non_negative_int(label: str, value: int | None) -> None:
    if value is not None and value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be >= 0")


def validate_non_negative_float(label: str, value: float | None) -> None:
    if value is not None and value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be >= 0")


def parse_iso_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {field_name} format") from exc
