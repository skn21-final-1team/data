"""커스텀 IR 평가 지표 (Hit Rate, MRR, NDCG).

LLM 호출 없이 동작하며, ground_truth의 핵심 키워드가
retrieved chunk에 포함되는지로 관련성을 판정한다.
"""

from __future__ import annotations

import math
import re

# 불용어 (한/영)
_STOPWORDS = frozenset(
    "a an the is was were are be been being have has had do does did "
    "will would shall should may might can could of in on at to for "
    "with by from and or but not no nor so yet both either neither "
    "은 는 이 가 을 를 에 에서 의 로 으로 와 과 도 만 까지 부터 라 다 하다 "
    "있다 없다 되다 하는 있는 없는 된 등 및 그 이다 한 할 함".split()
)


def _extract_keywords(text: str) -> set[str]:
    """텍스트에서 불용어를 제외한 키워드 집합을 추출한다."""
    tokens = re.findall(r"[a-zA-Z0-9가-힣]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _is_relevant(chunk_text: str, ground_truth: str, threshold: float = 0.4) -> bool:
    """ground_truth 키워드의 threshold 비율 이상이 chunk에 포함되면 relevant."""
    gt_keywords = _extract_keywords(ground_truth)
    if not gt_keywords:
        return False
    chunk_lower = chunk_text.lower()
    hits = sum(1 for kw in gt_keywords if kw in chunk_lower)
    return (hits / len(gt_keywords)) >= threshold


def _relevance_labels(chunks: list[str], ground_truth: str) -> list[int]:
    """각 chunk에 대해 관련성 라벨(1/0)을 반환."""
    return [1 if _is_relevant(c, ground_truth) else 0 for c in chunks]


def hit_rate(chunks: list[str], ground_truth: str) -> float:
    """top-k 안에 relevant chunk가 하나라도 있으면 1, 없으면 0."""
    labels = _relevance_labels(chunks, ground_truth)
    return 1.0 if any(labels) else 0.0


def mrr(chunks: list[str], ground_truth: str) -> float:
    """첫 번째 relevant chunk의 순위 역수. 없으면 0."""
    labels = _relevance_labels(chunks, ground_truth)
    for i, label in enumerate(labels):
        if label == 1:
            return 1.0 / (i + 1)
    return 0.0


def ndcg(chunks: list[str], ground_truth: str) -> float:
    """Normalized Discounted Cumulative Gain."""
    labels = _relevance_labels(chunks, ground_truth)
    if not any(labels):
        return 0.0

    # DCG
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(labels))

    # IDCG (이상적 순서: relevant가 앞에 몰려있는 경우)
    ideal = sorted(labels, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_single(chunks: list[str], ground_truth: str) -> dict[str, float]:
    """단일 질문에 대한 모든 지표를 계산."""
    return {
        "hit_rate": hit_rate(chunks, ground_truth),
        "mrr": mrr(chunks, ground_truth),
        "ndcg": ndcg(chunks, ground_truth),
    }


def evaluate_batch(
    results: list[dict[str, any]],
) -> dict[str, float]:
    """여러 질문의 평균 지표를 계산.

    Parameters
    ----------
    results : list[dict]
        각 항목은 {"chunks": list[str], "ground_truth": str}

    Returns
    -------
    dict[str, float]
        평균 hit_rate, mrr, ndcg
    """
    if not results:
        return {"hit_rate": 0.0, "mrr": 0.0, "ndcg": 0.0}

    scores = [evaluate_single(r["chunks"], r["ground_truth"]) for r in results]

    n = len(scores)
    return {
        "hit_rate": round(sum(s["hit_rate"] for s in scores) / n, 4),
        "mrr": round(sum(s["mrr"] for s in scores) / n, 4),
        "ndcg": round(sum(s["ndcg"] for s in scores) / n, 4),
    }
