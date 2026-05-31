from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
    )

    channel: Mapped[str] = mapped_column(String(50), default="whatsapp")
    direction: Mapped[str] = mapped_column(String(20), default="inbound")
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="messages")
