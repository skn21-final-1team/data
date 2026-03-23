import asyncio
import logging

from chunk.service import chunk_text_only
from crawl.client import hybrid_client
from crawl.preprocess import MarkdownPreprocessor
from crud.page_data import bulk_create_page_data, delete_page_data_by_source
from crud.source import get_source_by_id, update_source_status
from db.database import get_db_context
from core.config import get_settings
from core.exceptions import (
    EmbedError,
    PageDataSaveError,
    PipelineStageError,
    RefineError,
    RefinedSaveError,
    SummarizeError,
    SummarySaveError,
)
from embed.service import embed_texts
from llm.client import refine, summarize
from llm.config import get_llm_settings
from services.callback import send_callback

logger = logging.getLogger(__name__)


async def _process_content(source_id: int, raw_content: str) -> int:
    """전처리 → vLLM 정제 → vLLM 요약 → 청킹 → 임베딩 → PGVector 적재. 저장된 건수 반환."""

    # 재시도 시 이미 완료된 단계 건너뛰기 (DB 상태 확인)
    with get_db_context() as db:
        source = get_source_by_id(db, source_id)
        has_summary = source and source.summary and source.refined

    if has_summary:
        refined_text = source.refined
        logger.info("재시도: source_id=%d summary 이미 존재 → embed부터 실행", source_id)
    else:
        preprocessed = MarkdownPreprocessor.run(raw_content)

        try:
            refined_text = await refine(preprocessed)
        except PipelineStageError:
            raise
        except Exception as e:
            raise RefineError(str(e)) from e
        try:
            with get_db_context() as db:
                update_source_status(db, source_id, refined=refined_text)
        except Exception as e:
            raise RefinedSaveError(f"refined 저장 실패: {e}") from e

        try:
            summary_text = await summarize(refined_text)
        except PipelineStageError:
            raise
        except Exception as e:
            raise SummarizeError(str(e)) from e
        try:
            with get_db_context() as db:
                update_source_status(db, source_id, summary=summary_text)
        except Exception as e:
            raise SummarySaveError(f"summary 저장 실패: {e}") from e

        # ── 콜백 1: summary 완료 → Frontend 표시 가능 ──
        await send_callback(source_id, "summary_completed")

    # 재시도 시 기존 page_data 삭제 (중복 적재 방지)
    try:
        deleted = delete_page_data_by_source(source_id)
        if deleted:
            logger.info("재시도: source_id=%d 기존 page_data %d건 삭제", source_id, deleted)
    except Exception as e:
        raise PageDataSaveError(f"기존 page_data 삭제 실패: {e}") from e

    chunk_results = chunk_text_only(refined_text)
    chunks = [c.content for c in chunk_results]

    try:
        embeddings = await embed_texts(chunks)
    except PipelineStageError:
        raise
    except Exception as e:
        raise EmbedError(str(e)) from e

    try:
        bulk_create_page_data(
            source_id=source_id,
            chunks=chunks,
            embeddings=embeddings,
        )
    except Exception as e:
        raise PageDataSaveError(f"PGVector 적재 실패: {e}") from e

    # ── 콜백 2: 임베딩 완료 → 질문 검색 가능 ──
    await send_callback(source_id, "embed_completed")

    return len(chunks)


# ── Phase 1: 크롤링 (순차) ──────────────────────────────────────


async def _crawl_single(url: str, source_id: int) -> tuple[int, str] | None:
    """단일 URL 크롤링 → raw 저장. 성공 시 (source_id, raw_content) 반환."""
    try:
        scraped = await hybrid_client.scrape(url)
    except Exception as exc:
        logger.exception("크롤링 실패: %s", url)
        print(
            f"[크롤링 실패] source_id={source_id}  {url}  → {type(exc).__name__}: {exc}"
        )
        with get_db_context() as db:
            update_source_status(db, source_id, status="failed")
        await send_callback(
            source_id, "failed",
            stage="crawl",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return None

    with get_db_context() as db:
        update_source_status(
            db,
            source_id,
            status="success",
            title=scraped.title,
            raw=scraped.content,
        )
    print(f"[크롤링 성공] source_id={source_id}  {url}")
    return source_id, scraped.content


# ── Phase 2: LLM + 임베딩 (asyncio 병렬) ─────────────────────────


async def _run_parallel_processing(crawled: list[tuple[int, str]]) -> int:
    """크롤링 완료된 건들을 asyncio.gather + Semaphore로 병렬 처리. 실패 시 순번 밀기 재시도."""
    sem = asyncio.Semaphore(get_settings().MAX_WORKERS)
    max_retries = get_llm_settings().MAX_RETRIES
    success = 0
    queue = [(sid, content, 0) for sid, content in crawled]

    while queue:
        batch = queue[:]
        queue.clear()

        async def _guarded(sid: int, content: str) -> tuple[int, int]:
            async with sem:
                count = await _process_content(sid, content)
                return sid, count

        tasks = [_guarded(sid, content) for sid, content, _ in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (sid, content, attempt), result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error(
                    "처리 실패: source_id=%d (attempt %d)",
                    sid,
                    attempt + 1,
                    exc_info=result,
                )
                stage = result.stage if isinstance(result, PipelineStageError) else "unknown"
                error_type = type(result).__name__
                if attempt + 1 < max_retries:
                    print(
                        f"[재시도 예정] source_id={sid}"
                        f"  → 순번 밀기 ({attempt + 2}/{max_retries})"
                    )
                    await send_callback(
                        sid, "retrying",
                        stage=stage,
                        error_type=error_type, error=str(result),
                    )
                    queue.append((sid, content, attempt + 1))
                else:
                    print(
                        f"[최종 실패] source_id={sid}"
                        f"  → {error_type}: {result}"
                    )
                    await send_callback(
                        sid, "failed",
                        stage=stage,
                        error_type=error_type, error=str(result),
                    )
                    with get_db_context() as db:
                        update_source_status(db, sid, status="failed")
            else:
                source_id, count = result
                print(f"[적재 완료] source_id={source_id}  {count}개 청크 적재")
                success += 1

    return success


# ── 파이프라인 진입점 ────────────────────────────────────────────


async def process_pipelines_parallel(source_maps: list[dict[str, int]]) -> None:
    """소스 별 process_pipeline을 asyncio.gather로 병렬 실행."""
    await asyncio.gather(*(process_pipeline(sm) for sm in source_maps))


async def process_pipeline(source_map: dict[str, int]) -> None:
    """Phase 1: 크롤링(순차) → Phase 2: LLM+임베딩(asyncio 병렬)."""
    total = len(source_map)
    print(f"\n[파이프라인 시작] {total}개 URL 처리")

    # Phase 1 — 크롤링 (외부 사이트 부하 방지를 위해 순차)
    crawled: list[tuple[int, str]] = []
    for url, source_id in source_map.items():
        result = await _crawl_single(url, source_id)
        if result is not None:
            crawled.append(result)

    print(f"[크롤링 완료] {len(crawled)}/{total}건 성공")

    if not crawled:
        print("[파이프라인 종료] 크롤링 성공 건 없음")
        return

    # Phase 2 — LLM 정제/요약 + 임베딩 (asyncio 병렬)
    success = await _run_parallel_processing(crawled)

    print(f"[파이프라인 완료] 적재 {success}/{len(crawled)}건")
