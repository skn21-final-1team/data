import asyncio
import logging

from chunk.service import chunk_text
from core.config import get_settings
from crud.page_data import bulk_create_page_data
from db.database import get_db_context
from embed.service import embed_texts
from crawl.client import ScrapeResult
from schemas.crawl import CrawlRequest
from schemas.embed import EmbeddingCallbackPayload
from services.callback import send_callback, send_error_callback

logger = logging.getLogger(__name__)


def _process_sync(content: str, source_id: int) -> tuple[list[str], list[list[float]]]:
    """청킹 + 임베딩 + DB 적재 (동기, 스레드에서 실행)."""
    chunk_results = chunk_text(content)
    chunks = [c.content for c in chunk_results]

    embeddings = embed_texts(chunks)

    with get_db_context() as db:
        bulk_create_page_data(
            db=db,
            source_id=source_id,
            chunks=chunks,
            embeddings=embeddings,
        )

    return chunks, embeddings


async def process_and_callback(
    scraped_list: list[ScrapeResult],
    request: CrawlRequest,
    source_ids: dict[str, int],
) -> None:
    callback_url = get_settings().BACKEND_CALLBACK_URL

    for scraped in scraped_list:
        try:
            source_id = source_ids[scraped.url]

            chunks, embeddings = await asyncio.to_thread(
                _process_sync,
                scraped.content,
                source_id,
            )
            logger.info("page_data 적재 완료: %s (%d건)", scraped.url, len(chunks))

            payload = EmbeddingCallbackPayload(
                source_url=scraped.url,
                notebook_id=request.notebook_id,
                directory_id=request.directory_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            await send_callback(callback_url, payload.model_dump_json())

        except Exception as exc:
            logger.exception("파이프라인 처리 실패: %s", scraped.url)
            await send_error_callback(
                callback_url, scraped.url,
                request.notebook_id, request.directory_id,
                str(exc),
            )
