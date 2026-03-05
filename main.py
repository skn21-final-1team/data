from fastapi import FastAPI

from api.route import router
from core.exceptions.handlers import register_exception_handlers

app = FastAPI()

register_exception_handlers(app)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "ok"}
