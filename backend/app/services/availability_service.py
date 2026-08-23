from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.staff import Staff, StaffAvailability, StaffService
from app.services.business_hours_service import (
    is_business_open_for_interval,
    list_effective_open_intervals,
)
from app.services.staff_assignment_service import (
    get_available_staff_for_service,
    service_duration,
)


BUSINESS_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class BookableSlot:
    start_at: datetime
    end_at: datetime
    available_staff: list[Staff]


def list_bookable_slots(
    db: Session,
    service: Service,
    selected_date: date,
    *,
    staff_id: int | None = None,
    exclude_appointment_id: int | None = None,
    now: datetime | None = None,
) -> list[BookableSlot]:
    """Return real bookable slots using the same rules as staff assignment."""
    if not service.active or not list_effective_open_intervals(db, selected_date):
        return []

    windows_query = (
        db.query(StaffAvailability)
        .join(Staff, Staff.id == StaffAvailability.staff_id)
        .join(StaffService, StaffService.staff_id == StaffAvailability.staff_id)
        .filter(StaffAvailability.weekday == selected_date.weekday())
        .filter(StaffAvailability.active.is_(True))
        .filter(Staff.active.is_(True))
        .filter(StaffService.service_id == service.id)
    )
    if staff_id is not None:
        windows_query = windows_query.filter(StaffAvailability.staff_id == staff_id)
    windows = windows_query.order_by(StaffAvailability.start_time.asc()).all()

    duration = service_duration(service)
    candidate_starts: set[datetime] = set()
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    for window in windows:
        cursor = datetime.combine(selected_date, window.start_time, BUSINESS_TIMEZONE)
        window_end = datetime.combine(selected_date, window.end_time, BUSINESS_TIMEZONE)
        while cursor + duration <= window_end:
            if (
                cursor.astimezone(timezone.utc) > current_time.astimezone(timezone.utc)
                and is_business_open_for_interval(db, cursor, cursor + duration)
            ):
                candidate_starts.add(cursor)
            cursor += timedelta(minutes=window.slot_duration_minutes)

    slots: list[BookableSlot] = []
    for start_at in sorted(candidate_starts):
        available_staff = get_available_staff_for_service(
            db,
            service,
            start_at,
            exclude_appointment_id=exclude_appointment_id,
        )
        if staff_id is not None:
            available_staff = [staff for staff in available_staff if staff.id == staff_id]
        if available_staff:
            slots.append(
                BookableSlot(
                    start_at=start_at,
                    end_at=start_at + duration,
                    available_staff=available_staff,
                )
            )
    return slots
