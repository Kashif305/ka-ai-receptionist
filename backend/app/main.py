from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)


app.include_router(health_router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "running",
        "message": "Your 24/7 AI Employee for Customer Communication",
    }
