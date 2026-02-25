from __future__ import annotations

from chunk.config import ChunkResult
from embed.base import BaseEmbedder
from embed.config import DEFAULT_MODEL, EmbeddingResult
from embed.embedders import BgeM3Embedder, MultilingualE5Embedder

_EMBEDDER_MAP: dict[str, type[BaseEmbedder]] = {
    "BAAI/bge-m3": BgeM3Embedder,
    "intfloat/multilingual-e5-large": MultilingualE5Embedder,
}


def _get_embedder() -> BaseEmbedder:
    cls = _EMBEDDER_MAP.get(DEFAULT_MODEL)
    if cls is None:
        raise ValueError(f"지원하지 않는 임베딩 모델: {DEFAULT_MODEL}")
    return cls()


_embedder = _get_embedder()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _embedder.embed(texts, show_progress_bar=False)


def embed_chunks(
    chunks: dict[str, list[ChunkResult]],
) -> list[EmbeddingResult]:
    all_texts: list[str] = []
    index_map: list[tuple[str, int, str, dict[str, str]]] = []

    for source_id, chunk_list in chunks.items():
        for chunk in chunk_list:
            all_texts.append(chunk.content)
            index_map.append((source_id, chunk.index, chunk.content, chunk.metadata))

    vectors = _embedder.embed(all_texts)

    return [
        EmbeddingResult(
            source_id=src_id,
            chunk_index=idx,
            vector=vec,
            text=text,
            metadata=meta,
        )
        for (src_id, idx, text, meta), vec in zip(index_map, vectors)
    ]
