from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConsentSource = Literal["in_person", "whatsapp", "website", "phone", "imported", "other"]


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str
    email: str | None = Field(default=None, max_length=255)
    birthday: date | None = None
    notes: str | None = None
    is_active: bool = True
    marketing_opt_in: bool = False
    marketing_opt_in_source: ConsentSource | None = None

    @model_validator(mode="after")
    def require_consent_source(self):
        if self.marketing_opt_in and not self.marketing_opt_in_source:
            raise ValueError("marketing_opt_in_source is required when marketing consent is enabled")
        return self


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = None
    email: str | None = Field(default=None, max_length=255)
    birthday: date | None = None
    notes: str | None = None
    is_active: bool | None = None
    marketing_opt_in: bool | None = None
    marketing_opt_in_source: ConsentSource | None = None


class ClientAppointmentSummary(BaseModel):
    id: int
    service: str
    staff: str | None
    start_at: datetime
    end_at: datetime
    status: str


class ClientConversationSummary(BaseModel):
    id: int
    last_message: str | None
    last_activity_at: datetime
    message_count: int


class ClientListItem(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    is_active: bool
    marketing_opt_in: bool
    last_activity_at: datetime | None
    last_appointment: ClientAppointmentSummary | None
    total_appointment_count: int


class ClientDetail(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    birthday: date | None
    notes: str | None
    is_active: bool
    marketing_opt_in: bool
    marketing_opt_in_at: datetime | None
    marketing_opt_in_source: str | None
    marketing_opt_out_at: datetime | None
    marketing_consent_asked_at: datetime | None
    marketing_consent_status: Literal["not_asked", "opted_in", "opted_out"]
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime | None
    total_appointment_count: int
    upcoming_appointment: ClientAppointmentSummary | None
    last_appointment: ClientAppointmentSummary | None
    appointments: list[ClientAppointmentSummary]
    conversations: list[ClientConversationSummary]

    model_config = ConfigDict(from_attributes=True)
