from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead


router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(Customer.phone == payload.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="Customer with this phone already exists")

    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.created_at.desc()).all()
