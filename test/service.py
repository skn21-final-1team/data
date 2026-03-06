from __future__ import annotations

import logging

from crud.page_data import search_by_embedding

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    notebook_id: int,
    top_k: int = 5,
    source_ids: list[int] | None = None,
) -> list[dict]:
    """쿼리 → PGVector 코사인 유사도 검색."""
    logger.info(
        "검색 실행: notebook_id=%d, top_k=%d, query='%s'",
        notebook_id, top_k, query[:50],
    )

    results = search_by_embedding(
        query=query,
        notebook_id=notebook_id,
        top_k=top_k,
        source_ids=source_ids,
    )

    logger.info("검색 결과: %d건", len(results))
    return results
