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

    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).order_by(Appointment.start_at.asc()).all()
