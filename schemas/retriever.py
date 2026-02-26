from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="검색 쿼리 텍스트",
        examples=["FastAPI에서 의존성 주입을 사용하는 방법"],
    )
    notebook_id: int = Field(..., description="검색 범위 노트북 ID")
    top_k: int = Field(default=5, ge=1, le=20, description="반환할 최대 결과 수")


class RetrieveChunk(BaseModel):
    id: int = Field(..., description="page_data 레코드 ID")
    chunk_text: str = Field(..., description="검색된 청크 텍스트")
    similarity: float = Field(..., description="코사인 유사도 (0~1)")
    source_id: int = Field(..., description="출처 source ID")
    source_url: str = Field(..., description="출처 URL")
    source_title: str | None = Field(default=None, description="출처 페이지 제목")
    payload: dict | None = Field(default=None, description="청크 메타데이터")


class RetrieveResponse(BaseModel):
    query: str = Field(..., description="입력 쿼리")
    notebook_id: int = Field(..., description="검색 대상 노트북 ID")
    results: list[RetrieveChunk] = Field(..., description="검색 결과 목록")
    count: int = Field(..., description="반환된 결과 수")
