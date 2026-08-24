from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.staff import Staff, StaffService
from app.schemas.dashboard import (
    DashboardAppointment,
    DashboardCustomer,
    DashboardStaff,
    DashboardSummary,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

BUSINESS_TIMEZONE = ZoneInfo("America/New_York")


def aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def utc_day_bounds() -> tuple[datetime, datetime]:
    now_local = datetime.now(BUSINESS_TIMEZONE)
    day_start_local = datetime.combine(
        now_local.date(),
        time.min,
        tzinfo=BUSINESS_TIMEZONE,
    )
    day_end_local = datetime.combine(
        now_local.date(),
        time.max,
        tzinfo=BUSINESS_TIMEZONE,
    )
    return (
        day_start_local.astimezone(timezone.utc),
        day_end_local.astimezone(timezone.utc),
    )


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc)
    today_start, today_end = utc_day_bounds()

    today_appointments = (
        db.query(func.count(Appointment.id))
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= today_start)
        .filter(Appointment.start_at <= today_end)
        .scalar()
        or 0
    )

    upcoming_appointments = (
        db.query(func.count(Appointment.id))
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= now_utc)
        .scalar()
        or 0
    )

    total_customers = db.query(func.count(Customer.id)).scalar() or 0

    active_staff = (
        db.query(func.count(Staff.id))
        .filter(Staff.active.is_(True))
        .scalar()
        or 0
    )

    return {
        "today_appointments": today_appointments,
        "upcoming_appointments": upcoming_appointments,
        "total_customers": total_customers,
        "active_staff": active_staff,
    }


@router.get("/appointments", response_model=list[DashboardAppointment])
def dashboard_appointments(
    search: str | None = Query(default=None, max_length=120),
    selected_date: date | None = Query(default=None, alias="date"),
    service_id: int | None = Query(default=None, gt=0),
    staff_id: int | None = Query(default=None, gt=0),
    time_of_day: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if time_of_day not in {None, "morning", "afternoon", "evening"}:
        raise HTTPException(status_code=422, detail="Invalid time filter")
    query = (
        db.query(Appointment)
        .join(Appointment.customer)
        .options(
            selectinload(Appointment.customer),
            selectinload(Appointment.service),
            selectinload(Appointment.assigned_staff),
        )
    )
    if search and search.strip():
        query = query.filter(Customer.name.ilike(f"%{search.strip()}%"))
    if selected_date:
        local_start = datetime.combine(selected_date, time.min, tzinfo=BUSINESS_TIMEZONE)
        local_end = datetime.combine(selected_date, time.max, tzinfo=BUSINESS_TIMEZONE)
        query = query.filter(
            Appointment.start_at >= local_start.astimezone(timezone.utc),
            Appointment.start_at <= local_end.astimezone(timezone.utc),
        )
    if service_id is not None:
        query = query.filter(Appointment.service_id == service_id)
    if staff_id is not None:
        query = query.filter(Appointment.assigned_staff_id == staff_id)
    appointments = query.order_by(Appointment.start_at.desc()).all()
    if time_of_day:
        hour_ranges = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 24)}
        start_hour, end_hour = hour_ranges[time_of_day]
        appointments = [
            appointment
            for appointment in appointments
            if start_hour
            <= aware_utc(appointment.start_at).astimezone(BUSINESS_TIMEZONE).hour
            < end_hour
        ]

    return [
        {
            "id": appointment.id,
            "service_id": appointment.service_id,
            "assigned_staff_id": appointment.assigned_staff_id,
            "customer_name": appointment.customer.name or "Unnamed customer",
            "customer_phone": appointment.customer.phone,
            "service_name": appointment.service.name,
            "assigned_staff_name": (
                appointment.assigned_staff.name
                if appointment.assigned_staff
                else None
            ),
            "start_at": aware_utc(appointment.start_at),
            "end_at": aware_utc(appointment.end_at),
            "status": appointment.status,
            "source": appointment.source,
            "notes": appointment.notes,
        }
        for appointment in appointments
    ]


@router.get("/appointments/today", response_model=list[DashboardAppointment])
def dashboard_today_appointments(db: Session = Depends(get_db)):
    today_start, today_end = utc_day_bounds()

    appointments = (
        db.query(Appointment)
        .options(
            selectinload(Appointment.customer),
            selectinload(Appointment.service),
            selectinload(Appointment.assigned_staff),
        )
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= today_start)
        .filter(Appointment.start_at <= today_end)
        .order_by(Appointment.start_at.asc())
        .all()
    )

    return [
        {
            "id": appointment.id,
            "service_id": appointment.service_id,
            "assigned_staff_id": appointment.assigned_staff_id,
            "customer_name": appointment.customer.name or "Unnamed customer",
            "customer_phone": appointment.customer.phone,
            "service_name": appointment.service.name,
            "assigned_staff_name": (
                appointment.assigned_staff.name
                if appointment.assigned_staff
                else None
            ),
            "start_at": aware_utc(appointment.start_at),
            "end_at": aware_utc(appointment.end_at),
            "status": appointment.status,
            "source": appointment.source,
            "notes": appointment.notes,
        }
        for appointment in appointments
    ]


@router.get("/customers", response_model=list[DashboardCustomer])
def dashboard_customers(db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc)

    customers = (
        db.query(Customer)
        .options(selectinload(Customer.appointments))
        .order_by(Customer.created_at.desc())
        .all()
    )

    result = []

    for customer in customers:
        appointments = customer.appointments
        appointment_count = len(appointments)
        upcoming_count = sum(
            1
            for appointment in appointments
            if appointment.status == "confirmed"
            and appointment.start_at >= now_utc
        )
        last_appointment_at = max(
            (appointment.start_at for appointment in appointments),
            default=None,
        )

        result.append(
            {
                "id": customer.id,
                "name": customer.name or "Unnamed customer",
                "phone": customer.phone,
                "email": customer.email,
                "appointment_count": appointment_count,
                "upcoming_appointment_count": upcoming_count,
                "last_appointment_at": last_appointment_at,
                "created_at": customer.created_at,
            }
        )

    return result


@router.get("/staff", response_model=list[DashboardStaff])
def dashboard_staff(db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc)
    today_start, today_end = utc_day_bounds()

    staff_members = (
        db.query(Staff)
        .options(
            selectinload(Staff.services).selectinload(StaffService.service),
            selectinload(Staff.availability),
            selectinload(Staff.appointments),
        )
        .order_by(Staff.name.asc())
        .all()
    )

    result = []

    for staff in staff_members:
        upcoming_count = sum(
            1
            for appointment in staff.appointments
            if appointment.status == "confirmed"
            and appointment.start_at >= now_utc
        )

        today_count = sum(
            1
            for appointment in staff.appointments
            if appointment.status == "confirmed"
            and today_start <= appointment.start_at <= today_end
        )

        services = [
            {
                "id": link.service.id,
                "name": link.service.name,
                "duration_minutes": link.service.duration_minutes,
            }
            for link in staff.services
            if link.service
        ]

        availability = [
            {
                "id": slot.id,
                "weekday": slot.weekday,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "slot_duration_minutes": slot.slot_duration_minutes,
                "active": slot.active,
            }
            for slot in sorted(
                staff.availability,
                key=lambda item: (item.weekday, item.start_time),
            )
        ]

        result.append(
            {
                "id": staff.id,
                "name": staff.name,
                "phone": staff.phone,
                "email": staff.email,
                "active": staff.active,
                "services": services,
                "availability": availability,
                "upcoming_appointment_count": upcoming_count,
                "today_appointment_count": today_count,
            }
        )

    return result
