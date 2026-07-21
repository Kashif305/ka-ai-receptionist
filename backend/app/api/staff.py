from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.dashboard import utc_day_bounds
from app.core.database import get_db
from app.models.service import Service
from app.models.staff import Staff, StaffAvailability, StaffService
from app.schemas.staff import (
    StaffActiveUpdate,
    StaffAvailabilityUpdate,
    StaffCreate,
    StaffRead,
    StaffServicesUpdate,
    StaffUpdate,
)


router = APIRouter(prefix="/dashboard/staff", tags=["dashboard-staff"])


def _get_staff(db: Session, staff_id: int) -> Staff:
    staff = (
        db.query(Staff)
        .options(
            selectinload(Staff.services).selectinload(StaffService.service),
            selectinload(Staff.availability),
            selectinload(Staff.appointments),
        )
        .filter(Staff.id == staff_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return staff


def _validate_services(db: Session, service_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(service_ids))
    if len(unique_ids) != len(service_ids):
        raise HTTPException(status_code=422, detail="Duplicate service IDs are not allowed")
    if not unique_ids:
        return []

    services = db.query(Service).filter(Service.id.in_(unique_ids)).all()
    found_ids = {service.id for service in services}
    missing_ids = [service_id for service_id in unique_ids if service_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown service IDs: {', '.join(map(str, missing_ids))}",
        )
    inactive_ids = [service.id for service in services if not service.active]
    if inactive_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Inactive service IDs cannot be assigned: {', '.join(map(str, inactive_ids))}",
        )
    return unique_ids


def _validate_availability_duplicates(availability) -> None:
    keys = [
        (item.weekday, item.start_time, item.end_time)
        for item in availability
    ]
    if len(keys) != len(set(keys)):
        raise HTTPException(
            status_code=422,
            detail="Duplicate availability periods are not allowed",
        )


def _replace_services(staff: Staff, service_ids: list[int]) -> None:
    requested_ids = set(service_ids)
    current_ids = {link.service_id for link in staff.services}
    staff.services[:] = [
        link for link in staff.services if link.service_id in requested_ids
    ]
    staff.services.extend(
        StaffService(service_id=service_id)
        for service_id in service_ids
        if service_id not in current_ids
    )


def _replace_availability(staff: Staff, availability) -> None:
    staff.availability.clear()
    staff.availability.extend(
        StaffAvailability(**item.model_dump()) for item in availability
    )


def _serialize_staff(staff: Staff) -> StaffRead:
    now_utc = datetime.now(timezone.utc)
    today_start, today_end = utc_day_bounds()
    return StaffRead(
        id=staff.id,
        name=staff.name,
        phone=staff.phone,
        email=staff.email,
        active=staff.active,
        services=[
            {
                "id": link.service.id,
                "name": link.service.name,
                "duration_minutes": link.service.duration_minutes,
            }
            for link in staff.services
            if link.service is not None
        ],
        availability=[
            {
                "id": item.id,
                "weekday": item.weekday,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "slot_duration_minutes": item.slot_duration_minutes,
                "active": item.active,
            }
            for item in sorted(
                staff.availability,
                key=lambda value: (value.weekday, value.start_time),
            )
        ],
        upcoming_appointment_count=sum(
            appointment.status == "confirmed" and appointment.start_at >= now_utc
            for appointment in staff.appointments
        ),
        today_appointment_count=sum(
            appointment.status == "confirmed"
            and today_start <= appointment.start_at <= today_end
            for appointment in staff.appointments
        ),
    )


def _commit_and_reload(db: Session, staff: Staff) -> Staff:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save staff member") from exc
    db.expire_all()
    return _get_staff(db, staff.id)


@router.post("", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    service_ids = _validate_services(db, payload.service_ids)
    _validate_availability_duplicates(payload.availability)
    staff = Staff(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        active=payload.active,
    )
    _replace_services(staff, service_ids)
    _replace_availability(staff, payload.availability)
    db.add(staff)
    return _serialize_staff(_commit_and_reload(db, staff))


@router.put("/{staff_id}", response_model=StaffRead)
def update_staff(staff_id: int, payload: StaffUpdate, db: Session = Depends(get_db)):
    staff = _get_staff(db, staff_id)
    service_ids = _validate_services(db, payload.service_ids)
    _validate_availability_duplicates(payload.availability)
    staff.name = payload.name
    staff.phone = payload.phone
    staff.email = payload.email
    staff.active = payload.active
    _replace_services(staff, service_ids)
    _replace_availability(staff, payload.availability)
    return _serialize_staff(_commit_and_reload(db, staff))


@router.put("/{staff_id}/services", response_model=StaffRead)
def update_staff_services(
    staff_id: int,
    payload: StaffServicesUpdate,
    db: Session = Depends(get_db),
):
    staff = _get_staff(db, staff_id)
    _replace_services(staff, _validate_services(db, payload.service_ids))
    return _serialize_staff(_commit_and_reload(db, staff))


@router.put("/{staff_id}/availability", response_model=StaffRead)
def update_staff_availability(
    staff_id: int,
    payload: StaffAvailabilityUpdate,
    db: Session = Depends(get_db),
):
    staff = _get_staff(db, staff_id)
    _validate_availability_duplicates(payload.availability)
    _replace_availability(staff, payload.availability)
    return _serialize_staff(_commit_and_reload(db, staff))


@router.patch("/{staff_id}/active", response_model=StaffRead)
def update_staff_active(
    staff_id: int,
    payload: StaffActiveUpdate,
    db: Session = Depends(get_db),
):
    staff = _get_staff(db, staff_id)
    staff.active = payload.active
    return _serialize_staff(_commit_and_reload(db, staff))
