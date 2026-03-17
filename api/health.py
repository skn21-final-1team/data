from fastapi import APIRouter
from sqlalchemy import text

from db.database import DbSession
from schemas.health import HealthResponse

router = APIRouter()


@router.get("/health")
def health_check(db: DbSession) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return HealthResponse(database=db_status)
