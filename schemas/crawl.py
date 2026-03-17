from pydantic import BaseModel, Field, HttpUrl


class CrawlSourceItem(BaseModel):
    source_id: int
    url: HttpUrl


class CrawlRequest(BaseModel):
    sources: list[CrawlSourceItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="크롤링할 source 목록 (Backend에서 생성된 레코드)",
    )


class CrawlResponse(BaseModel):
    status: str = "accepted"
    accepted: list[int] = Field(default_factory=list, description="접수된 source_id 목록")
    not_found: list[int] = Field(default_factory=list, description="존재하지 않는 source_id 목록")
