from fastapi import FastAPI

from api.route import router
from core.exceptions.handlers import init_exception_handlers

app = FastAPI()

init_exception_handlers(app)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "ok"}
