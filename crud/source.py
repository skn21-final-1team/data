from sqlalchemy.orm import Session
from sqlalchemy import select

from models.source import SourceModel, CrawlModel

def get_source_by_id(db: Session, source_id: int) -> SourceModel | None:
    return db.query(SourceModel).filter(SourceModel.id == source_id).first()


def update_source_status(
    db: Session,
    source_id: int,
    status: str | None = None,
    title: str | None = None,
    raw: str | None = None,
    refined: str | None = None,
    summary: str | None = None,
) -> None:
    updates: dict[str, object] = {}
    if status is not None:
        updates["status"] = status
    if title is not None:
        updates["title"] = title
    if raw is not None:
        updates["raw"] = raw
    if refined is not None:
        updates["refined"] = refined
    if summary is not None:
        updates["summary"] = summary
    if updates:
        db.query(SourceModel).filter(SourceModel.id == source_id).update(updates)
        db.commit()


def get_sources_for_crawl(db: Session, source_ids: list[int]) -> list[CrawlModel]:
    """소스 ID 리스트로 CrawlModel을 벌크 조회합니다."""
    stmt = select(CrawlModel).where(CrawlModel.id.in_(source_ids))
    return list(db.scalars(stmt).all())
