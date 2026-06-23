from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.service import Service


BUSINESS_TZ = ZoneInfo("America/New_York")


def _owner_numbers() -> set[str]:
    return {
        phone.strip().replace("+", "")
        for phone in settings.owner_phone_numbers.split(",")
        if phone.strip()
    }


def is_owner_phone(phone: str) -> bool:
    clean_phone = phone.strip().replace("+", "")
    return clean_phone in _owner_numbers()


def _localize(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(BUSINESS_TZ)


def _target_date_from_message(message: str):
    text = message.strip().lower()

    if text in {
        "today",
        "today appointments",
        "today's appointments",
        "todays appointments",
        "appointments today",
        "schedule today",
        "today schedule",
    }:
        return datetime.now(BUSINESS_TZ).date(), "Today's Appointments"

    if text in {
        "tomorrow",
        "tomorrow appointments",
        "tomorrow's appointments",
        "tomorrows appointments",
        "appointments tomorrow",
        "schedule tomorrow",
        "tomorrow schedule",
    }:
        return datetime.now(BUSINESS_TZ).date() + timedelta(days=1), "Tomorrow's Appointments"

    return None, None


def get_owner_summary_reply(db: Session, phone: str, message: str) -> str | None:
    if not is_owner_phone(phone):
        return None

    target_date, title = _target_date_from_message(message)
    if not target_date:
        return None

    start_at = datetime.combine(target_date, time.min, tzinfo=BUSINESS_TZ)
    end_at = datetime.combine(target_date, time.max, tzinfo=BUSINESS_TZ)

    appointments = (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= start_at)
        .filter(Appointment.start_at <= end_at)
        .order_by(Appointment.start_at.asc())
        .all()
    )

    if not appointments:
        return f"""📅 {title}
Samina Beauty Salon

No confirmed appointments found."""

    lines = [
        f"📅 {title}",
        "Samina Beauty Salon",
        "",
        f"Total: {len(appointments)}",
        "",
    ]

    for appointment in appointments:
        customer = db.get(Customer, appointment.customer_id)
        service = db.get(Service, appointment.service_id)

        local_start = _localize(appointment.start_at)
        customer_name = customer.name if customer else "Customer"
        service_name = service.name if service else "Appointment"

        lines.append(f"{local_start.strftime('%I:%M %p').lstrip('0')} — {customer_name}")
        lines.append(f"Service: {service_name}")
        lines.append("")

    return "\n".join(lines).strip()
