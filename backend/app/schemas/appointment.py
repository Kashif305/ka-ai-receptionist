from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    customer_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    source: str = "manual"
    notes: str | None = None


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
