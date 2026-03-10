import asyncio
import logging

from chunk.service import chunk_text_only
from crawl.client import hybrid_client
from crawl.preprocess import MarkdownPreprocessor
from crud.page_data import bulk_create_page_data
from crud.source import update_source_status
from db.database import get_db_context
from embed.service import embed_texts
from llm.client import refine, summarize

logger = logging.getLogger(__name__)


def _process_content(source_id: int, raw_content: str) -> int:
    """전처리 → vLLM 정제 → vLLM 요약 → 청킹 → 임베딩 → PGVector 적재. 저장된 건수 반환."""
    preprocessed = MarkdownPreprocessor.run(raw_content)

    refined_text = refine(preprocessed)
    with get_db_context() as db:
        update_source_status(db, source_id, refined=refined_text)

    summary_text = summarize(refined_text)
    with get_db_context() as db:
        update_source_status(db, source_id, summary=summary_text)

    chunk_results = chunk_text_only(refined_text)
    chunks = [c.content for c in chunk_results]

    embeddings = embed_texts(chunks)

    bulk_create_page_data(
        source_id=source_id,
        chunks=chunks,
        embeddings=embeddings,
    )

    return len(chunks)


async def _process_single(url: str, source_id: int) -> bool:
    """단일 URL: 크롤링 → raw 저장 → vLLM 정제/요약 → 청킹·임베딩·적재."""
    try:
        scraped = await hybrid_client.scrape(url)
    except Exception as exc:
        logger.exception("크롤링 실패: %s", url)
        print(
            f"[크롤링 실패] source_id={source_id}  {url}  → {type(exc).__name__}: {exc}"
        )
        with get_db_context() as db:
            update_source_status(db, source_id, status="failed")
        return False

    with get_db_context() as db:
        update_source_status(
            db,
            source_id,
            status="success",
            title=scraped.title,
            raw=scraped.content,
        )
    print(f"[크롤링 성공] source_id={source_id}  {url}")

    try:
        count = await asyncio.to_thread(_process_content, source_id, scraped.content)
        print(f"[적재 완료] source_id={source_id}  {count}개 청크 적재")
    except Exception as exc:
        logger.exception("처리 실패: %s", url)
        print(
            f"[처리 실패] source_id={source_id}  {url}  → {type(exc).__name__}: {exc}"
        )

    return True


async def process_pipeline(source_map: dict[str, int]) -> None:
    """백그라운드: URL별 독립 처리 (하나 실패해도 나머지 계속 진행)."""
    print(f"\n[파이프라인 시작] {len(source_map)}개 URL 처리")

    success = 0
    for url, source_id in source_map.items():
        if await _process_single(url, source_id):
            success += 1

    print(f"[파이프라인 완료] 성공 {success}/{len(source_map)}건")
