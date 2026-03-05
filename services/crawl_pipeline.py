import asyncio
import logging

from chunk.service import chunk_text
from crawl.client import hybrid_client
from crud.page_data import bulk_create_page_data
from crud.source import update_source_status
from db.database import get_db_context
from embed.service import embed_texts

logger = logging.getLogger(__name__)


def _chunk_embed_store(source_id: int, content: str) -> int:
    """청킹 → 임베딩 → page_data 적재. 저장된 건수 반환."""
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

    return len(chunks)


async def _process_single(url: str, source_id: int) -> bool:
    """단일 URL: 크롤링 → source 업데이트 → 청킹·임베딩·적재. 실패해도 다른 URL에 영향 없음."""
    # 1) 크롤링
    try:
        scraped = await hybrid_client.scrape(url)
    except Exception as exc:
        logger.exception("크롤링 실패: %s", url)
        print(f"[크롤링 실패] source_id={source_id}  {url}  → {type(exc).__name__}: {exc}")
        with get_db_context() as db:
            update_source_status(db, source_id, status="failed")
        return False

    # 2) source 업데이트 (크롤링 성공 시점에 확정)
    with get_db_context() as db:
        update_source_status(
            db, source_id, status="success",
            title=scraped.title, summary=scraped.content,
        )
    print(f"[크롤링 성공] source_id={source_id}  {url}")

    # 3) 청킹 → 임베딩 → page_data 적재 (실패해도 source status는 유지)
    try:
        count = await asyncio.to_thread(_chunk_embed_store, source_id, scraped.content)
        print(f"[임베딩 완료] source_id={source_id}  {count}개 청크 적재")
    except Exception as exc:
        logger.exception("임베딩 실패: %s", url)
        print(f"[임베딩 실패] source_id={source_id}  {url}  → {type(exc).__name__}: {exc}")

    return True


async def process_pipeline(source_map: dict[str, int]) -> None:
    """백그라운드: URL별 독립 처리 (하나 실패해도 나머지 계속 진행)."""
    print(f"\n[파이프라인 시작] {len(source_map)}개 URL 처리")

    success = 0
    for url, source_id in source_map.items():
        if await _process_single(url, source_id):
            success += 1

    print(f"[파이프라인 완료] 성공 {success}/{len(source_map)}건")
