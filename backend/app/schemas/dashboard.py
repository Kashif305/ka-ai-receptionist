from datetime import datetime, time

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    today_appointments: int
    upcoming_appointments: int
    total_customers: int
    active_staff: int


class DashboardAppointment(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    service_name: str
    assigned_staff_name: str | None
    start_at: datetime
    end_at: datetime
    status: str
    source: str
    notes: str | None


class DashboardCustomer(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    appointment_count: int
    upcoming_appointment_count: int
    last_appointment_at: datetime | None
    created_at: datetime


class DashboardStaffService(BaseModel):
    id: int
    name: str
    duration_minutes: int


class DashboardStaffAvailability(BaseModel):
    id: int
    weekday: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    active: bool


class DashboardStaff(BaseModel):
    id: int
    name: str
    phone: str | None
    email: str | None
    active: bool
    services: list[DashboardStaffService]
    availability: list[DashboardStaffAvailability]
    upcoming_appointment_count: int
    today_appointment_count: int
