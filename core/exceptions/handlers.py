import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.exceptions.crawl import CrawlFailedException

logger = logging.getLogger(__name__)


def _log(tag: str, request: Request, exc: Exception) -> None:
    """공통 로그 출력."""
    body_hint = ""
    if hasattr(request, "_body"):
        raw = request._body[:500] if len(request._body) > 500 else request._body
        body_hint = f"\n  요청 body: {raw.decode('utf-8', errors='replace')}"
    print(
        f"\n{'=' * 60}\n"
        f"[{tag}] {request.method} {request.url}\n"
        f"  클라이언트: {request.client.host if request.client else 'unknown'}\n"
        f"  예외 타입 : {type(exc).__name__}\n"
        f"  메시지    : {exc}"
        f"{body_hint}\n"
        f"{'=' * 60}"
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CrawlFailedException)
    async def crawl_failed_handler(
        request: Request, exc: CrawlFailedException
    ) -> JSONResponse:
        _log("CrawlFailed", request, exc)
        traceback.print_exc()
        return JSONResponse(
            status_code=422,
            content={
                "error": "CrawlFailed",
                "detail": f"크롤링 실패: {exc}",
                "hint": "URL이 유효한지, robots.txt에 차단되지 않았는지 확인하세요.",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = " → ".join(str(part) for part in err["loc"])
            errors.append({"field": loc, "message": err["msg"], "type": err["type"]})
        _log("ValidationError", request, exc)
        print(f"  필드별 오류: {errors}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "detail": "요청 형식이 올바르지 않습니다.",
                "fields": errors,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        _log("UnhandledError", request, exc)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "detail": f"서버 내부 오류가 발생했습니다: {exc}",
                "hint": "Data 서버 로그를 확인하세요.",
            },
        )
