from sqlalchemy import func
from sqlalchemy.orm import Session

from models.source import SourceModel


def get_source_by_id(db: Session, source_id: int) -> SourceModel | None:
    return db.query(SourceModel).filter(SourceModel.id == source_id).first()


def get_sources_with_raw(db: Session, min_length: int = 10) -> list[SourceModel]:
    """raw가 있고 refined가 없는 소스 — 정제 대상."""
    return (
        db.query(SourceModel)
        .filter(
            SourceModel.raw.is_not(None),
            func.length(SourceModel.raw) > min_length,
            SourceModel.refined.is_(None),
        )
        .all()
    )


def get_sources_with_refined(db: Session, min_length: int = 10) -> list[SourceModel]:
    """refined가 있고 summary가 없는 소스 — 요약 대상."""
    return (
        db.query(SourceModel)
        .filter(
            SourceModel.refined.is_not(None),
            func.length(SourceModel.refined) > min_length,
            SourceModel.summary.is_(None),
        )
        .all()
    )


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
) -> SourceModel:
    source = SourceModel(
        url=url,
        title=title,
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
