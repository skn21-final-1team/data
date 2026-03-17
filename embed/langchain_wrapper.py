"""LangChain Embeddings 어댑터 — RunPod Serverless API."""

from __future__ import annotations

import asyncio

from langchain_core.embeddings import Embeddings

from embed.service import embed_texts


def _run_async(coro):
    """이벤트 루프 유무에 관계없이 코루틴 실행."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # 이미 이벤트 루프가 실행 중이면 새 스레드에서 실행
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class LangChainEmbeddingsWrapper(Embeddings):

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _run_async(embed_texts(texts))

    def embed_query(self, text: str) -> list[float]:
        return _run_async(embed_texts([text]))[0]
