from datetime import time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.dashboard import DashboardStaff


class StaffAvailabilityWrite(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(gt=0)
    active: bool = True

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class StaffProfileWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("phone", "email")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class StaffCreate(StaffProfileWrite):
    service_ids: list[int] = Field(default_factory=list)
    availability: list[StaffAvailabilityWrite] = Field(default_factory=list)


class StaffUpdate(StaffCreate):
    pass


class StaffServicesUpdate(BaseModel):
    service_ids: list[int]


class StaffAvailabilityUpdate(BaseModel):
    availability: list[StaffAvailabilityWrite]


class StaffActiveUpdate(BaseModel):
    active: bool


StaffRead = DashboardStaff
