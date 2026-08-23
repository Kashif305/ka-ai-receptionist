from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.staff import Staff
from app.schemas.appointment import (
    AppointmentAvailability,
    AppointmentCancel,
    AppointmentDetail,
    AppointmentReschedule,
)
from app.services.staff_assignment_service import (
    get_available_staff_for_service,
    service_duration,
)
from app.services.business_hours_service import (
    BusinessHoursError,
    validate_interval_within_business_hours,
)
from app.services.availability_service import list_bookable_slots
from app.api.scheduling_validation import validate_selected_staff


router = APIRouter(prefix="/dashboard/appointments", tags=["dashboard-appointments"])
BUSINESS_TIMEZONE = ZoneInfo("America/New_York")


def _appointment_query(db: Session):
    return db.query(Appointment).options(
        selectinload(Appointment.customer),
        selectinload(Appointment.service),
        selectinload(Appointment.assigned_staff),
    )


def _get_appointment(
    db: Session,
    appointment_id: int,
    *,
    lock: bool = False,
) -> Appointment:
    query = _appointment_query(db).filter(Appointment.id == appointment_id)
    if lock:
        query = query.with_for_update()
    appointment = query.first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


def _serialize(appointment: Appointment) -> AppointmentDetail:
    return AppointmentDetail(
        id=appointment.id,
        customer_id=appointment.customer_id,
        customer_name=appointment.customer.name or "Unnamed customer",
        customer_phone=appointment.customer.phone,
        customer_email=appointment.customer.email,
        service_id=appointment.service_id,
        service_name=appointment.service.name,
        service_duration_minutes=appointment.service.duration_minutes,
        assigned_staff_id=appointment.assigned_staff_id,
        assigned_staff_name=(
            appointment.assigned_staff.name if appointment.assigned_staff else None
        ),
        start_at=appointment.start_at,
        end_at=appointment.end_at,
        status=appointment.status,
        source=appointment.source,
        notes=appointment.notes,
        created_at=appointment.created_at,
    )


def _require_confirmed(appointment: Appointment, action: str) -> None:
    if appointment.status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Only confirmed appointments can be {action}; "
                f"this appointment is {appointment.status}."
            ),
        )


def _append_note(existing: str | None, note: str) -> str:
    return f"{existing.rstrip()}\n{note}" if existing and existing.strip() else note


def _commit(db: Session, appointment: Appointment) -> AppointmentDetail:
    try:
        db.commit()
        db.refresh(appointment)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update appointment")
    return _serialize(_get_appointment(db, appointment.id))


@router.get("/{appointment_id}", response_model=AppointmentDetail)
def appointment_details(appointment_id: int, db: Session = Depends(get_db)):
    return _serialize(_get_appointment(db, appointment_id))


@router.post("/{appointment_id}/cancel", response_model=AppointmentDetail)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentCancel,
    db: Session = Depends(get_db),
):
    appointment = _get_appointment(db, appointment_id, lock=True)
    _require_confirmed(appointment, "cancelled")
    appointment.status = "cancelled"
    note = "Owner cancellation"
    if payload.reason:
        note = f"{note}: {payload.reason}"
    appointment.notes = _append_note(appointment.notes, note)
    return _commit(db, appointment)


@router.post("/{appointment_id}/complete", response_model=AppointmentDetail)
def complete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = _get_appointment(db, appointment_id, lock=True)
    _require_confirmed(appointment, "completed")
    appointment.status = "completed"
    return _commit(db, appointment)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentDetail)
def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
):
    appointment = _get_appointment(db, appointment_id, lock=True)
    _require_confirmed(appointment, "rescheduled")
    start_at = payload.start_at.astimezone(timezone.utc)
    if start_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="New appointment time must be in the future")

    if payload.staff_id is not None:
        validate_selected_staff(db, payload.staff_id, appointment.service_id)

    try:
        validate_interval_within_business_hours(
            db, start_at, start_at + service_duration(appointment.service)
        )
    except BusinessHoursError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    available_staff = get_available_staff_for_service(
        db,
        appointment.service,
        start_at,
        exclude_appointment_id=appointment.id,
    )
    if payload.staff_id is not None:
        selected_staff = next(
            (staff for staff in available_staff if staff.id == payload.staff_id),
            None,
        )
        if selected_staff is None:
            raise HTTPException(
                status_code=409,
                detail="Selected staff member is unavailable or already booked at that time",
            )
    else:
        selected_staff = next(
            (
                staff
                for staff in available_staff
                if staff.id == appointment.assigned_staff_id
            ),
            available_staff[0] if available_staff else None,
        )
        if selected_staff is None:
            raise HTTPException(
                status_code=409,
                detail="No eligible staff member is available at that time",
            )

    previous_start = appointment.start_at
    appointment.start_at = start_at
    appointment.end_at = start_at + service_duration(appointment.service)
    appointment.assigned_staff_id = selected_staff.id
    local_previous = previous_start
    if local_previous.tzinfo is None:
        local_previous = local_previous.replace(tzinfo=timezone.utc)
    previous_label = local_previous.astimezone(BUSINESS_TIMEZONE).strftime(
        "%b %d, %Y at %I:%M %p"
    )
    new_label = start_at.astimezone(BUSINESS_TIMEZONE).strftime(
        "%b %d, %Y at %I:%M %p"
    )
    history_note = f"Owner reschedule from {previous_label} to {new_label}"
    if payload.note:
        history_note = f"{history_note}: {payload.note}"
    appointment.notes = _append_note(appointment.notes, history_note)
    return _commit(db, appointment)


@router.get("/{appointment_id}/availability", response_model=AppointmentAvailability)
def appointment_availability(
    appointment_id: int,
    selected_date: date = Query(alias="date"),
    staff_id: int | None = None,
    db: Session = Depends(get_db),
):
    appointment = _get_appointment(db, appointment_id)
    _require_confirmed(appointment, "rescheduled")
    service = db.get(Service, appointment.service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if staff_id is not None:
        validate_selected_staff(db, staff_id, service.id)

    slots = list_bookable_slots(
        db,
        service,
        selected_date,
        staff_id=staff_id,
        exclude_appointment_id=appointment.id,
    )

    return {
        "date": selected_date,
        "service_id": service.id,
        "service_duration_minutes": service.duration_minutes,
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
