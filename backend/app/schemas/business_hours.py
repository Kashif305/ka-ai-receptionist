from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BusinessHourInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    is_open: bool
    open_time: time | None = None
    close_time: time | None = None

    @model_validator(mode="after")
    def validate_interval(self):
        if self.is_open:
            if self.open_time is None or self.close_time is None:
                raise ValueError("Open days require opening and closing times")
            if self.close_time <= self.open_time:
                raise ValueError("Closing time must be later than opening time")
        elif self.open_time is not None or self.close_time is not None:
            raise ValueError("Closed days cannot include opening or closing times")
        return self


class BusinessHourRead(BusinessHourInput):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyBusinessHoursUpdate(BaseModel):
    hours: list[BusinessHourInput] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_week(self):
        weekdays = [item.weekday for item in self.hours]
        if len(set(weekdays)) != 7:
            raise ValueError("Exactly one entry per weekday is required")
        if set(weekdays) != set(range(7)):
            raise ValueError("Business hours must include Monday through Sunday")
        return self


class BusinessClosureInput(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date")
        return self


class BusinessClosureRead(BusinessClosureInput):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
