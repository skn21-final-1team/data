from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from api.route import router
from core.exceptions.handlers import register_exception_handlers
from db.database import Base, engine
import models  # noqa: F401 — Base.metadata에 모델 등록


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)
app.include_router(router)
