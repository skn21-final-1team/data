import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.exceptions.base import CustomException
from core.exceptions.crawl import (
    ContentTooShortError,
    CrawlFailedError,
    GarbageContentError,
    RobotsBlockedError,
    ScrapeFetchError,
)
from core.exceptions.db import (
    PageDataSaveError,
    RefinedSaveError,
    SourceSaveError,
    SummarySaveError,
)
from core.exceptions.embed import (
    EmbedConnectionError,
    EmbedError,
)
from core.exceptions.pipeline import PipelineStageError
from core.exceptions.vllm import (
    RefineError,
    SummarizeError,
    VLLMColdStartError,
    VLLMConnectionError,
)

logger = logging.getLogger(__name__)


def custom_base_handler(_: Request, exc: CustomException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.code,
        content={"error": type(exc).__name__, "message": exc.message, "code": exc.code},
    )


def pipeline_stage_handler(_: Request, exc: PipelineStageError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.code,
        content={
            "error": type(exc).__name__,
            "stage": exc.stage,
            "message": exc.message,
            "code": exc.code,
        },
    )


def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    messages = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=422,
        content={"error": "ValidationError", "message": "; ".join(messages), "code": 422},
    )


def global_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "message": f"서버 내부 오류가 발생했습니다: {exc}",
            "code": 500,
        },
    )


def init_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_handler)
    # crawl
    app.add_exception_handler(RobotsBlockedError, custom_base_handler)
    app.add_exception_handler(ContentTooShortError, custom_base_handler)
    app.add_exception_handler(GarbageContentError, custom_base_handler)
    app.add_exception_handler(ScrapeFetchError, custom_base_handler)
    app.add_exception_handler(CrawlFailedError, custom_base_handler)
    # pipeline — vLLM
    app.add_exception_handler(RefineError, pipeline_stage_handler)
    app.add_exception_handler(SummarizeError, pipeline_stage_handler)
    app.add_exception_handler(VLLMConnectionError, pipeline_stage_handler)
    app.add_exception_handler(VLLMColdStartError, pipeline_stage_handler)
    # pipeline — embed
    app.add_exception_handler(EmbedError, pipeline_stage_handler)
    app.add_exception_handler(EmbedConnectionError, pipeline_stage_handler)
    # pipeline — db
    app.add_exception_handler(RefinedSaveError, pipeline_stage_handler)
    app.add_exception_handler(SummarySaveError, pipeline_stage_handler)
    app.add_exception_handler(SourceSaveError, pipeline_stage_handler)
    app.add_exception_handler(PageDataSaveError, pipeline_stage_handler)
    # base
    app.add_exception_handler(PipelineStageError, pipeline_stage_handler)
    app.add_exception_handler(CustomException, custom_base_handler)
    app.add_exception_handler(Exception, global_handler)
