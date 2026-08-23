from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.staff import Staff, StaffService


def validate_selected_staff(db: Session, staff_id: int, service_id: int) -> Staff:
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if not staff.active:
        raise HTTPException(status_code=409, detail="Selected staff member is inactive")
    offers_service = (
        db.query(StaffService)
        .filter(StaffService.staff_id == staff_id)
        .filter(StaffService.service_id == service_id)
        .first()
    )
    if offers_service is None:
        raise HTTPException(
            status_code=409,
            detail="Selected staff member does not offer this service",
        )
    return staff
