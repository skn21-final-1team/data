from fastapi import APIRouter, HTTPException

from core.exceptions.crawl import CrawlFailedException
from crawl.client import hybrid_client
from schemas.crawl import CrawlRequest, CrawlResult

router = APIRouter()


@router.post("/crawl")
async def crawl(request: CrawlRequest) -> list[CrawlResult]:
    try:
        results: list[CrawlResult] = []
        for url in request.urls:
            scraped = await hybrid_client.scrape(str(url))
            results.append(
                CrawlResult(
                    url=scraped.url,
                    title=scraped.title,
                    summary=scraped.content,
                    notebook_id=request.notebook_id,
                    directory_id=request.directory_id,
                    user_id=request.user_id,
                )
            )
        return results
    except CrawlFailedException as e:
        raise HTTPException(status_code=502, detail=str(e))
