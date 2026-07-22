from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    price: float = Field(ge=0)
    active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ServiceUpdate(ServiceCreate):
    pass


class ServiceActiveUpdate(BaseModel):
    active: bool


class ServiceRead(BaseModel):
    id: int
    name: str
    description: str | None
    duration_minutes: int
    price: float | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
