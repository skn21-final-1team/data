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
    title: str | None,
    summary: str,
    notebook_id: int | None = None,
    directory_id: int | None = None,
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
