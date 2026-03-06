"""Retriever 성능 평가 (RAGAS) — LLM 호출 비용 발생.

testset.json의 질문-정답 쌍으로 retrieval 품질을 측정한다.
OPENAI_API_KEY 환경변수 필요.

실행::
    uv run python -m test.evaluation
    uv run python -m test.evaluation --top_k 20
    uv run python -m test.evaluation --mode reranker --top_k 5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
)

from chunk.service import CHUNKER
from embed.config import DEFAULT_MODEL as EMBED_MODEL
from test.service import retrieve

logger = logging.getLogger(__name__)

RAGAS_MODEL = "gpt-4o"
TESTSET_PATH = Path("test/testset.json")
OUTPUT_ROOT = Path("test/output")


def _build_output_dir(mode: str, top_k: int) -> Path:
    model_tag = EMBED_MODEL.replace("/", "_")
    chunk_tag = CHUNKER.config.strategy_name
    return OUTPUT_ROOT / model_tag / chunk_tag / f"{mode}_top{top_k}"


def load_testset() -> list[dict]:
    return json.loads(TESTSET_PATH.read_text(encoding="utf-8"))


def run_retrieval(
    testset: list[dict],
    top_k: int = 5,
    mode: str = "baseline",
) -> Dataset:
    """각 질문에 대해 retrieve 실행 → RAGAS Dataset 구성."""
    questions: list[str] = []
    ground_truths: list[str] = []
    contexts_list: list[list[str]] = []

    use_reranker = mode == "reranker"
    if use_reranker:
        from test.reranker import rerank

        fetch_k = max(top_k, 20)
        print(f"    Reranker 활성: 벡터검색 top-{fetch_k} → 리랭크 top-{top_k}")
    else:
        fetch_k = top_k

    for i, item in enumerate(testset, 1):
        results = retrieve(
            query=item["question"],
            notebook_id=item["notebook_id"],
            top_k=fetch_k,
        )

        if use_reranker:
            results = rerank(item["question"], results, top_k=top_k)

        questions.append(item["question"])
        ground_truths.append(item["ground_truth"])
        contexts_list.append([r["chunk_text"] for r in results])
        print(f"    [{i}/{len(testset)}] {item['question'][:40]}... → {len(results)}건")

    return Dataset.from_dict(
        {
            "question": questions,
            "ground_truth": ground_truths,
            "contexts": contexts_list,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="baseline", choices=["baseline", "reranker"])
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()

    output_dir = _build_output_dir(args.mode, args.top_k)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[설정] 모델={EMBED_MODEL}, 청킹={CHUNKER.config.strategy_name}, "
        f"mode={args.mode}, top_k={args.top_k}"
    )
    print(f"[출력] {output_dir}/")

    print("\n[1] 테스트셋 로드...")
    testset = load_testset()
    print(f"    {len(testset)}개 질문")

    print("[2] Retrieval 실행...")
    dataset = run_retrieval(testset, top_k=args.top_k, mode=args.mode)

    print("[3] RAGAS 평가 실행...")
    from openai import OpenAI
    from ragas.llms import llm_factory

    from core.config import get_settings

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

    result_data = {
        "embed_model": EMBED_MODEL,
        "chunk_strategy": CHUNKER.config.strategy_name,
        "mode": args.mode,
        "top_k": args.top_k,
        "scores": scores,
    }

    result_path = output_dir / "ragas_results.json"
    detail_path = output_dir / "ragas_detail.csv"

    result_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    print(
        f"\n[결과] {EMBED_MODEL} / {CHUNKER.config.strategy_name} / {args.mode} / top_{args.top_k}"
    )
    for metric, score in scores.items():
        print(f"  {metric}: {score}")
    print(f"\n[완료] 저장: {output_dir}/")


if __name__ == "__main__":
    main()
