"""BaseEmbedder → LangChain Embeddings 어댑터."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from embed.service import _embedder


class LangChainEmbeddingsWrapper(Embeddings):

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _embedder.embed(texts, show_progress_bar=False)

    def embed_query(self, text: str) -> list[float]:
        return _embedder.embed([text], show_progress_bar=False)[0]
