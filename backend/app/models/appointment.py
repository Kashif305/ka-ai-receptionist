from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    status: Mapped[str] = mapped_column(String(32), default="confirmed", index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
