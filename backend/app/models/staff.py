from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    services = relationship("StaffService", back_populates="staff", cascade="all, delete-orphan")
    availability = relationship("StaffAvailability", back_populates="staff", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="assigned_staff")


class StaffService(Base):
    __tablename__ = "staff_services"
    __table_args__ = (
        UniqueConstraint("staff_id", "service_id", name="uq_staff_service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)

    staff = relationship("Staff", back_populates="services")
    service = relationship("Service")


class StaffAvailability(Base):
    __tablename__ = "staff_availability"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)

    weekday: Mapped[int] = mapped_column(Integer, index=True)  # Monday=0, Sunday=6
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    staff = relationship("Staff", back_populates="availability")
