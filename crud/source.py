from sqlalchemy.orm import Session

from models.source import SourceModel


# notebook_id, directory_id 파라미터는 해당 테이블 생성 후 추가
def create_source(
    db: Session,
    url: str,
    title: str | None,
    summary: str,
    user_id: int,
    notebook_id: int | None = None,
    directory_id: int | None = None,
) -> SourceModel:
    source = SourceModel(
        url=url,
        title=title,
        summary=summary,
        user_id=user_id,
        notebook_id=notebook_id,
        directory_id=directory_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source
