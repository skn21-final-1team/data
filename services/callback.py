import asyncio
import json
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


async def send_callback(url: str, body: str) -> None:
    """콜백 전송 (exponential backoff 재시도, 최대 3회)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    content=body,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
            return
        except Exception:
            if attempt == MAX_RETRIES:
                logger.exception("콜백 전송 최종 실패 (%d/%d): %s", attempt, MAX_RETRIES, url)
                raise
            delay = RETRY_BASE_DELAY ** attempt
            logger.warning("콜백 전송 실패 (%d/%d), %ds 후 재시도: %s", attempt, MAX_RETRIES, delay, url)
            await asyncio.sleep(delay)


async def send_error_callback(
    url: str, source_url: str, notebook_id: int, directory_id: int, error: str,
) -> None:
    """파이프라인 실패 시 에러 상태를 백엔드에 전달."""
    payload = json.dumps({
        "source_url": source_url,
        "notebook_id": notebook_id,
        "directory_id": directory_id,
        "status": "error",
        "message": error,
    })
    try:
        await send_callback(url, payload)
    except Exception:
        logger.exception("에러 콜백 전송 실패: %s", source_url)
