from fastapi import APIRouter
from sqlalchemy import text

from db.database import DbSession

router = APIRouter()


@router.get("/health")
def health_check(db: DbSession) -> dict:
    """서버 상태 및 DB 연결 확인."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "database": db_status}
