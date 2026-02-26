from fastapi import APIRouter

from db.database import DbSession
from retriever.service import retrieve
from schemas.retriever import RetrieveChunk, RetrieveRequest, RetrieveResponse

router = APIRouter()


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_chunks(
    request: RetrieveRequest,
    db: DbSession,
) -> RetrieveResponse:
    results = retrieve(
        db=db,
        query=request.query,
        notebook_id=request.notebook_id,
        top_k=request.top_k,
    )

    return RetrieveResponse(
        query=request.query,
        notebook_id=request.notebook_id,
        results=[RetrieveChunk(**r) for r in results],
        count=len(results),
    )
