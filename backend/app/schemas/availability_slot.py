from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AvailabilitySlotCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    slot_minutes: int = Field(default=30, gt=0)
    active: bool = True

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilitySlotRead(AvailabilitySlotCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
