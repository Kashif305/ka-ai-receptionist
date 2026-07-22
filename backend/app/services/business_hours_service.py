from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.business_hours import BusinessClosure, BusinessHour


BUSINESS_TIMEZONE = ZoneInfo("America/New_York")


class BusinessHoursError(ValueError):
    pass


def get_weekly_hours(db: Session) -> list[BusinessHour]:
    hours = db.query(BusinessHour).order_by(BusinessHour.weekday.asc()).all()
    existing = {item.weekday for item in hours}
    if len(existing) < 7:
        for weekday in range(7):
            if weekday not in existing:
                db.add(BusinessHour(weekday=weekday, is_open=False))
        db.flush()
        hours = db.query(BusinessHour).order_by(BusinessHour.weekday.asc()).all()
    return hours


def is_date_closed(db: Session, selected_date: date) -> bool:
    return (
        db.query(BusinessClosure)
        .filter(BusinessClosure.start_date <= selected_date)
        .filter(BusinessClosure.end_date >= selected_date)
        .first()
        is not None
    )


def _as_business_datetime(value: datetime) -> datetime:
    # Existing appointment rows are UTC-oriented. Treat naive legacy values as UTC
    # without changing their persisted representation.
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TIMEZONE)


def _is_valid_local_datetime(value: datetime) -> bool:
    if value.tzinfo is not BUSINESS_TIMEZONE:
        return True
    round_trip = value.astimezone(timezone.utc).astimezone(BUSINESS_TIMEZONE)
    return (
        round_trip.replace(tzinfo=None) == value.replace(tzinfo=None)
        and round_trip.fold == value.fold
    )


def validate_interval_within_business_hours(
    db: Session, start_at: datetime, end_at: datetime
) -> None:
    if end_at <= start_at:
        raise BusinessHoursError("Appointment end time must be later than start time.")

    if not _is_valid_local_datetime(start_at) or not _is_valid_local_datetime(end_at):
        raise BusinessHoursError("Selected time is invalid because of daylight-saving time.")

    local_start = _as_business_datetime(start_at)
    local_end = _as_business_datetime(end_at)
    if local_start.date() != local_end.date():
        raise BusinessHoursError("Selected time is outside business hours.")
    if is_date_closed(db, local_start.date()):
        raise BusinessHoursError("Business is closed for the selected date range.")

    hour = (
        db.query(BusinessHour)
        .filter(BusinessHour.weekday == local_start.weekday())
        .first()
    )
    if hour is None or not hour.is_open:
        raise BusinessHoursError("Business is closed on the selected day.")
    if hour.open_time is None or hour.close_time is None:
        raise BusinessHoursError("Business is closed on the selected day.")

    start_time = local_start.time().replace(tzinfo=None)
    end_time = local_end.time().replace(tzinfo=None)
    if start_time < hour.open_time or end_time > hour.close_time:
        raise BusinessHoursError("Selected time is outside business hours.")


def is_business_open_for_interval(db: Session, start_at: datetime, end_at: datetime) -> bool:
    try:
        validate_interval_within_business_hours(db, start_at, end_at)
    except BusinessHoursError:
        return False
    return True


def is_business_open_at(db: Session, moment: datetime) -> bool:
    local = _as_business_datetime(moment)
    if is_date_closed(db, local.date()):
        return False
    hour = db.query(BusinessHour).filter(BusinessHour.weekday == local.weekday()).first()
    if hour is None or not hour.is_open or hour.open_time is None or hour.close_time is None:
        return False
    local_time: time = local.time().replace(tzinfo=None)
    return hour.open_time <= local_time < hour.close_time


def list_effective_open_intervals(db: Session, selected_date: date) -> list[tuple[datetime, datetime]]:
    if is_date_closed(db, selected_date):
        return []
    hour = db.query(BusinessHour).filter(BusinessHour.weekday == selected_date.weekday()).first()
    if hour is None or not hour.is_open or hour.open_time is None or hour.close_time is None:
        return []
    return [
        (
            datetime.combine(selected_date, hour.open_time, BUSINESS_TIMEZONE),
            datetime.combine(selected_date, hour.close_time, BUSINESS_TIMEZONE),
        )
    ]
