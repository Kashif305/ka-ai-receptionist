from datetime import datetime

from pydantic import BaseModel


class MessageRead(BaseModel):
    id: int
    customer_id: int
    channel: str
    direction: str
    external_message_id: str | None = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True
