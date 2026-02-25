from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)

from chunk.base import BaseChunker
from chunk.config import ChunkerConfig, ChunkResult

# ---------------------------------------------------------------------------
# 실험용 전략 (Markdown 입력 기준, 아래 순서로 실험 진행):
#   1. RecursiveChunker       - 재귀적 문자 분할 (베이스라인)
#   2. TokenChunker           - 토큰 기반 분할 (tiktoken)
#   3. SemanticChunker        - 의미적 청킹 (임베딩 유사도 기반)
#   4. MarkdownHeaderChunker  - 헤더 기반 구조 분할
#   5. MarkdownChunker        - MD 구분자 기반 Recursive
#   6. HierarchicalMarkdownChunker - 1차 헤더 분할 → 2차 RecursiveCharacter 재분할
# ---------------------------------------------------------------------------


class RecursiveChunker(BaseChunker):
    def __init__(self, config: ChunkerConfig) -> None:
        super().__init__(config)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        splits: list[str] = self._splitter.split_text(text)
        return [ChunkResult(content=s, index=i) for i, s in enumerate(splits)]


class TokenChunker(BaseChunker):
    def __init__(
        self,
        config: ChunkerConfig,
        encoding_name: str = "cl100k_base",
    ) -> None:
        super().__init__(config)
        self._splitter = TokenTextSplitter(
            encoding_name=encoding_name,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        splits: list[str] = self._splitter.split_text(text)
        return [ChunkResult(content=s, index=i) for i, s in enumerate(splits)]


class SemanticChunker(BaseChunker):
    def __init__(
        self,
        config: ChunkerConfig,
        model_name: str = "all-MiniLM-L6-v2",
        breakpoint_threshold_type: str = "percentile",
    ) -> None:
        super().__init__(config)
        from langchain_experimental.text_splitter import (
            SemanticChunker as LCSemanticChunker,
        )
        from langchain_huggingface import HuggingFaceEmbeddings

        self._embeddings = HuggingFaceEmbeddings(model_name=model_name)
        self._splitter = LCSemanticChunker(
            embeddings=self._embeddings,
            breakpoint_threshold_type=breakpoint_threshold_type,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        docs = self._splitter.create_documents([text])
        return [
            ChunkResult(content=doc.page_content, index=i) for i, doc in enumerate(docs)
        ]


class MarkdownHeaderChunker(BaseChunker):
    DEFAULT_HEADERS: list[tuple[str, str]] = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    def __init__(
        self,
        config: ChunkerConfig,
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(config)
        headers = headers_to_split_on or self.DEFAULT_HEADERS
        self._splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        docs = self._splitter.split_text(text)
        return [
            ChunkResult(
                content=doc.page_content,
                index=i,
                metadata={k: str(v) for k, v in doc.metadata.items()},
            )
            for i, doc in enumerate(docs)
        ]


class HierarchicalMarkdownChunker(BaseChunker):
    """1차 헤더 분할 → 2차 RecursiveCharacter 재분할."""

    DEFAULT_HEADERS: list[tuple[str, str]] = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    def __init__(
        self,
        config: ChunkerConfig,
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(config)
        headers = headers_to_split_on or self.DEFAULT_HEADERS
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers,
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
            if len(doc.page_content) <= self.config.chunk_size:
                results.append(
                    ChunkResult(content=doc.page_content, index=idx, metadata=meta)
                )
                idx += 1
            else:
                for sub in self._recursive_splitter.split_text(doc.page_content):
                    results.append(ChunkResult(content=sub, index=idx, metadata=meta))
                    idx += 1
        return results


class MarkdownChunker(BaseChunker):
    def __init__(self, config: ChunkerConfig) -> None:
        super().__init__(config)
        self._splitter = MarkdownTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def chunk(self, text: str) -> list[ChunkResult]:
        splits: list[str] = self._splitter.split_text(text)
        return [ChunkResult(content=s, index=i) for i, s in enumerate(splits)]
