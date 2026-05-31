from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate, AppointmentRead


router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentRead)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    service = db.get(Service, payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    conflict = (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at < payload.end_at)
        .filter(Appointment.end_at > payload.start_at)
        .first()
    )

    if conflict:
        raise HTTPException(status_code=409, detail="Time slot already booked")

    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).order_by(Appointment.start_at.asc()).all()


@router.get("/upcoming", response_model=list[AppointmentRead])
def list_upcoming_appointments(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    return (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= now)
        .order_by(Appointment.start_at.asc())
        .all()
    )


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)
    return appointment
