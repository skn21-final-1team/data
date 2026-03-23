"""page_data CRUD — PGVector 기반 저장/검색."""

from __future__ import annotations

import json

from langchain_postgres.vectorstores import PGVector
from sqlalchemy import text

from db.database import get_db_context
from db.vector_store import get_vector_store


def delete_page_data_by_source(source_id: int) -> int:
    """source_id에 해당하는 page_data(임베딩) 삭제. 삭제된 건수 반환."""
    with get_db_context() as db:
        result = db.execute(
            text(
                """
                DELETE FROM langchain_pg_embedding
                WHERE collection_id = (
                    SELECT uuid FROM langchain_pg_collection WHERE name = :col
                )
                AND cmetadata @> CAST(:filter AS jsonb)
                """
            ),
            {"col": "page_data", "filter": json.dumps({"source_id": source_id})},
        )
        db.commit()
        return result.rowcount


def bulk_create_page_data(
    source_id: int,
    chunks: list[str],
    embeddings: list[list[float]],
    vector_store: PGVector | None = None,
) -> list[str]:
    """청크 + 임베딩을 PGVector에 저장. 반환: 생성된 ID 목록."""
    store = vector_store or get_vector_store()
    metadatas = [{"source_id": source_id, "seq": i} for i, _ in enumerate(chunks)]
    return store.add_embeddings(
        texts=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def search_by_embedding(
    query: str,
    notebook_id: int,
    top_k: int = 5,
    source_ids: list[int] | None = None,
    vector_store: PGVector | None = None,
) -> list[dict]:
    """PGVector 코사인 유사도 검색."""
    store = vector_store or get_vector_store()

    filter_dict: dict = {}
    if source_ids:
        filter_dict["source_id"] = {"$in": source_ids}

    results = store.similarity_search_with_score(
        query=query,
        k=top_k,
        filter=filter_dict if filter_dict else None,
    )

    return [
        {
            "chunk_text": doc.page_content,
            "source_id": doc.metadata.get("source_id"),
            "similarity": round(1 - score, 4),
        }
        for doc, score in results
    ]
