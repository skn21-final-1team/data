from fastapi import APIRouter

from api.crawl import router as crawl_router
from api.chunk import router as chunk_router
from api.embed import router as embed_router

router = APIRouter()

router.include_router(crawl_router)
router.include_router(chunk_router)
router.include_router(embed_router)
