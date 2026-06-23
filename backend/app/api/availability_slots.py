from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.availability_slot import AvailabilitySlot
from app.schemas.availability_slot import AvailabilitySlotCreate, AvailabilitySlotRead


router = APIRouter(prefix="/availability-slots", tags=["availability-slots"])


@router.get("", response_model=list[AvailabilitySlotRead])
def list_availability_slots(db: Session = Depends(get_db)):
    return (
        db.query(AvailabilitySlot)
        .order_by(AvailabilitySlot.weekday, AvailabilitySlot.start_time)
        .all()
    )


@router.post("", response_model=AvailabilitySlotRead, status_code=201)
def create_availability_slot(
    payload: AvailabilitySlotCreate,
    db: Session = Depends(get_db),
):
    availability_slot = AvailabilitySlot(**payload.model_dump())
    db.add(availability_slot)
    db.commit()
    db.refresh(availability_slot)
    return availability_slot
