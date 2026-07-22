from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppointmentCreate(BaseModel):
    customer_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    source: str = "manual"
    notes: str | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Appointment times must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_interval(self):
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self


class AppointmentRead(BaseModel):
    id: int
    customer_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    status: str
    source: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentDetail(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_phone: str
    customer_email: str | None
    service_id: int
    service_name: str
    service_duration_minutes: int
    assigned_staff_id: int | None
    assigned_staff_name: str | None
    start_at: datetime
    end_at: datetime
    status: str
    source: str
    notes: str | None
    created_at: datetime


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AppointmentReschedule(BaseModel):
    start_at: datetime
    staff_id: int | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("start_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_at must include a timezone offset")
        return value

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AppointmentSlotStaff(BaseModel):
    id: int
    name: str


class AppointmentSlot(BaseModel):
    start_at: datetime
    end_at: datetime
    available_staff: list[AppointmentSlotStaff]


class AppointmentAvailability(BaseModel):
    date: date
    service_id: int
    service_duration_minutes: int
    slots: list[AppointmentSlot]
