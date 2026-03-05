from pydantic import BaseModel, Field, HttpUrl


class CrawlRequest(BaseModel):
    urls: list[HttpUrl] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="크롤링할 URL 목록",
        examples=[["https://example.com"]],
    )
    notebook_id: int = Field(..., description="노트북 ID")
    directory_id: int | None = Field(default=None, description="디렉토리 ID")


class CrawlAccepted(BaseModel):
    """즉시 응답: URL 접수 완료."""
    source_id: int = Field(..., description="생성된 source ID")
    url: str = Field(..., description="접수된 URL")


class CrawlResponse(BaseModel):
    """POST /crawl 응답."""
    status: str = Field(default="accepted", description="접수 상태")
    count: int = Field(..., description="접수된 URL 수")
    sources: list[CrawlAccepted] = Field(..., description="생성된 source 목록")
