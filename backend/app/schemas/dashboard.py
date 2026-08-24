from datetime import datetime, time

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    today_appointments: int
    upcoming_appointments: int
    total_customers: int
    active_staff: int


class DashboardAppointment(BaseModel):
    id: int
    service_id: int
    assigned_staff_id: int | None
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


class DashboardConversationListItem(BaseModel):
    id: int
    customer_name: str | None
    customer_phone: str
    last_message_preview: str | None
    last_activity_at: datetime
    status: str
    appointment_id: int | None
    ai_summary: str | None
    unread: bool


class DashboardConversationCustomer(BaseModel):
    id: int
    name: str | None
    phone: str
    email: str | None


class DashboardConversationAppointment(BaseModel):
    id: int
    service_name: str
    staff_name: str | None
    start_at: datetime
    end_at: datetime
    status: str


class DashboardConversationDetail(BaseModel):
    id: int
    customer: DashboardConversationCustomer
    status: str
    created_at: datetime
    last_activity_at: datetime
    ai_summary: str | None
    appointment: DashboardConversationAppointment | None
    internal_notes: str | None
    unread: bool


class DashboardConversationMessage(BaseModel):
    id: int
    sender: str
    body: str
    timestamp: datetime
    direction: str
    delivery_status: str | None


class DashboardConversationNotesUpdate(BaseModel):
    notes: str = Field(max_length=5000)


class DashboardConversationNotes(BaseModel):
    conversation_id: int
    notes: str | None
