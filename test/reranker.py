"""Cross-Encoder 기반 Reranker.

벡터 검색 결과를 쿼리와 함께 재평가하여 관련성 순으로 재정렬한다.

사용::
    from test.reranker import rerank
    reranked = rerank(query, results, top_k=5)
"""

from __future__ import annotations

import logging

from sentence_transformers import CrossEncoder

from core.device import get_device

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """모델을 싱글톤으로 로드한다."""
    global _model
    if _model is None:
        device = get_device()
        logger.info("Reranker 모델 로드: %s (%s)", MODEL_NAME, device)
        _model = CrossEncoder(MODEL_NAME, device=device)
    return _model


def rerank(
    query: str,
    results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """벡터 검색 결과를 Cross-Encoder로 재정렬한다.

    Args:
        query: 검색 쿼리
        results: retrieve()가 반환한 결과 리스트 (chunk_text 포함)
        top_k: 재정렬 후 반환할 상위 개수
    """
    if not results:
        return results

    model = _get_model()

    pairs = [(query, r["chunk_text"]) for r in results]
    scores = model.predict(pairs)

    for r, score in zip(results, scores):
        r["rerank_score"] = float(score)

    reranked = sorted(results, key=lambda r: r["rerank_score"], reverse=True)
    return reranked[:top_k]
