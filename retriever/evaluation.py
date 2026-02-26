"""Retriever 성능 평가 (RAGAS).

testset.json의 질문-정답 쌍으로 retrieval 품질을 측정한다.

실행::
    uv run python -m retriever.evaluation
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
)

from db.database import get_db_context
from embed.config import DEFAULT_MODEL as EMBED_MODEL
from retriever.service import retrieve

logger = logging.getLogger(__name__)

TESTSET_PATH = Path("retriever/testset.json")
OUTPUT_DIR = Path("retriever/output")


def load_testset() -> list[dict]:
    """testset.json 로드.

    형식::
        [
            {
                "question": "...",
                "ground_truth": "...",
                "notebook_id": 14
            }
        ]
    """
    return json.loads(TESTSET_PATH.read_text(encoding="utf-8"))


def run_retrieval(testset: list[dict], top_k: int = 5) -> Dataset:
    """각 질문에 대해 retrieve 실행 → RAGAS Dataset 구성."""
    questions: list[str] = []
    ground_truths: list[str] = []
    contexts_list: list[list[str]] = []

    with get_db_context() as db:
        for item in testset:
            results = retrieve(
                db=db,
                query=item["question"],
                notebook_id=item["notebook_id"],
                top_k=top_k,
            )

            questions.append(item["question"])
            ground_truths.append(item["ground_truth"])
            contexts_list.append([r["chunk_text"] for r in results])

    return Dataset.from_dict(
        {
            "question": questions,
            "ground_truth": ground_truths,
            "contexts": contexts_list,
        }
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[1] 테스트셋 로드...")
    testset = load_testset()
    print(f"    {len(testset)}개 질문")

    print("[2] Retrieval 실행...")
    dataset = run_retrieval(testset)

    print("[3] RAGAS 평가 실행...")
    from openai import OpenAI
    from ragas.llms import llm_factory

    from core.config import get_settings
    from retriever.config import RAGAS_MODEL

    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    llm = llm_factory(model=RAGAS_MODEL, client=client)
    print(f"    평가 모델: {RAGAS_MODEL}")

    metrics = [
        context_precision,
        context_recall,
    ]
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=llm,
    )

    df = result.to_pandas()
    numeric_cols = df.select_dtypes(include="number").columns
    scores = {col: round(df[col].mean(), 4) for col in numeric_cols}

    model_tag = EMBED_MODEL.replace("/", "_")
    result_path = OUTPUT_DIR / f"ragas_results_{model_tag}.json"
    detail_path = OUTPUT_DIR / f"ragas_detail_{model_tag}.csv"

    result_path.write_text(
        json.dumps(scores, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    print(f"\n[결과] 임베딩 모델: {EMBED_MODEL}")
    for metric, score in scores.items():
        print(f"  {metric}: {score}")
    print(f"\n[완료] 저장: {result_path}")


if __name__ == "__main__":
    main()
