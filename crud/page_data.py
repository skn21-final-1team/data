from sqlalchemy import text
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


def search_by_embedding(
    db: Session,
    query_embedding: list[float],
    notebook_id: int,
    top_k: int = 5,
) -> list[dict]:
    """pgvector 코사인 유사도 검색 (notebook_id 범위)."""
    stmt = text("""
        SELECT
            pd.id,
            pd.chunk_text,
            pd.payload,
            pd.source_id,
            s.url   AS source_url,
            s.title AS source_title,
            (1 - (pd.embedding <=> :embedding)) AS similarity
        FROM page_data pd
        JOIN source s ON pd.source_id = s.id
        WHERE s.notebook_id = :notebook_id
        ORDER BY pd.embedding <=> :embedding
        LIMIT :top_k
    """)

    rows = db.execute(
        stmt,
        {"embedding": str(query_embedding), "notebook_id": notebook_id, "top_k": top_k},
    ).fetchall()

    return [
        {
            "id": row.id,
            "chunk_text": row.chunk_text,
            "payload": row.payload,
            "source_id": row.source_id,
            "source_url": row.source_url,
            "source_title": row.source_title,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]
