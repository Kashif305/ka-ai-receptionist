from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.business_hours import BusinessClosure
from app.schemas.business_hours import (
    BusinessClosureInput,
    BusinessClosureRead,
    BusinessHourRead,
    WeeklyBusinessHoursUpdate,
)
from app.services.business_hours_service import get_weekly_hours


router = APIRouter(prefix="/dashboard", tags=["dashboard-business-hours"])


def _commit(db: Session, message: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail=message)


def _get_closure(db: Session, closure_id: int) -> BusinessClosure:
    closure = db.get(BusinessClosure, closure_id)
    if closure is None:
        raise HTTPException(status_code=404, detail="Business closure not found")
    return closure


def _ensure_no_overlap(
    db: Session,
    payload: BusinessClosureInput,
    exclude_id: int | None = None,
) -> None:
    query = (
        db.query(BusinessClosure)
        .filter(BusinessClosure.start_date <= payload.end_date)
        .filter(BusinessClosure.end_date >= payload.start_date)
    )
    if exclude_id is not None:
        query = query.filter(BusinessClosure.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Closure dates overlap an existing business closure.",
        )


@router.get("/business-hours", response_model=list[BusinessHourRead])
def list_business_hours(db: Session = Depends(get_db)):
    hours = get_weekly_hours(db)
    _commit(db, "Unable to initialize business hours")
    return hours


@router.put("/business-hours", response_model=list[BusinessHourRead])
def update_business_hours(
    payload: WeeklyBusinessHoursUpdate,
    db: Session = Depends(get_db),
):
    hours = get_weekly_hours(db)
    by_weekday = {item.weekday: item for item in hours}
    for requested in payload.hours:
        record = by_weekday[requested.weekday]
        record.is_open = requested.is_open
        record.open_time = requested.open_time if requested.is_open else None
        record.close_time = requested.close_time if requested.is_open else None
    _commit(db, "Unable to update business hours")
    return get_weekly_hours(db)


@router.get("/business-closures", response_model=list[BusinessClosureRead])
def list_business_closures(db: Session = Depends(get_db)):
    return (
        db.query(BusinessClosure)
        .order_by(BusinessClosure.start_date.asc(), BusinessClosure.id.asc())
        .all()
    )


@router.post(
    "/business-closures",
    response_model=BusinessClosureRead,
    status_code=status.HTTP_201_CREATED,
)
def create_business_closure(
    payload: BusinessClosureInput,
    db: Session = Depends(get_db),
):
    _ensure_no_overlap(db, payload)
    closure = BusinessClosure(**payload.model_dump())
    db.add(closure)
    _commit(db, "Unable to create business closure")
    db.refresh(closure)
    return closure


@router.put("/business-closures/{closure_id}", response_model=BusinessClosureRead)
def update_business_closure(
    closure_id: int,
    payload: BusinessClosureInput,
    db: Session = Depends(get_db),
):
    closure = _get_closure(db, closure_id)
    _ensure_no_overlap(db, payload, exclude_id=closure.id)
    closure.start_date = payload.start_date
    closure.end_date = payload.end_date
    closure.reason = payload.reason
    _commit(db, "Unable to update business closure")
    db.refresh(closure)
    return closure


@router.delete("/business-closures/{closure_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_closure(closure_id: int, db: Session = Depends(get_db)):
    closure = _get_closure(db, closure_id)
    db.delete(closure)
    _commit(db, "Unable to remove business closure")
