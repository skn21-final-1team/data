from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.route import router
from core.exceptions.handlers import register_exception_handlers
from core.logging import setup_logging



@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "ok"}
