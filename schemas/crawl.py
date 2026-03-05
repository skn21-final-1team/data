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
