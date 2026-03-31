import secrets

from fastapi import Header, HTTPException

from app.core.config import ADMIN_API_KEY
from app.core.database import SessionLocal
from app.models import CompanyDB


def require_admin_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not x_api_key or not ADMIN_API_KEY or not secrets.compare_digest(x_api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="invalid admin api key")


def require_company_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing company api key")

    db = SessionLocal()
    try:
        company = (
            db.query(CompanyDB)
            .filter(CompanyDB.api_key == x_api_key, CompanyDB.is_active.is_(True))
            .first()
        )
        if not company:
            raise HTTPException(status_code=401, detail="invalid company api key")
        return {
            "id": company.id,
            "name": company.name,
            "api_key": company.api_key,
        }
    finally:
        db.close()
