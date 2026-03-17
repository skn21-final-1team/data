import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from chunk.service import chunk_text_only
from crawl.client import hybrid_client
from crawl.preprocess import MarkdownPreprocessor
from crud.page_data import bulk_create_page_data, delete_page_data_by_source
from crud.source import get_source_by_id, update_source_status
from db.database import get_db_context
from embed.service import embed_texts
from llm.client import refine, summarize
from llm.config import get_llm_settings
from services.callback import send_callback

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _detect_stage(exc: Exception) -> str:
    """예외 정보로 실패 단계 추정."""
    msg = str(exc).lower()
    if "refine" in msg or "정제" in msg:
        return "refine"
    if "summar" in msg or "요약" in msg:
        return "summarize"
    return "embed"


def _process_content(source_id: int, raw_content: str) -> int:
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

        refined_text = refine(preprocessed)
        with get_db_context() as db:
            update_source_status(db, source_id, refined=refined_text)

        summary_text = summarize(refined_text)
        with get_db_context() as db:
            update_source_status(db, source_id, summary=summary_text)

        # ── 콜백 1: summary 완료 → Frontend 표시 가능 ──
        send_callback(source_id, "summary_completed")

    # 재시도 시 기존 page_data 삭제 (중복 적재 방지)
    deleted = delete_page_data_by_source(source_id)
    if deleted:
        logger.info("재시도: source_id=%d 기존 page_data %d건 삭제", source_id, deleted)

    chunk_results = chunk_text_only(refined_text)
    chunks = [c.content for c in chunk_results]

    embeddings = embed_texts(chunks)

    bulk_create_page_data(
        source_id=source_id,
        chunks=chunks,
        embeddings=embeddings,
    )

    # ── 콜백 2: 임베딩 완료 → 질문 검색 가능 ──
    send_callback(source_id, "embed_completed")

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


# ── Phase 2: LLM + 임베딩 (병렬) ────────────────────────────────


def _process_single_content(source_id: int, raw_content: str) -> tuple[int, int]:
    """단일 source 처리 (스레드에서 실행). 반환: (source_id, chunk_count)."""
    count = _process_content(source_id, raw_content)
    return source_id, count


def _run_parallel_processing(crawled: list[tuple[int, str]]) -> int:
    """크롤링 완료된 건들을 ThreadPoolExecutor로 병렬 처리. 실패 시 순번 밀기 재시도."""
    success = 0
    queue = [(sid, content, 0) for sid, content in crawled]

    while queue:
        batch = queue[:]
        queue.clear()

        with ThreadPoolExecutor(max_workers=get_llm_settings().MAX_WORKERS) as pool:
            futures = {
                pool.submit(_process_single_content, sid, content): (
                    sid,
                    content,
                    attempt,
                )
                for sid, content, attempt in batch
            }
            for future in as_completed(futures):
                sid, content, attempt = futures[future]
                try:
                    source_id, count = future.result()
                    print(f"[적재 완료] source_id={source_id}  {count}개 청크 적재")
                    success += 1
                except Exception as exc:
                    logger.exception(
                        "처리 실패: source_id=%d (attempt %d)", sid, attempt + 1
                    )
                    if attempt + 1 < MAX_RETRIES:
                        print(
                            f"[재시도 예정] source_id={sid}"
                            f"  → 순번 밀기 ({attempt + 2}/{MAX_RETRIES})"
                        )
                        send_callback(sid, "retrying", error=str(exc))
                        queue.append((sid, content, attempt + 1))
                    else:
                        print(
                            f"[최종 실패] source_id={sid}"
                            f"  → {type(exc).__name__}: {exc}"
                        )
                        send_callback(
                            sid,
                            "failed",
                            stage=_detect_stage(exc),
                            error=str(exc),
                        )
                        with get_db_context() as db:
                            update_source_status(db, sid, status="failed")

    return success


# ── 파이프라인 진입점 ────────────────────────────────────────────


async def process_pipeline(source_map: dict[str, int]) -> None:
    """Phase 1: 크롤링(순차) → Phase 2: LLM+임베딩(병렬)."""
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

    # Phase 2 — LLM 정제/요약 + 임베딩 (RunPod worker 병렬 활용)
    success = await asyncio.to_thread(_run_parallel_processing, crawled)

    print(f"[파이프라인 완료] 적재 {success}/{len(crawled)}건")
