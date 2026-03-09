from __future__ import annotations

import re

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)

from chunk.base import BaseChunker
from chunk.config import ChunkerConfig, ChunkResult


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


# ---------------------------------------------------------------------------
# 헤더 경로 Prepend 유틸리티
# ---------------------------------------------------------------------------

def _build_header_path(metadata: dict[str, str]) -> str:
    """메타데이터에서 헤더 경로 문자열 생성. 예: [# A > ## B > ### C]"""
    parts: list[str] = []
    for key in ("Header 1", "Header 2", "Header 3"):
        if key in metadata:
            level = key.split()[-1]
            parts.append(f"{'#' * int(level)} {metadata[key]}")
    return f"[{' > '.join(parts)}] " if parts else ""


class MarkdownPrependChunker(BaseChunker):
    """S5-P: MarkdownChunker + 헤더 경로 Prepend."""

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
        self._text_splitter = MarkdownTextSplitter(
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
            splits = self._text_splitter.split_text(doc.page_content)
            for s in splits:
                results.append(ChunkResult(content=f"{prefix}{s}", index=idx, metadata=meta))
                idx += 1
        return results


class HierarchicalPrependChunker(BaseChunker):
    """S6-P: HierarchicalMarkdownChunker + 헤더 경로 Prepend."""

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


class ContextualChunker(BaseChunker):
    """S7: Contextual Retrieval — 각 chunk에 LLM이 생성한 맥락 요약을 prepend.

    OpenAI GPT-4o를 사용하여 각 청크의 맥락을 문서 전체 기준으로 요약합니다.
    """

    def __init__(self, config: ChunkerConfig, model: str = "gpt-4o") -> None:
        super().__init__(config)
        self._splitter = MarkdownTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        self._model = model

    def _generate_context(self, document: str, chunk: str) -> str:
        import httpx

        from core.config import get_settings

        settings = get_settings()
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": self._model,
                "temperature": 0,
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "<document>\n"
                            f"{document[:3000]}\n"
                            "</document>\n\n"
                            "Here is the chunk we want to situate within the whole document:\n"
                            "<chunk>\n"
                            f"{chunk}\n"
                            "</chunk>\n\n"
                            "Give a short succinct context (1-2 sentences, Korean) "
                            "to situate this chunk within the overall document. "
                            "Answer only the context, nothing else."
                        ),
                    }
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def chunk(self, text: str) -> list[ChunkResult]:
        splits: list[str] = self._splitter.split_text(text)
        results: list[ChunkResult] = []
        for i, s in enumerate(splits):
            context = self._generate_context(text, s)
            results.append(ChunkResult(content=f"[{context}] {s}", index=i))
        return results


class SentenceWindowChunker(BaseChunker):
    """S9: Sentence Window — 문장 단위 분할 + 주변 window_size 문장 확장."""

    def __init__(self, config: ChunkerConfig, window_size: int = 3) -> None:
        super().__init__(config)
        self._window_size = window_size

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        raw = re.split(r"(?<=[.!?。\n])\s+", text)
        return [s.strip() for s in raw if s.strip()]

    def chunk(self, text: str) -> list[ChunkResult]:
        sentences = self._split_sentences(text)
        if not sentences:
            return [ChunkResult(content=text, index=0)]

        results: list[ChunkResult] = []
        idx = 0
        i = 0
        while i < len(sentences):
            start = max(0, i - self._window_size)
            end = min(len(sentences), i + self._window_size + 1)
            window = " ".join(sentences[start:end])

            if len(window) > self.config.chunk_size and idx > 0:
                i += 1
                continue

            results.append(ChunkResult(
                content=window,
                index=idx,
                metadata={"center_sentence": str(i)},
            ))
            idx += 1
            i += max(1, self._window_size)

        return results
