from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str | None = None
    phone: str
    whatsapp_id: str | None = None
    email: str | None = None
    notes: str | None = None


class CustomerRead(BaseModel):
    id: int
    name: str | None
    phone: str
    whatsapp_id: str | None
    email: str | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
