from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.service import Service
from app.models.staff import Staff, StaffAvailability, StaffService
from app.services.business_hours_service import is_business_open_for_interval


def get_available_staff_for_service(
    db: Session,
    service: Service,
    start_at: datetime,
    exclude_appointment_id: int | None = None,
) -> list[Staff]:
    """
    Return active staff who:
    1. Can perform the selected service
    2. Are available during the requested time window
    3. Are not already booked during that time
    """
    end_at = start_at.replace()
    end_at = start_at + service_duration(service)

    if not service.active or not is_business_open_for_interval(db, start_at, end_at):
        return []

    local_start = (
        start_at.astimezone(ZoneInfo("America/New_York"))
        if start_at.tzinfo is not None
        else start_at
    )
    weekday = local_start.weekday()
    requested_start_time = local_start.time()
    local_end = (
        end_at.astimezone(ZoneInfo("America/New_York"))
        if end_at.tzinfo is not None
        else end_at
    )
    if local_start.date() != local_end.date():
        return []
    requested_end_time = local_end.time()

    qualified_staff = (
        db.query(Staff)
        .join(StaffService, StaffService.staff_id == Staff.id)
        .filter(Staff.active.is_(True))
        .filter(StaffService.service_id == service.id)
        .order_by(Staff.id.asc())
        .all()
    )

    available_staff: list[Staff] = []

    for staff in qualified_staff:
        availability = (
            db.query(StaffAvailability)
            .filter(StaffAvailability.staff_id == staff.id)
            .filter(StaffAvailability.weekday == weekday)
            .filter(StaffAvailability.active.is_(True))
            .filter(StaffAvailability.start_time <= requested_start_time)
            .filter(StaffAvailability.end_time >= requested_end_time)
            .first()
        )

        if not availability:
            continue

        conflict_query = (
            db.query(Appointment)
            .filter(Appointment.assigned_staff_id == staff.id)
            .filter(Appointment.status == "confirmed")
            .filter(Appointment.start_at < end_at)
            .filter(Appointment.end_at > start_at)
        )

        if exclude_appointment_id is not None:
            conflict_query = conflict_query.filter(Appointment.id != exclude_appointment_id)

        if conflict_query.first() is None:
            available_staff.append(staff)

    return available_staff


def service_duration(service: Service):
    from datetime import timedelta

    return timedelta(minutes=service.duration_minutes)
