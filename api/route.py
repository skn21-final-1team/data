from fastapi import APIRouter

from api.crawl import router as crawl_router
from api.health import router as health_router

router = APIRouter()

router.include_router(crawl_router)
router.include_router(health_router)
