from fastapi import APIRouter, BackgroundTasks

from crud.source import get_source_by_id
from db.database import DbSession
from schemas.crawl import CrawlRequest, CrawlResponse, CrawlSyncRequest
from services.crawl_pipeline import process_pipeline

router = APIRouter()


@router.post("/crawl")
def crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CrawlResponse:
    """URL 접수 → 즉시 응답. 크롤링·청킹·임베딩은 백그라운드에서 처리."""
    source_map: dict[str, int] = {}
    not_found: list[int] = []

    for item in request.sources:
        source = get_source_by_id(db, item.source_id)
        if source is None:
            not_found.append(item.source_id)
            continue
        source_map[str(item.url)] = item.source_id

    if source_map:
        background_tasks.add_task(process_pipeline, source_map)

    return CrawlResponse(
        accepted=list(source_map.values()),
        not_found=not_found,
    )


@router.post("/crawl/sync")
def crawl_sync(
    request: CrawlSyncRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CrawlResponse:
    """북마크 동기화 크롤링 접수. 크롤링·청킹·임베딩은 백그라운드에서 처리."""
    source_map: dict[str, int] = {}
    not_found: list[int] = []

    for item in request.sources:
        source = get_source_by_id(db, item.source_id)
        if source is None:
            not_found.append(item.source_id)
            continue
        source_map[str(item.url)] = item.source_id

    if source_map:
        background_tasks.add_task(process_pipeline, source_map)

    return CrawlResponse(
        accepted=list(source_map.values()),
        not_found=not_found,
    )
