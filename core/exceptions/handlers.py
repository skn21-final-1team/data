from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions.crawl import CrawlFailedException


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CrawlFailedException)
    async def crawl_failed_handler(
        request: Request, exc: CrawlFailedException
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
