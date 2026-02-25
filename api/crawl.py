from fastapi import APIRouter, BackgroundTasks

from crawl.client import ScrapeResult, hybrid_client
from schemas.crawl import CrawlRequest, CrawlResult
from services.crawl_pipeline import process_and_callback

router = APIRouter()


@router.post("/crawl")
async def crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
) -> list[CrawlResult]:
    scraped_list: list[ScrapeResult] = []
    results: list[CrawlResult] = []

    for url in request.urls:
        scraped = await hybrid_client.scrape(str(url))
        scraped_list.append(scraped)
        results.append(
            CrawlResult(
                url=scraped.url,
                title=scraped.title,
                summary=scraped.content,
                notebook_id=request.notebook_id,
                directory_id=request.directory_id,
            )
        )

    background_tasks.add_task(process_and_callback, scraped_list, request)

    return results
