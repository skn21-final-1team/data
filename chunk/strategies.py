from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from chunk.base import BaseChunker
from chunk.config import ChunkerConfig, ChunkResult


def _build_header_path(metadata: dict[str, str]) -> str:
    """메타데이터에서 헤더 경로 문자열 생성. 예: [# A > ## B > ### C]"""
    parts: list[str] = []
    for key in ("Header 1", "Header 2", "Header 3"):
        if key in metadata:
            level = key.split()[-1]
            parts.append(f"{'#' * int(level)} {metadata[key]}")
    return f"[{' > '.join(parts)}] " if parts else ""


class HierarchicalPrependChunker(BaseChunker):
    """헤더 분할 → RecursiveCharacter 재분할 → 헤더 경로 Prepend."""

    DEFAULT_HEADERS: list[tuple[str, str]] = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    def __init__(self, config: ChunkerConfig) -> None:
        super().__init__(config)
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.DEFAULT_HEADERS,
        )
        self._recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        header_docs = self._header_splitter.split_text(text)
        results: list[ChunkResult] = []
        idx = 0
        for doc in header_docs:
            meta = {k: str(v) for k, v in doc.metadata.items()}
            prefix = _build_header_path(meta)
            if len(doc.page_content) <= self.config.chunk_size:
                results.append(
                    ChunkResult(content=f"{prefix}{doc.page_content}", index=idx, metadata=meta)
                )
                idx += 1
            else:
                for sub in self._recursive_splitter.split_text(doc.page_content):
                    results.append(ChunkResult(content=f"{prefix}{sub}", index=idx, metadata=meta))
                    idx += 1
        return results
