from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.service import Service
from app.schemas.service import ServiceActiveUpdate, ServiceCreate, ServiceRead, ServiceUpdate


router = APIRouter(prefix="/dashboard/services", tags=["dashboard-services"])


def _get_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


def _ensure_unique_name(db: Session, name: str, *, exclude_service_id: int | None = None) -> None:
    query = db.query(Service.id).filter(func.lower(Service.name) == name.lower())
    if exclude_service_id is not None:
        query = query.filter(Service.id != exclude_service_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="Service with this name already exists")


def _commit(db: Session, service: Service) -> Service:
    try:
        db.commit()
        db.refresh(service)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service with this name already exists") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save service") from exc
    return service


@router.get("", response_model=list[ServiceRead])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.name.asc()).all()


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: Session = Depends(get_db)):
    return _get_service(db, service_id)


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    _ensure_unique_name(db, payload.name)
    service = Service(**payload.model_dump())
    db.add(service)
    return _commit(db, service)


@router.put("/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, payload: ServiceUpdate, db: Session = Depends(get_db)):
    service = _get_service(db, service_id)
    _ensure_unique_name(db, payload.name, exclude_service_id=service.id)
    for field, value in payload.model_dump().items():
        setattr(service, field, value)
    return _commit(db, service)


@router.patch("/{service_id}/active", response_model=ServiceRead)
def update_service_active(service_id: int, payload: ServiceActiveUpdate, db: Session = Depends(get_db)):
    service = _get_service(db, service_id)
    service.active = payload.active
    return _commit(db, service)
