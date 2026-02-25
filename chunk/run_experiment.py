from __future__ import annotations

from pathlib import Path

from chunk.config import ChunkerConfig
from chunk.pipeline import ChunkingPipeline
from chunk.preprocess import MarkdownPreprocessor
from chunk.strategies import (
    HierarchicalMarkdownChunker,
    MarkdownChunker,
    MarkdownHeaderChunker,
    RecursiveChunker,
    SemanticChunker,
    TokenChunker,
)

CHUNKERS = [
    RecursiveChunker(
        ChunkerConfig("재귀분할_Recursive_500c", chunk_size=500, chunk_overlap=50),
    ),
    TokenChunker(
        ChunkerConfig("토큰기반_Token_256tok", chunk_size=256, chunk_overlap=30),
    ),
    SemanticChunker(
        ChunkerConfig("시맨틱_MiniLM_L6", chunk_size=0, chunk_overlap=0),
        model_name="all-MiniLM-L6-v2",
        breakpoint_threshold_type="percentile",
    ),
    MarkdownHeaderChunker(
        ChunkerConfig("헤더기반_MarkdownHeader", chunk_size=0, chunk_overlap=0),
    ),
    MarkdownChunker(
        ChunkerConfig("MD구분자_Markdown_1000c", chunk_size=1000, chunk_overlap=100),
    ),
    HierarchicalMarkdownChunker(
        ChunkerConfig("계층적_Hierarchical_1000c", chunk_size=1000, chunk_overlap=100),
    ),
]

OUTPUT_DIR = Path("chunk/output")


def main() -> None:
    """실험 파이프라인을 실행한다."""
    print("[INFO] DB(source 테이블)에서 데이터 로드 중...")
    sources = ChunkingPipeline.load_from_db()
    if not sources:
        print("[ERROR] DB에 활성 문서가 없습니다.")
        print("  백엔드에서 크롤링을 먼저 실행하세요.")
        return

    print(f"[INFO] {len(sources)}개 문서 로드 완료")
    for s in sources:
        print(f"  - {s.source_id} ({len(s.content):,}자)")

    print(f"\n[INFO] {len(CHUNKERS)}개 전략으로 청킹 실행 중...")
    pipeline = ChunkingPipeline(
        sources,
        CHUNKERS,
        output_dir=OUTPUT_DIR,
        preprocessor=MarkdownPreprocessor.run,
    )
    results = pipeline.run()

    original_texts = {s.source_id: s.content for s in sources}
    output_path = pipeline.save_results(results, original_texts, output_root=OUTPUT_DIR)

    print(f"\n[OK] 결과 저장 완료: {output_path}/")
    print("  - comparison.csv      (전략 간 평균 비교)")
    print("  - total_analysis.md   (전략 분석)")
    print("  - {전략명}/notebook_{id}__chunks.json  (notebook 단위 청크)")
    print("  - {전략명}/eval.json                   (전략별 평가)")


if __name__ == "__main__":
    main()
