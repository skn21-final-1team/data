from fastapi import FastAPI

from api.crawl import router as crawl_router
from api.chunk import router as chunk_router
from api.embed import router as embed_router

app = FastAPI()

app.include_router(crawl_router)
app.include_router(chunk_router)
app.include_router(embed_router)
