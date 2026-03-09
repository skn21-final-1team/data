"""임베딩 서비스 — RunPod Serverless Native API 호출."""

from __future__ import annotations

import httpx

from core.config import get_settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """텍스트 리스트를 임베딩 벡터로 변환 (RunPod /runsync)."""
    settings = get_settings()

    response = httpx.post(
        f"{settings.EMBED_BASE_URL}/runsync",
        headers={"Authorization": f"Bearer {settings.RUNPOD_API_KEY}"},
        json={
            "input": {
                "openai_route": "/v1/embeddings",
                "openai_input": {
                    "model": settings.EMBED_MODEL,
                    "input": texts,
                },
            }
        },
        timeout=120,
    )
    response.raise_for_status()

    output = response.json().get("output", [])
    data = output[0].get("data", []) if output else []
    return [item["embedding"] for item in data]
