from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"),
        CheckConstraint("end_time > start_time", name="ck_availability_time_range"),
        CheckConstraint("slot_minutes > 0", name="ck_availability_slot_minutes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
