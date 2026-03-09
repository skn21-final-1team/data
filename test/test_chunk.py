"""청킹 전략 비교 평가 → comparison.csv + total_analysis.md 산출 (독립 실행).

입력: test/output/refined.json (test_vllm 산출물) 또는 DB summary
출력: test/output_analysis/chunk/comparison.csv, total_analysis.md
      test/output/chunks.json (test_embed 입력용)

사용법::

    # 기본 실행 (S8 Late Chunking 제외 전체 전략)
    uv run python -m test.test_chunk

    # DB summary 기반 (vLLM 미사용 시)
    uv run python -m test.test_chunk --from-db

    # 특정 전략만
    uv run python -m test.test_chunk --strategies markdown recursive contextual

    # 청크 크기/오버랩 변경
    uv run python -m test.test_chunk --chunk_size 500 --chunk_overlap 50

전략 목록:
    S1  recursive          RecursiveCharacterTextSplitter
    S2  token              TokenTextSplitter (tiktoken)
    S3  semantic           SemanticChunker (임베딩 유사도 기반)
    S4  markdown_header    MarkdownHeaderTextSplitter
    S5  markdown           MarkdownTextSplitter (현재 서비스)
    S6  hierarchical       MarkdownHeader → Recursive 재분할
    S5P markdown_prepend   S5 + 헤더 경로 Prepend
    S6P hierarchical_prepend  S6 + 헤더 경로 Prepend
    S7  contextual         Contextual Retrieval (GPT-4o, OPENAI_API_KEY 필요)
    S9  sentence_window    문장 단위 분할 + 주변 문장 확장
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path

from chunk.config import ChunkerConfig, ChunkResult
from chunk.strategies import (
    ContextualChunker,
    HierarchicalMarkdownChunker,
    HierarchicalPrependChunker,
    MarkdownChunker,
    MarkdownHeaderChunker,
    MarkdownPrependChunker,
    RecursiveChunker,
    SemanticChunker,
    SentenceWindowChunker,
    TokenChunker,
)

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = Path(__file__).parent / "output"
REFINED_PATH = OUTPUT_DIR / "refined.json"
CHUNKS_PATH = OUTPUT_DIR / "chunks.json"
ANALYSIS_DIR = Path(__file__).parent / "output_analysis" / "chunk"

STRATEGY_MAP: dict[str, type] = {
    "recursive": RecursiveChunker,
    "token": TokenChunker,
    "semantic": SemanticChunker,
    "markdown_header": MarkdownHeaderChunker,
    "markdown": MarkdownChunker,
    "hierarchical": HierarchicalMarkdownChunker,
    "markdown_prepend": MarkdownPrependChunker,
    "hierarchical_prepend": HierarchicalPrependChunker,
    "contextual": ContextualChunker,
    "sentence_window": SentenceWindowChunker,
}

STRATEGY_LABELS: dict[str, str] = {
    "recursive": "S1_재귀분할_Recursive",
    "token": "S2_토큰기반_Token",
    "semantic": "S3_시맨틱_Semantic",
    "markdown_header": "S4_헤더기반_MarkdownHeader",
    "markdown": "S5_MD구분자_Markdown",
    "hierarchical": "S6_계층적_Hierarchical",
    "markdown_prepend": "S5P_MD구분자_Prepend",
    "hierarchical_prepend": "S6P_계층적_Prepend",
    "contextual": "S7_Contextual_Retrieval",
    "sentence_window": "S9_SentenceWindow",
}

# size/overlap 무시 전략 (자동 분할)
NO_SIZE_STRATEGIES = {"semantic", "markdown_header"}


# ---------------------------------------------------------------------------
# 평가 지표 계산
# ---------------------------------------------------------------------------


def _paragraph_preservation(chunks: list[str]) -> float:
    intact = 0
    total = 0
    for chunk in chunks:
        paragraphs = [p.strip() for p in chunk.split("\n\n") if p.strip()]
        total += max(len(paragraphs), 1)
        for p in paragraphs:
            if not p.startswith("...") and not p.endswith("..."):
                intact += 1
    return intact / total if total else 0.0


def _sentence_integrity(chunks: list[str]) -> float:
    if not chunks:
        return 0.0
    clean_boundaries = 0
    for chunk in chunks:
        text = chunk.strip()
        if text and re.search(r"[.!?。\n#\-\|`\]]$", text):
            clean_boundaries += 1
    return clean_boundaries / len(chunks)


def _whitespace_preservation(chunks: list[str], original: str) -> float:
    orig_blanks = original.count("\n\n")
    if orig_blanks == 0:
        return 1.0
    chunk_blanks = sum(c.count("\n\n") for c in chunks)
    return min(chunk_blanks / orig_blanks, 1.0)


def _list_preservation(chunks: list[str]) -> float:
    total_items = 0
    intact_items = 0
    for chunk in chunks:
        lines = chunk.split("\n")
        in_list = False
        for line in lines:
            if re.match(r"^\s*[-*+]\s|^\s*\d+\.\s", line):
                total_items += 1
                intact_items += 1
                in_list = True
            elif in_list and line.strip() == "":
                in_list = False
    return intact_items / total_items if total_items else 1.0


def _heading_preservation(chunks: list[str]) -> float:
    total_headings = 0
    start_headings = 0
    for chunk in chunks:
        lines = chunk.strip().split("\n")
        for j, line in enumerate(lines):
            if re.match(r"^#{1,6}\s", line):
                total_headings += 1
                if j == 0:
                    start_headings += 1
    return start_headings / total_headings if total_headings else 1.0


def _coverage(chunks: list[str], original: str) -> float:
    total_len = sum(len(c) for c in chunks)
    orig_len = len(original)
    return total_len / orig_len if orig_len else 0.0


def _boundary_quality(chunks: list[str]) -> float:
    if len(chunks) <= 1:
        return 1.0
    good = 0
    for chunk in chunks:
        text = chunk.strip()
        ends_clean = bool(re.search(r"\n\n$|[.!?。]$|\n```$|\n---$", text))
        starts_clean = bool(re.match(r"^#{1,6}\s|^\s*[-*+]\s|^\s*\d+\.\s|^```|\[", text))
        if ends_clean or starts_clean:
            good += 1
    return good / len(chunks)


def evaluate_chunks(
    chunks: list[str], original: str, elapsed: float
) -> dict[str, float]:
    char_lengths = [len(c) for c in chunks]
    avg_chars = statistics.mean(char_lengths) if char_lengths else 0.0
    std_chars = statistics.stdev(char_lengths) if len(char_lengths) > 1 else 0.0

    return {
        "chunks": len(chunks),
        "avg_chars": round(avg_chars, 4),
        "std_chars": round(std_chars, 4),
        "paragraph": round(_paragraph_preservation(chunks), 4),
        "sentence": round(_sentence_integrity(chunks), 4),
        "whitespace": round(_whitespace_preservation(chunks, original), 4),
        "list": round(_list_preservation(chunks), 4),
        "heading": round(_heading_preservation(chunks), 4),
        "coverage": round(_coverage(chunks, original), 4),
        "boundary": round(_boundary_quality(chunks), 4),
        "time_s": round(elapsed, 4),
    }


# ---------------------------------------------------------------------------
# 분석 리포트 생성
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "strategy", "doc_count", "chunks", "avg_chars", "std_chars",
    "paragraph", "sentence", "whitespace", "list", "heading",
    "coverage", "boundary", "time_s",
]


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis_md(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    best: dict[str, tuple[str, float]] = {}
    metrics = ["paragraph", "sentence", "whitespace", "list", "heading"]
    for row in rows:
        name = str(row["strategy"])
        for m in metrics:
            val = float(row[m])
            if m not in best or val > best[m][1]:
                best[m] = (name, val)

    coverage_best = min(rows, key=lambda r: abs(float(r["coverage"]) - 1.0))
    boundary_best = max(rows, key=lambda r: float(r["boundary"]))
    std_best = min(rows, key=lambda r: float(r["std_chars"]))

    def score(row: dict[str, object]) -> float:
        struct = statistics.mean(float(row[m]) for m in metrics)
        cov = 1.0 - abs(float(row["coverage"]) - 1.0)
        bnd = float(row["boundary"])
        return struct * 0.4 + cov * 0.3 + bnd * 0.3

    ranked = sorted(rows, key=score, reverse=True)

    lines = [
        "# 청킹 전략 분석 요약",
        "",
        "## 1. 구조 보존 관점 (높을수록 좋음)",
        "",
    ]
    labels = {
        "paragraph": "단락 보존",
        "sentence": "문장 무결성",
        "whitespace": "공백 구조 보존",
        "list": "리스트 보존",
        "heading": "헤더 보존",
    }
    for m in metrics:
        name, val = best[m]
        lines.append(f"- **{labels[m]}**: {name} ({val:.1%})")

    lines += [
        "",
        "## 2. 커버리지 관점 (1.0에 가까울수록 좋음)",
        "",
        f"- **최적 커버리지**: {coverage_best['strategy']} ({float(coverage_best['coverage']):.1%})",
    ]

    lines += [
        "",
        "## 3. 경계 품질 관점 (높을수록 좋음)",
        "",
        f"- **최적 경계**: {boundary_best['strategy']} ({float(boundary_best['boundary']):.1%})",
    ]

    lines += [
        "",
        "## 4. 청크 크기 균일성 (std_chars 낮을수록 좋음)",
        "",
        f"- **가장 균일**: {std_best['strategy']} (std={float(std_best['std_chars']):.1f})",
    ]

    lines += ["", "## 5. 종합 추천", ""]
    for i, row in enumerate(ranked, 1):
        struct = statistics.mean(float(row[m]) for m in metrics)
        cov = float(row["coverage"])
        bnd = float(row["boundary"])
        rec = " <-- 추천" if i == 1 else ""
        lines.append(
            f"{i}. **{row['strategy']}** "
            f"(구조={struct:.1%} 커버리지={cov:.1%} 경계={bnd:.1%}){rec}"
        )

    lines += [
        "",
        "---",
        "",
        "*이 분석은 구조 보존 + 경계 품질 + 커버리지 근접도를 기반으로 산출되었습니다. "
        "최종 판단은 임베딩 후 retrieval 성능으로 결정하세요.*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def load_texts_from_refined() -> dict[str, str]:
    if not REFINED_PATH.exists():
        print(f"[오류] {REFINED_PATH} 파일이 없습니다. test_vllm을 먼저 실행하세요.")
        sys.exit(1)
    data: dict[str, str] = json.loads(REFINED_PATH.read_text(encoding="utf-8"))
    print(f"[입력] refined.json에서 {len(data)}개 문서 로드")
    return data


def load_texts_from_db() -> dict[str, str]:
    from crud.source import get_sources_with_summary
    from db.database import get_db_context

    with get_db_context() as db:
        sources = get_sources_with_summary(db)
        data = {str(s.id): s.summary for s in sources}
    print(f"[입력] DB에서 {len(data)}개 문서 로드")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="청킹 전략 비교 평가")
    parser.add_argument(
        "--strategies", nargs="+", choices=STRATEGY_MAP.keys(),
        default=list(STRATEGY_MAP.keys()), help="평가할 전략 목록",
    )
    parser.add_argument("--chunk_size", type=int, default=1000, help="청크 크기 (기본: 1000)")
    parser.add_argument("--chunk_overlap", type=int, default=100, help="청크 오버랩 (기본: 100)")
    parser.add_argument("--from-db", action="store_true", help="DB summary 기반 (refined.json 대신)")
    parser.add_argument("--best", default="markdown", help="chunks.json에 저장할 전략 (기본: markdown)")
    args = parser.parse_args()

    texts = load_texts_from_db() if args.from_db else load_texts_from_refined()
    if not texts:
        print("[오류] 처리할 문서가 없습니다.")
        sys.exit(1)

    csv_rows: list[dict[str, object]] = []
    all_source_chunks: dict[str, dict[str, list[str]]] = {}

    for strategy_name in args.strategies:
        label = STRATEGY_LABELS.get(strategy_name, strategy_name)
        suffix = f"_{args.chunk_size}c" if strategy_name not in NO_SIZE_STRATEGIES else ""
        display_name = f"{label}{suffix}"

        config = ChunkerConfig(
            strategy_name=strategy_name,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        chunker = STRATEGY_MAP[strategy_name](config)

        all_chunks: list[str] = []
        all_original = ""
        total_time = 0.0
        source_chunks: dict[str, list[str]] = {}

        print(f"\n[청킹] {display_name}")
        for source_id, text in texts.items():
            t0 = time.time()
            results: list[ChunkResult] = chunker.chunk(text)
            total_time += time.time() - t0

            chunks = [r.content for r in results]
            all_chunks.extend(chunks)
            all_original += text
            source_chunks[source_id] = chunks

        metrics = evaluate_chunks(all_chunks, all_original, total_time)
        avg_per_doc = metrics["chunks"] / len(texts) if texts else 0
        metrics["chunks"] = round(avg_per_doc, 4)
        time_per_doc = total_time / len(texts) if texts else 0

        row: dict[str, object] = {"strategy": display_name, "doc_count": len(texts)}
        row.update(metrics)
        row["time_s"] = round(time_per_doc, 4)
        csv_rows.append(row)

        all_source_chunks[strategy_name] = source_chunks

        print(f"  문서: {len(texts)}개 | 평균 청크: {avg_per_doc:.1f}개 | 평균 {metrics['avg_chars']:.0f}자")
        print(f"  구조: 단락={metrics['paragraph']:.1%} 문장={metrics['sentence']:.1%} 경계={metrics['boundary']:.1%}")
        print(f"  커버리지: {metrics['coverage']:.1%} | 시간: {total_time:.2f}초")

    # CSV 저장
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = ANALYSIS_DIR / "comparison.csv"
    write_csv(csv_rows, csv_path)
    print(f"\n[저장] {csv_path}")

    # 분석 MD 저장
    md_path = ANALYSIS_DIR / "total_analysis.md"
    write_analysis_md(csv_rows, md_path)
    print(f"[저장] {md_path}")

    # --best 전략의 청크를 chunks.json으로 저장 (test_embed 입력용)
    best_key = args.best if args.best in all_source_chunks else list(all_source_chunks.keys())[0]
    best_chunks = all_source_chunks[best_key]
    OUTPUT_DIR.mkdir(exist_ok=True)
    CHUNKS_PATH.write_text(
        json.dumps(best_chunks, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"[저장] {CHUNKS_PATH} (전략={best_key}, {sum(len(v) for v in best_chunks.values())}개 청크)")


if __name__ == "__main__":
    main()
