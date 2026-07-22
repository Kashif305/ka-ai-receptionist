import asyncio

from fastapi import FastAPI

from app import models  # noqa: F401
from app.api.appointments import router as appointments_router
from app.api.appointment_management import router as appointment_management_router
from app.api.availability_slots import router as availability_slots_router
from app.api.business_hours import router as business_hours_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.dashboard_conversations import router as dashboard_conversations_router
from app.api.dashboard_services import router as dashboard_services_router
from app.api.health import router as health_router
from app.api.services import router as services_router
from app.api.staff import router as staff_router
from app.api.whatsapp import router as whatsapp_router
from app.core.config import settings
from app.core.database import create_db_tables
from app.services.daily_summary_service import daily_summary_loop


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.3.0",
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_tables()
    asyncio.create_task(daily_summary_loop())


app.include_router(health_router)
app.include_router(customers_router)
app.include_router(dashboard_router)
app.include_router(dashboard_conversations_router)
app.include_router(dashboard_services_router)
app.include_router(appointment_management_router)
app.include_router(staff_router)
app.include_router(services_router)
app.include_router(appointments_router)
app.include_router(availability_slots_router)
app.include_router(business_hours_router)
app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "status": "running",
        "message": "Your 24/7 AI Employee for Customer Communication",
    }
