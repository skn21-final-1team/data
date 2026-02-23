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
    user_id: int = Field(..., description="사용자 ID")


class CrawlResult(BaseModel):
    url: str = Field(..., description="크롤링한 URL")
    title: str | None = Field(default=None, description="페이지 제목")
    summary: str | None = Field(default=None, description="추출된 본문 텍스트")
    notebook_id: int = Field(..., description="노트북 ID")
    directory_id: int | None = Field(default=None, description="디렉토리 ID")
    user_id: int = Field(..., description="사용자 ID")
    is_active: bool = Field(default=False, description="활성화 여부")
