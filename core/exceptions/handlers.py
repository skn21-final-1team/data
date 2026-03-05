import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.exceptions.crawl import CrawlFailedException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CrawlFailedException)
    async def crawl_failed_handler(
        request: Request, exc: CrawlFailedException
    ) -> JSONResponse:
        print(f"[CrawlFailed] {request.method} {request.url.path} → {exc}")
        return JSONResponse(
            status_code=422,
            content={"detail": f"크롤링 실패: {exc}"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = " → ".join(str(l) for l in err["loc"])
            errors.append({"field": loc, "message": err["msg"]})
        print(f"[ValidationError] {request.method} {request.url.path} → {errors}")
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        print(f"[UnhandledError] {request.method} {request.url.path} → {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {type(exc).__name__}"},
        )
