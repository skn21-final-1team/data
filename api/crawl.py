from fastapi import APIRouter, BackgroundTasks

from crud.source import create_source
from db.database import DbSession
from schemas.crawl import CrawlAccepted, CrawlRequest, CrawlResponse
from services.crawl_pipeline import process_pipeline

router = APIRouter()


@router.post("/crawl")
def crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> CrawlResponse:
    """URL 접수 → 즉시 응답. 크롤링·청킹·임베딩은 백그라운드에서 처리."""
    sources: list[CrawlAccepted] = []

    for url in request.urls:
        source = create_source(
            db=db,
            url=str(url),
            notebook_id=request.notebook_id,
            directory_id=request.directory_id,
        )
        sources.append(CrawlAccepted(source_id=source.id, url=str(url)))

    source_map = {s.url: s.source_id for s in sources}
    background_tasks.add_task(process_pipeline, source_map)

    return CrawlResponse(count=len(sources), sources=sources)
