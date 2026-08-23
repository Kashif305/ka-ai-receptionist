from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.scheduling_validation import validate_selected_staff
from app.core.database import get_db
from app.models.service import Service
from app.schemas.appointment import ServiceAvailability
from app.services.availability_service import BUSINESS_TIMEZONE, list_bookable_slots


router = APIRouter(prefix="/dashboard", tags=["dashboard-availability"])


@router.get("/availability", response_model=ServiceAvailability)
def service_availability(
    service_id: int = Query(gt=0),
    selected_date: date = Query(alias="date"),
    staff_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if not service.active:
        raise HTTPException(status_code=409, detail="Service is inactive")
    if staff_id is not None:
        validate_selected_staff(db, staff_id, service.id)

    slots = list_bookable_slots(db, service, selected_date, staff_id=staff_id)
    return {
        "service_id": service.id,
        "service_name": service.name,
        "service_duration_minutes": service.duration_minutes,
        "date": selected_date,
        "timezone": BUSINESS_TIMEZONE.key,
        "slots": [
            {
                "start_at": slot.start_at,
                "end_at": slot.end_at,
                "available_staff": [
                    {"id": staff.id, "name": staff.name}
                    for staff in slot.available_staff
                ],
            }
            for slot in slots
        ],
    }
