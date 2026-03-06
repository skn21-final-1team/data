from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from crud.page_data import search_by_embedding
from embed.service import embed_texts

logger = logging.getLogger(__name__)


def retrieve(
    db: Session,
    query: str,
    notebook_id: int,
    top_k: int = 5,
) -> list[dict]:
    """쿼리 → 임베딩 → pgvector 코사인 유사도 검색."""
    query_embedding = embed_texts([query])[0]

    logger.info(
        "검색 실행: notebook_id=%d, top_k=%d, query='%s'",
        notebook_id, top_k, query[:50],
    )

    results = search_by_embedding(
        db=db,
        query_embedding=query_embedding,
        notebook_id=notebook_id,
        top_k=top_k,
    )

    logger.info("검색 결과: %d건", len(results))
    return results
