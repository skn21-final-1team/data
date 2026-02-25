from pydantic import BaseModel, Field


class EmbeddingCallbackPayload(BaseModel):
    source_url: str = Field(..., description="원본 크롤링 URL")
    notebook_id: int = Field(..., description="노트북 ID")
    directory_id: int | None = Field(default=None, description="디렉토리 ID")
    chunks: list[str] = Field(..., description="청킹된 텍스트 목록")
    embeddings: list[list[float]] = Field(..., description="각 청크의 임베딩 벡터")
