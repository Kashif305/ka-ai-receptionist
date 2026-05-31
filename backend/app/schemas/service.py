from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    duration_minutes: int = 30
    price: float | None = None
    active: bool = True


class ServiceRead(BaseModel):
    id: int
    name: str
    description: str | None
    duration_minutes: int
    price: float | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
