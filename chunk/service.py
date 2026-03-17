from __future__ import annotations

from chunk.config import ChunkerConfig, ChunkResult, TextSource
from chunk.strategies import HierarchicalPrependChunker
from crawl.preprocess import MarkdownPreprocessor

CHUNKER = HierarchicalPrependChunker(
    ChunkerConfig("markdown_1000c", chunk_size=1000, chunk_overlap=100),
)


def chunk_sources(sources: list[TextSource]) -> dict[str, list[ChunkResult]]:
    """source 목록을 전처리 → 청킹하여 source_id별 청크를 반환한다."""
    results: dict[str, list[ChunkResult]] = {}
    for source in sources:
        text = MarkdownPreprocessor.run(source.content)
        results[source.source_id] = CHUNKER.chunk(text)
    return results


def chunk_text(text: str) -> list[ChunkResult]:
    """단일 텍스트를 전처리 → 청킹한다."""
    return CHUNKER.chunk(MarkdownPreprocessor.run(text))


def chunk_text_only(text: str) -> list[ChunkResult]:
    """전처리 없이 청킹만 수행한다. (이미 전처리된 텍스트용)"""
    return CHUNKER.chunk(text)
