from fastapi import APIRouter, BackgroundTasks

from crud.source import create_source
from crawl.client import ScrapeResult, hybrid_client
from db.database import DbSession
from schemas.crawl import CrawlRequest, CrawlResult
from services.crawl_pipeline import process_and_callback

router = APIRouter()


@router.post("/crawl")
async def crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> list[CrawlResult]:
    scraped_list: list[ScrapeResult] = []
    source_ids: dict[str, int] = {}
    results: list[CrawlResult] = []

    for url in request.urls:
        scraped = await hybrid_client.scrape(str(url))
        scraped_list.append(scraped)

        source = create_source(
            db=db,
            url=scraped.url,
            title=scraped.title,
            summary=scraped.content,
            notebook_id=request.notebook_id,
            directory_id=request.directory_id,
        )
        source_ids[scraped.url] = source.id

        results.append(
            CrawlResult(
                url=scraped.url,
                title=scraped.title,
                summary=scraped.content,
                notebook_id=request.notebook_id,
                directory_id=request.directory_id,
            )
        )

    background_tasks.add_task(process_and_callback, scraped_list, request, source_ids)

    return results
