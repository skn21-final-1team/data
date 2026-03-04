"""Retriever 성능 평가 — IR 지표 (Hit Rate, MRR, NDCG) + MLflow.

실행::
    uv run python -m retriever.evaluation_ir --mode baseline --top_k 5
    uv run python -m retriever.evaluation_ir --mode reranker --top_k 5
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import mlflow

from chunk.service import CHUNKER
from db.database import get_db_context
from embed.config import DEFAULT_MODEL as EMBED_MODEL
from retriever.metrics import evaluate_batch, evaluate_single
from retriever.service import retrieve

logger = logging.getLogger(__name__)

TESTSET_PATH = Path("retriever/testset.json")
OUTPUT_ROOT = Path("retriever/output")


def _build_output_dir(mode: str, top_k: int) -> Path:
    model_tag = EMBED_MODEL.replace("/", "_")
    chunk_tag = CHUNKER.config.strategy_name
    return OUTPUT_ROOT / model_tag / chunk_tag / f"{mode}_top{top_k}"


def load_testset() -> list[dict]:
    return json.loads(TESTSET_PATH.read_text(encoding="utf-8"))


def run_evaluation(
    testset: list[dict],
    top_k: int = 5,
    mode: str = "baseline",
) -> tuple[dict[str, float], list[dict]]:
    """각 질문에 대해 retrieve → 커스텀 IR 지표 계산.

    Returns
    -------
    (평균 지표, 질문별 상세 결과)
    """
    use_reranker = mode == "reranker"
    if use_reranker:
        from retriever.reranker import rerank

        fetch_k = max(top_k, 20)
        print(f"    Reranker 활성: 벡터검색 top-{fetch_k} → 리랭크 top-{top_k}")
    else:
        fetch_k = top_k

    batch_input: list[dict] = []
    details: list[dict] = []

    for i, item in enumerate(testset, 1):
        with get_db_context() as db:
            results = retrieve(
                db=db,
                query=item["question"],
                notebook_id=item["notebook_id"],
                top_k=fetch_k,
            )

        if use_reranker:
            results = rerank(item["question"], results, top_k=top_k)

        chunks = [r["chunk_text"] for r in results]
        ground_truth = item["ground_truth"]

        scores = evaluate_single(chunks, ground_truth)
        batch_input.append({"chunks": chunks, "ground_truth": ground_truth})

        details.append({
            "question": item["question"],
            "ground_truth": ground_truth,
            "num_results": len(results),
            **scores,
        })

        print(
            f"    [{i}/{len(testset)}] {item['question'][:40]}... "
            f"→ hit={scores['hit_rate']}, mrr={scores['mrr']:.4f}, ndcg={scores['ndcg']:.4f}"
        )

    avg_scores = evaluate_batch(batch_input)
    return avg_scores, details


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="baseline", choices=["baseline", "reranker"])
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()

    output_dir = _build_output_dir(args.mode, args.top_k)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_size = CHUNKER.config.chunk_size
    chunk_overlap = CHUNKER.config.chunk_overlap
    chunk_strategy = CHUNKER.config.strategy_name

    print(
        f"[설정] 모델={EMBED_MODEL}, 청킹={chunk_strategy} "
        f"(size={chunk_size}, overlap={chunk_overlap}), "
        f"mode={args.mode}, top_k={args.top_k}"
    )
    print(f"[출력] {output_dir}/\n")

    # MLflow 실험 추적
    mlflow.set_experiment("retriever-evaluation")

    with mlflow.start_run(run_name=f"{args.mode}_top{args.top_k}_{chunk_strategy}"):
        mlflow.log_params({
            "embed_model": EMBED_MODEL,
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "mode": args.mode,
            "top_k": args.top_k,
        })

        print("[1] 테스트셋 로드...")
        testset = load_testset()
        print(f"    {len(testset)}개 질문\n")

        print("[2] Retrieval + 평가 실행...")
        avg_scores, details = run_evaluation(testset, top_k=args.top_k, mode=args.mode)

        # MLflow 지표 기록
        mlflow.log_metrics(avg_scores)

        # 결과 저장
        result_data = {
            "embed_model": EMBED_MODEL,
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "mode": args.mode,
            "top_k": args.top_k,
            "scores": avg_scores,
        }

        result_path = output_dir / "results.json"
        detail_path = output_dir / "details.json"

        result_path.write_text(
            json.dumps(result_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        detail_path.write_text(
            json.dumps(details, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # MLflow artifact 저장
        mlflow.log_artifact(str(result_path))
        mlflow.log_artifact(str(detail_path))

        print(f"\n[결과] {EMBED_MODEL} / {chunk_strategy} / {args.mode} / top_{args.top_k}")
        for metric, score in avg_scores.items():
            print(f"  {metric}: {score}")
        print(f"\n[완료] 저장: {output_dir}/")
        print(f"[MLflow] mlflow ui 로 실험 비교 가능")


if __name__ == "__main__":
    main()
