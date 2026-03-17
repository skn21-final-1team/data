from __future__ import annotations

from chunk.config import ChunkerConfig, ChunkResult
from chunk.strategies import HierarchicalPrependChunker

CHUNKER = HierarchicalPrependChunker(
    ChunkerConfig("markdown_1000c", chunk_size=1000, chunk_overlap=100),
)


def chunk_text_only(text: str) -> list[ChunkResult]:
    """전처리 없이 청킹만 수행한다. (이미 전처리된 텍스트용)"""
    return CHUNKER.chunk(text)
