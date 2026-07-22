from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead
from app.services.client_service import InvalidPhoneNumber, get_or_create_client, normalize_phone


router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    try:
        normalized_phone = normalize_phone(payload.phone)
    except InvalidPhoneNumber as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = db.query(Customer).filter(Customer.phone == normalized_phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="Customer with this phone already exists")

    customer = Customer(**payload.model_dump(exclude={"phone"}), phone=normalized_phone)
    db.add(customer)
    db.flush()
    get_or_create_client(db, normalized_phone, customer.name)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.created_at.desc()).all()
