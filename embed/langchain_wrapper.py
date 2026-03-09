"""LangChain Embeddings 어댑터 — RunPod Serverless API."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from embed.service import embed_texts


class LangChainEmbeddingsWrapper(Embeddings):

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed_texts([text])[0]
