from fastapi import APIRouter, Depends, Query

from app.api import require_admin_api_key, success_response
from app.core.database import SessionLocal
from app.core.serialization import serialize_transaction
from app.models import TransactionDB

router = APIRouter()


@router.get("/api/transactions")
def list_transactions(
    company_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(TransactionDB)
        if company_id is not None:
            query = query.filter(TransactionDB.company_id == company_id)
        if status:
            query = query.filter(TransactionDB.status == status)

        rows = query.order_by(TransactionDB.id.desc()).all()
        transactions = [serialize_transaction(r) for r in rows]
        return success_response(
            "Transactions loaded",
            data={"transactions": transactions},
            legacy={"transactions": transactions},
        )
    finally:
        db.close()
