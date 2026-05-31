from fastapi import FastAPI

from app import models  # noqa: F401
from app.api.appointments import router as appointments_router
from app.api.customers import router as customers_router
from app.api.health import router as health_router
from app.api.services import router as services_router
from app.api.whatsapp import router as whatsapp_router
from app.core.config import settings
from app.core.database import create_db_tables


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.3.0",
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_tables()


app.include_router(health_router)
app.include_router(customers_router)
app.include_router(services_router)
app.include_router(appointments_router)
app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "running",
        "message": "Your 24/7 AI Employee for Customer Communication",
    }
