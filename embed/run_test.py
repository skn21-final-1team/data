"""임베딩 테스트: chunking/output 결과물 → 임베딩 → embedding/output 저장.

주석을 풀어 사용할 전략(STRATEGY)과 모델(EMBEDDER)을 하나씩 선택하여 실행.

실행::

    uv run python -m embedding.run_test
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from tqdm import tqdm

from embedding.base import BaseEmbedder
from embedding.embedders import BgeM3Embedder, MultilingualE5Embedder

# ---------------------------------------------------------------------------
# 1) 청킹 전략 선택 (하나만 주석 해제)
# ---------------------------------------------------------------------------
# STRATEGY = "MD구분자_Markdown_1000c"
# STRATEGY = "재귀분할_Recursive_500c"
# STRATEGY = "토큰기반_Token_256tok"
# STRATEGY = "시맨틱_MiniLM_L6"
STRATEGY = "헤더기반_MarkdownHeader"
# STRATEGY = "계층적_Hierarchical_1000c"

# ---------------------------------------------------------------------------
# 2) 임베딩 모델 선택 (하나만 주석 해제)
# ---------------------------------------------------------------------------
EMBEDDER: BaseEmbedder = BgeM3Embedder()
# EMBEDDER: BaseEmbedder = MultilingualE5Embedder()

# ---------------------------------------------------------------------------
CHUNKING_OUTPUT = Path("chunking/output")
EMBEDDING_OUTPUT = Path("embedding/output")


def load_chunks(strategy: str) -> list[dict]:
    """chunking/output/{strategy}/ 에서 모든 청크를 로드한다."""
    strategy_dir = CHUNKING_OUTPUT / strategy
    if not strategy_dir.exists():
        raise FileNotFoundError(f"전략 디렉토리 없음: {strategy_dir}")

    chunks: list[dict] = []
    for json_path in sorted(strategy_dir.glob("notebook_*__chunks.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        chunks.extend(data["chunks"])
    return chunks


def main() -> None:
    model_name = EMBEDDER.name.replace("/", "_")
    print(f"[INFO] 전략: {STRATEGY}")
    print(f"[INFO] 모델: {EMBEDDER.name}")

    # 1. 청크 로드
    try:
        chunks = load_chunks(STRATEGY)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return

    if not chunks:
        print("[ERROR] 청크가 없습니다.")
        return
    print(f"[INFO] {len(chunks)}개 청크 로드")

    texts = [c["content"] for c in chunks]

    # 2. 임베딩 (Batch 처리 + tqdm)
    print("[INFO] 임베딩 시작...")
    start = time.perf_counter()

    vectors = []
    batch_size = EMBEDDER.config.batch_size

    # tqdm으로 진행률 표시
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding", unit="batch"):
        batch_texts = texts[i : i + batch_size]
        batch_vectors = EMBEDDER.embed(batch_texts, show_progress_bar=False)
        vectors.extend(batch_vectors)

    elapsed = time.perf_counter() - start
    print(
        f"[INFO] 완료 ({elapsed:.1f}s, {len(vectors)}개 벡터, {len(vectors) / elapsed:.1f} chunks/s)"
    )

    # 3. 결과 저장
    output_dir = EMBEDDING_OUTPUT / model_name / STRATEGY
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for chunk, vector in zip(chunks, vectors):
        results.append(
            {
                "source_id": chunk["source_id"],
                "chunk_index": chunk["index"],
                "url": chunk.get("url", ""),
                "text": chunk["content"],
                "vector": vector,
                "metadata": chunk.get("metadata", {}),
            }
        )

    (output_dir / "embeddings.json").write_text(
        json.dumps(
            {
                "model": EMBEDDER.name,
                "strategy": STRATEGY,
                "dimension": EMBEDDER.dimension,
                "count": len(results),
                "elapsed_seconds": round(elapsed, 2),
                "results": results,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 요약 정보 (벡터 제외)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "model": EMBEDDER.name,
                "strategy": STRATEGY,
                "dimension": EMBEDDER.dimension,
                "count": len(results),
                "elapsed_seconds": round(elapsed, 2),
                "chunks_per_second": round(len(results) / elapsed, 1),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[OK] 저장 완료: {output_dir}/")
    print(f"  - embeddings.json ({len(results)}개 벡터 포함)")
    print("  - summary.json (요약)")


if __name__ == "__main__":
    main()
