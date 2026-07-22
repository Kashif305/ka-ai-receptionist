from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessHour(Base):
    __tablename__ = "business_hours"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_business_hours_weekday"),
        CheckConstraint(
            "(is_open = false AND open_time IS NULL AND close_time IS NULL) OR "
            "(is_open = true AND open_time IS NOT NULL AND close_time IS NOT NULL "
            "AND close_time > open_time)",
            name="ck_business_hours_valid_interval",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    is_open: Mapped[bool]
    open_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BusinessClosure(Base):
    __tablename__ = "business_closures"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_business_closures_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
