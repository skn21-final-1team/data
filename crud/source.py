from sqlalchemy import func
from sqlalchemy.orm import Session

from models.source import SourceModel


def get_sources_with_summary(db: Session, min_length: int = 10) -> list[SourceModel]:
    return (
        db.query(SourceModel)
        .filter(
            SourceModel.summary.is_not(None),
            func.length(SourceModel.summary) > min_length,
        )
        .all()
    )


def create_source(
    db: Session,
    url: str,
    notebook_id: int,
    directory_id: int | None = None,
    title: str | None = None,
    summary: str | None = None,
) -> SourceModel:
    source = SourceModel(
        url=url,
        title=title,
        summary=summary,
        notebook_id=notebook_id,
        directory_id=directory_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source_status(
    db: Session,
    source_id: int,
    status: str,
    title: str | None = None,
    summary: str | None = None,
) -> None:
    """source 상태 업데이트. 크롤링 성공 시 본문도 함께 저장."""
    updates: dict[str, object] = {"status": status}
    if title is not None:
        updates["title"] = title
    if summary is not None:
        updates["summary"] = summary
    db.query(SourceModel).filter(SourceModel.id == source_id).update(updates)
    db.commit()
