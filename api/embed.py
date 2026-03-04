from fastapi import APIRouter
from pydantic import BaseModel, Field

from embed.config import DEFAULT_MODEL
from embed.service import embed_texts

router = APIRouter()


class QueryEmbedRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="임베딩할 쿼리 텍스트")


class QueryEmbedResponse(BaseModel):
    query: str
    embedding: list[float]
    dimension: int
    model: str


@router.post("/embed/query")
def embed_query(request: QueryEmbedRequest) -> QueryEmbedResponse:
    """쿼리 텍스트를 임베딩 벡터로 변환한다."""
    embedding = embed_texts([request.query])[0]
    return QueryEmbedResponse(
        query=request.query,
        embedding=embedding,
        dimension=len(embedding),
        model=DEFAULT_MODEL,
    )
