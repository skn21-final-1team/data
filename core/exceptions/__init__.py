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

__all__ = [
    "CustomException",
    # crawl
    "CrawlFailedError",
    "RobotsBlockedError",
    "ContentTooShortError",
    "GarbageContentError",
    "ScrapeFetchError",
    # pipeline base
    "PipelineStageError",
    # vLLM
    "RefineError",
    "SummarizeError",
    "VLLMConnectionError",
    "VLLMColdStartError",
    # embed
    "EmbedError",
    "EmbedConnectionError",
    # db
    "SourceSaveError",
    "RefinedSaveError",
    "SummarySaveError",
    "PageDataSaveError",
]
