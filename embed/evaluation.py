"""임베딩 벡터 품질 평가.

output/ 에 저장된 임베딩 벡터를 로드하여 평가한다.
벡터 자체의 품질(분포, 등방성, 클러스터링, 중복)만 측정하며,
retrieval 성능 평가는 retriever/ 에서 별도 수행한다.

실행::

    uv run python -m embedding.evaluation
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from sklearn.metrics import silhouette_score
from umap import UMAP

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------------------
# 평가 대상 (모델, 전략) — 주석을 풀어 선택
# ---------------------------------------------------------------------------
TARGETS: list[tuple[str, str]] = [
    ("BAAI_bge-m3", "MD구분자_Markdown_1000c"),
    ("BAAI_bge-m3", "재귀분할_Recursive_500c"),
    ("intfloat_multilingual-e5-large", "MD구분자_Markdown_1000c"),
    ("intfloat_multilingual-e5-large", "재귀분할_Recursive_500c"),
    ("BAAI_bge-m3", "토큰기반_Token_256tok"),
    ("BAAI_bge-m3", "시맨틱_MiniLM_L6"),
    # ("BAAI_bge-m3", "헤더기반_MarkdownHeader"),
    # ("BAAI_bge-m3", "계층적_Hierarchical_1000c"),
    ("intfloat_multilingual-e5-large", "토큰기반_Token_256tok"),
    ("intfloat_multilingual-e5-large", "시맨틱_MiniLM_L6"),
    # ("intfloat_multilingual-e5-large", "헤더기반_MarkdownHeader"),
    # ("intfloat_multilingual-e5-large", "계층적_Hierarchical_1000c"),
]

DUPLICATE_THRESHOLD = 0.95
EMBEDDING_OUTPUT = Path("embedding/output")


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------
def load_embeddings(
    model: str,
    strategy: str,
) -> tuple[np.ndarray, list[str], list[str]]:
    """embeddings.json에서 벡터, source_id, 텍스트를 로드한다."""
    path = EMBEDDING_OUTPUT / model / strategy / "embeddings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data["results"]
    vectors = np.array([r["vector"] for r in results])
    source_ids = [r["source_id"] for r in results]
    texts = [r["text"] for r in results]
    return vectors, source_ids, texts


# ---------------------------------------------------------------------------
# 1. UMAP 시각화
# ---------------------------------------------------------------------------
def visualize_umap(
    vectors: np.ndarray,
    source_ids: list[str],
    output_path: Path,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
) -> None:
    """UMAP 2D 산점도를 PNG로 저장한다."""
    reducer = UMAP(n_neighbors=n_neighbors, min_dist=min_dist, random_state=42)
    coords = reducer.fit_transform(vectors)

    unique_sources = sorted(set(source_ids))
    cmap = matplotlib.colormaps.get_cmap("tab20").resampled(len(unique_sources))
    color_map = {src: cmap(i) for i, src in enumerate(unique_sources)}
    colors = [color_map[s] for s in source_ids]

    plt.figure(figsize=(12, 8))
    plt.scatter(coords[:, 0], coords[:, 1], c=colors, s=8, alpha=0.7)
    plt.title(f"UMAP — {output_path.parent.name}")
    plt.xlabel("UMAP-1")
    plt.ylabel("UMAP-2")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


# ---------------------------------------------------------------------------
# 2. 분포 분석 (코사인 유사도 분포 + Isotropy)
# ---------------------------------------------------------------------------
def analyze_distribution(vectors: np.ndarray) -> dict[str, float]:
    """코사인 유사도 분포와 등방성을 계산한다."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / (norms + 1e-9)

    # 코사인 유사도 (상삼각 행렬만)
    sim_matrix = normalized @ normalized.T
    triu_indices = np.triu_indices(len(vectors), k=1)
    pairwise_sims = sim_matrix[triu_indices]

    # Isotropy: 특이값 균일도 (1.0에 가까울수록 등방적)
    _, singular_values, _ = np.linalg.svd(normalized, full_matrices=False)
    sv_normalized = singular_values / singular_values.sum()
    isotropy = float(np.exp(-np.sum(sv_normalized * np.log(sv_normalized + 1e-9))))

    return {
        "cosine_mean": round(float(pairwise_sims.mean()), 4),
        "cosine_std": round(float(pairwise_sims.std()), 4),
        "cosine_min": round(float(pairwise_sims.min()), 4),
        "cosine_max": round(float(pairwise_sims.max()), 4),
        "isotropy": round(isotropy, 4),
    }


# ---------------------------------------------------------------------------
# 3. 클러스터링 분석 (Silhouette Score, source_id 기준)
# ---------------------------------------------------------------------------
def analyze_clustering(
    vectors: np.ndarray,
    source_ids: list[str],
) -> dict[str, float]:
    """source_id를 라벨로 Silhouette Score를 계산한다."""
    unique_labels = set(source_ids)
    if len(unique_labels) < 2:
        return {"silhouette_score": 0.0, "n_clusters": len(unique_labels)}

    labels = [sorted(unique_labels).index(s) for s in source_ids]
    score = silhouette_score(vectors, labels, metric="cosine")

    return {
        "silhouette_score": round(float(score), 4),
        "n_clusters": len(unique_labels),
    }


# ---------------------------------------------------------------------------
# 4. 중복 검출
# ---------------------------------------------------------------------------
def detect_duplicates(
    vectors: np.ndarray,
    texts: list[str],
    threshold: float = DUPLICATE_THRESHOLD,
) -> dict:
    """코사인 유사도 threshold 이상인 near-duplicate 쌍을 검출한다."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / (norms + 1e-9)
    sim_matrix = normalized @ normalized.T

    duplicates: list[dict] = []
    n = len(vectors)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= threshold:
                duplicates.append(
                    {
                        "pair": (i, j),
                        "similarity": round(float(sim_matrix[i][j]), 4),
                        "text_i": texts[i][:100],
                        "text_j": texts[j][:100],
                    }
                )

    return {
        "threshold": threshold,
        "total_chunks": n,
        "duplicate_pairs": len(duplicates),
        "duplicate_ratio": round(len(duplicates) / max(n * (n - 1) / 2, 1), 4),
        "top_duplicates": sorted(
            duplicates, key=lambda x: x["similarity"], reverse=True
        )[:20],
    }


# ---------------------------------------------------------------------------
# 분석 리포트 생성
# ---------------------------------------------------------------------------
def generate_analysis(all_results: dict[str, dict]) -> str:
    """total_analysis.md 내용을 생성한다."""
    lines: list[str] = []
    lines.append("# 임베딩 벡터 품질 분석 요약\n")
    lines.append("> 벡터 자체의 분포·등방성·클러스터링·중복도만 평가합니다.")
    lines.append("> Retrieval 성능 평가는 retriever/ 에서 별도 수행합니다.\n")

    # 비교 테이블
    lines.append("## 분포 & 등방성\n")
    lines.append("| 모델 × 전략 | cos 평균 | cos std | Isotropy |")
    lines.append("|---|---|---|---|")
    for key, r in all_results.items():
        d = r["distribution"]
        lines.append(
            f"| {key} | {d['cosine_mean']} | {d['cosine_std']} | {d['isotropy']} |"
        )
    lines.append("")

    lines.append("## 클러스터링 (Silhouette, source_id 기준)\n")
    lines.append("| 모델 × 전략 | Silhouette | 클러스터 수 |")
    lines.append("|---|---|---|")
    for key, r in all_results.items():
        c = r["clustering"]
        lines.append(f"| {key} | {c['silhouette_score']} | {c['n_clusters']} |")
    lines.append("")

    lines.append("## 중복 검출\n")
    lines.append("| 모델 × 전략 | threshold | 중복 쌍 | 중복 비율 |")
    lines.append("|---|---|---|---|")
    for key, r in all_results.items():
        dup = r["duplicates"]
        lines.append(
            f"| {key} | {dup['threshold']} | "
            f"{dup['duplicate_pairs']}/{dup['total_chunks']} | {dup['duplicate_ratio']} |"
        )
    lines.append("")

    # 해석 가이드
    lines.append("## 해석 가이드\n")
    lines.append("- **cos 평균**: 낮을수록 벡터 간 변별력 높음 (0.3~0.5 권장)")
    lines.append("- **cos std**: 높을수록 유사도 분포가 넓음 (변별력 있음)")
    lines.append(
        "- **Isotropy**: 차원 수에 가까울수록 벡터 공간을 고르게 활용 (exp(entropy), 최대=dim)"
    )
    lines.append("- **Silhouette**: 1.0에 가까울수록 같은 source 청크끼리 잘 뭉침")
    lines.append("- **중복 비율**: 낮을수록 좋음 (높으면 DB 저장 전 제거 필요)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    all_results: dict[str, dict] = {}

    for model, strategy in TARGETS:
        key = f"{model} / {strategy}"
        print(f"[INFO] 평가 중: {key}")

        vectors, source_ids, texts = load_embeddings(model, strategy)
        output_dir = EMBEDDING_OUTPUT / model / strategy
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. UMAP
        print("  - UMAP 시각화...")
        visualize_umap(vectors, source_ids, output_dir / "umap.png")

        # 2. 분포
        print("  - 분포 분석...")
        dist = analyze_distribution(vectors)

        # 3. 클러스터링
        print("  - 클러스터링 분석...")
        clust = analyze_clustering(vectors, source_ids)

        # 4. 중복
        print("  - 중복 검출...")
        dup = detect_duplicates(vectors, texts)

        # 개별 결과 저장
        eval_result = {
            "model": model,
            "strategy": strategy,
            "distribution": dist,
            "clustering": clust,
            "duplicates": dup,
        }
        (output_dir / "eval.json").write_text(
            json.dumps(eval_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        all_results[key] = eval_result
        print(f"  [OK] 저장: {output_dir}/eval.json, umap.png")

    # total_analysis.md
    analysis = generate_analysis(all_results)
    (EMBEDDING_OUTPUT / "total_analysis.md").write_text(analysis, encoding="utf-8")
    print(f"\n[OK] {EMBEDDING_OUTPUT}/total_analysis.md 저장 완료")


if __name__ == "__main__":
    main()
