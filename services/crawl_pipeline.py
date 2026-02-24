import logging

import httpx

from core.config import get_settings
from crawl.client import ScrapeResult
from schemas.crawl import CrawlRequest
from schemas.embed import EmbeddingCallbackPayload

logger = logging.getLogger(__name__)


async def process_and_callback(
    scraped_list: list[ScrapeResult],
    request: CrawlRequest,
) -> None:
    for scraped in scraped_list:
        try:
            # TODO: chunk/ 모듈 구현 후 교체
            chunks = [scraped.content]

            # TODO: embed/ 모듈 구현 후 교체
            embeddings = [[0.0] * 768]

            payload = EmbeddingCallbackPayload(
                source_url=scraped.url,
                notebook_id=request.notebook_id,
                directory_id=request.directory_id,
                user_id=request.user_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            callback_url = get_settings().BACKEND_CALLBACK_URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    callback_url,
                    content=payload.model_dump_json(),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

        except Exception:
            logger.exception("콜백 전송 실패: %s", scraped.url)
