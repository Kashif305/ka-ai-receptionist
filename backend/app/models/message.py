from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    channel: Mapped[str] = mapped_column(String(32), default="manual")
    direction: Mapped[str] = mapped_column(String(16))
    message_text: Mapped[str] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="messages")
