"""PGVector store 팩토리."""

from __future__ import annotations

from langchain_postgres.vectorstores import PGVector

from core.config import get_settings
from embed.langchain_wrapper import LangChainEmbeddingsWrapper

_stores: dict[str, PGVector] = {}


def get_vector_store(collection_name: str = "page_data") -> PGVector:
    """PGVector store 싱글톤 반환."""
    if collection_name not in _stores:
        _stores[collection_name] = PGVector(
            embeddings=LangChainEmbeddingsWrapper(),
            collection_name=collection_name,
            connection=get_settings().DATABASE_URL,
            use_jsonb=True,
            create_extension=False,
        )
    return _stores[collection_name]
