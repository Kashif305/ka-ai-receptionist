import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate, AppointmentRead
from app.services.whatsapp_service import send_whatsapp_text


router = APIRouter(prefix="/appointments", tags=["appointments"])
logger = logging.getLogger(__name__)


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


@router.post("/{appointment_id}/owner-cancel")
def owner_cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status == "cancelled":
        return {
            "message": "Appointment was already cancelled.",
            "appointment_id": appointment.id,
            "status": appointment.status,
            "notification_sent": False,
        }

    customer = db.get(Customer, appointment.customer_id)
    appointment.status = "cancelled"
    cancellation_note = "Cancelled by owner/admin"
    appointment.notes = (
        f"{appointment.notes}\n{cancellation_note}" if appointment.notes else cancellation_note
    )
    db.commit()
    db.refresh(appointment)

    notification_sent = False
    notification_error = None
    if customer:
        recipient = customer.whatsapp_id or customer.phone
        appointment_start = appointment.start_at
        if appointment_start.tzinfo is None:
            appointment_start = appointment_start.replace(tzinfo=timezone.utc)
        local_start = appointment_start.astimezone(ZoneInfo("America/New_York"))
        message = (
            "We’re sorry, your appointment on "
            f"{local_start.strftime('%A, %B %d at %I:%M %p')} has been cancelled "
            "due to a schedule change. Please reply 'reschedule' to choose a new appointment time."
        )
        try:
            response = send_whatsapp_text(recipient, message)
            notification_sent = response.ok
            if not response.ok:
                notification_error = "WhatsApp rejected the notification"
        except Exception:
            logger.exception(
                "Failed to send owner cancellation notification for appointment %s",
                appointment.id,
            )
            notification_error = "WhatsApp notification could not be sent"
    else:
        notification_error = "Customer record was not found"

    return {
        "message": "Appointment cancelled by owner/admin.",
        "appointment_id": appointment.id,
        "status": appointment.status,
        "notification_sent": notification_sent,
        "notification_error": notification_error,
    }
