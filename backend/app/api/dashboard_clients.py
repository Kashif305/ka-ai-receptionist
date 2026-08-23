from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.schemas.client import ClientCreate, ClientDetail, ClientListItem, ClientUpdate
from app.services.client_service import InvalidPhoneNumber, normalize_phone
from app.services.marketing_consent_service import consent_status


router = APIRouter(prefix="/dashboard/clients", tags=["dashboard", "clients"])


def _query(db: Session):
    return db.query(Client).options(
        selectinload(Client.appointments).selectinload(Appointment.service),
        selectinload(Client.appointments).selectinload(Appointment.assigned_staff),
        selectinload(Client.conversations)
        .selectinload(ConversationState.customer)
        .selectinload(Customer.messages),
    )


def _appointment(item: Appointment) -> dict:
    return {
        "id": item.id,
        "service": item.service.name,
        "staff": item.assigned_staff.name if item.assigned_staff else None,
        "start_at": item.start_at,
        "end_at": item.end_at,
        "status": item.status,
    }


def _latest(items: list[Appointment]) -> Appointment | None:
    return max(items, key=lambda item: (item.start_at, item.id), default=None)


def _list_item(client: Client) -> dict:
    last = _latest(client.appointments)
    return {
        "id": client.id, "name": client.name, "phone": client.phone, "email": client.email,
        "is_active": client.is_active, "marketing_opt_in": client.marketing_opt_in,
        "last_activity_at": client.last_activity_at,
        "last_appointment": _appointment(last) if last else None,
        "total_appointment_count": len(client.appointments),
    }


@router.get("", response_model=list[ClientListItem])
def list_clients(
    search: str | None = None,
    status: str = Query(default="all", pattern="^(all|active|inactive|opted_in|opted_out|never_booked)$"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = _query(db)
    if search and search.strip():
        value = search.strip()
        digits = "".join(char for char in value if char.isdigit())
        conditions = [Client.name.ilike(f"%{value}%"), Client.phone.like(f"%{value}%")]
        if digits and digits != value:
            conditions.append(Client.phone.like(f"%{digits}%"))
        query = query.filter(or_(*conditions))
    if status == "active": query = query.filter(Client.is_active.is_(True))
    elif status == "inactive": query = query.filter(Client.is_active.is_(False))
    elif status == "opted_in": query = query.filter(Client.marketing_opt_in.is_(True))
    elif status == "opted_out": query = query.filter(Client.marketing_opt_in.is_(False), Client.marketing_opt_out_at.is_not(None))
    elif status == "never_booked": query = query.filter(~Client.appointments.any())
    clients = query.order_by(Client.last_activity_at.desc().nullslast(), Client.created_at.desc(), Client.id.desc()).offset(offset).limit(limit).all()
    return [_list_item(client) for client in clients]


@router.post("", response_model=ClientDetail, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    try:
        phone = normalize_phone(payload.phone)
    except InvalidPhoneNumber as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db.query(Client).filter(Client.phone == phone).first():
        raise HTTPException(status_code=409, detail="A client with this phone number already exists")
    now = datetime.now(timezone.utc)
    client = Client(**payload.model_dump(exclude={"phone"}), phone=phone)
    if payload.marketing_opt_in:
        client.marketing_opt_in_at = now
    db.add(client)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A client with this phone number already exists") from exc
    return client_detail(client.id, db)


@router.get("/{client_id}", response_model=ClientDetail)
def client_detail(client_id: int, db: Session = Depends(get_db)):
    client = _query(db).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    appointments = sorted(client.appointments, key=lambda item: (item.start_at, item.id), reverse=True)
    now = datetime.now(timezone.utc)
    def aware(value): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    upcoming = min((item for item in appointments if aware(item.start_at) >= now and item.status in {"confirmed", "booked"}), key=lambda item: item.start_at, default=None)
    conversations = []
    for state in sorted(client.conversations, key=lambda item: (item.updated_at, item.id), reverse=True):
        messages = sorted(state.customer.messages, key=lambda item: (item.created_at, item.id))
        conversations.append({"id": state.id, "last_message": messages[-1].body if messages else None, "last_activity_at": messages[-1].created_at if messages else state.updated_at, "message_count": len(messages)})
    return {
        **{key: getattr(client, key) for key in ("id", "name", "phone", "email", "birthday", "notes", "is_active", "marketing_opt_in", "marketing_opt_in_at", "marketing_opt_in_source", "marketing_opt_out_at", "marketing_consent_asked_at", "created_at", "updated_at", "last_activity_at")},
        "marketing_consent_status": consent_status(client),
        "total_appointment_count": len(appointments), "upcoming_appointment": _appointment(upcoming) if upcoming else None,
        "last_appointment": _appointment(appointments[0]) if appointments else None,
        "appointments": [_appointment(item) for item in appointments], "conversations": conversations,
    }


@router.patch("/{client_id}", response_model=ClientDetail)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client: raise HTTPException(status_code=404, detail="Client not found")
    changes = payload.model_dump(exclude_unset=True)
    if "phone" in changes:
        try: changes["phone"] = normalize_phone(changes["phone"])
        except InvalidPhoneNumber as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
        duplicate = db.query(Client).filter(Client.phone == changes["phone"], Client.id != client.id).first()
        if duplicate: raise HTTPException(status_code=409, detail="A client with this phone number already exists")
    consent = changes.get("marketing_opt_in")
    now = datetime.now(timezone.utc)
    if consent is True and not client.marketing_opt_in:
        source = changes.get("marketing_opt_in_source")
        if not source: raise HTTPException(status_code=422, detail="marketing_opt_in_source is required when enabling marketing consent")
        changes.update(marketing_opt_in_at=now, marketing_opt_out_at=None)
    elif consent is False and client.marketing_opt_in:
        changes["marketing_opt_out_at"] = now
    elif consent is not True:
        changes.pop("marketing_opt_in_source", None)
    for key, value in changes.items(): setattr(client, key, value)
    try: db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="A client with this phone number already exists") from exc
    return client_detail(client.id, db)
