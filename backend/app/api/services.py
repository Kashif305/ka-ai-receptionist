from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceRead


router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    existing = db.query(Service).filter(Service.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Service with this name already exists")

    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("", response_model=list[ServiceRead])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.name.asc()).all()
