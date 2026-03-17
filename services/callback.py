import logging

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)


async def send_callback(source_id: int, event: str, **data) -> None:
    """Backend에 콜백 전송. 실패해도 파이프라인은 계속 진행."""
    url = get_settings().BACKEND_CALLBACK_URL
    if not url:
        return
    payload = {"source_id": source_id, "event": event, **data}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception:
        logger.warning("콜백 전송 실패: source_id=%d event=%s", source_id, event)
