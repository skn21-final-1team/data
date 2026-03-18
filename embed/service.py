"""임베딩 서비스 — RunPod Serverless /run + polling (async)."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from core.config import get_settings
from core.exceptions import EmbedConnectionError
from embed.config import get_embed_settings

logger = logging.getLogger(__name__)


async def _run_and_poll(base_url: str, api_key: str, payload: dict) -> dict:
    """RunPod /run 후 /status 폴링으로 결과 수신."""
    cfg = get_embed_settings()
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/run", headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            job_id = resp.json()["id"]

            deadline = time.time() + cfg.POLL_TIMEOUT
            while time.time() < deadline:
                st = await client.get(
                    f"{base_url}/status/{job_id}", headers=headers, timeout=30
                )
                st.raise_for_status()
                data = st.json()

                if data["status"] == "COMPLETED":
                    return data
                if data["status"] == "FAILED":
                    raise EmbedConnectionError(f"RunPod embed job failed: {data}")

                await asyncio.sleep(cfg.POLL_INTERVAL)

        raise EmbedConnectionError(
            f"RunPod embed job {job_id} timed out after {cfg.POLL_TIMEOUT}s"
        )
    except EmbedConnectionError:
        raise
    except Exception as e:
        raise EmbedConnectionError(f"임베딩 서버 연결 실패: {e}") from e


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """텍스트 리스트를 임베딩 벡터로 변환 (RunPod /run + polling)."""
    settings = get_settings()
    cfg = get_embed_settings()

    payload = {
        "input": {
            "openai_route": "/v1/embeddings",
            "openai_input": {
                "model": settings.EMBED_MODEL,
                "input": texts,
            },
        }
    }

    last_exc: Exception | None = None
    result: dict = {}
    for attempt in range(1, cfg.COLD_START_RETRIES + 1):
        try:
            result = await _run_and_poll(
                base_url=settings.EMBED_BASE_URL,
                api_key=settings.RUNPOD_API_KEY,
                payload=payload,
            )
            break
        except EmbedConnectionError as e:
            last_exc = e
            if attempt < cfg.COLD_START_RETRIES:
                logger.warning(
                    "임베딩 콜드스타트 실패 (시도 %d/%d), %.0f초 후 재시도: %s",
                    attempt,
                    cfg.COLD_START_RETRIES,
                    cfg.COLD_START_DELAY,
                    e,
                )
                await asyncio.sleep(cfg.COLD_START_DELAY)
    else:
        raise EmbedConnectionError(
            f"임베딩 콜드스타트 재시도 횟수를 초과했습니다: {last_exc}"
        ) from last_exc

    output = result.get("output", [])
    data = output[0].get("data", []) if output else []
    return [item["embedding"] for item in data]
