from sqlalchemy.orm import Session

from models.page_data import PageDataModel


def create_page_data(
    db: Session,
    source_id: int,
    chunk_text: str,
    embedding: list[float],
    payload: dict[str, str] | None = None,
) -> PageDataModel:
    page_data = PageDataModel(
        source_id=source_id,
        chunk_text=chunk_text,
        payload=payload,
        embedding=embedding,
    )
    db.add(page_data)
    db.commit()
    db.refresh(page_data)
    return page_data


def bulk_create_page_data(
    db: Session,
    source_id: int,
    chunks: list[str],
    embeddings: list[list[float]],
) -> list[PageDataModel]:
    records = [
        PageDataModel(
            source_id=source_id,
            chunk_text=chunk_text,
            embedding=embedding,
        )
        for chunk_text, embedding in zip(chunks, embeddings)
    ]
    db.add_all(records)
    db.commit()
    return records
