import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = f"1{digits}"
    if not 7 <= len(digits) <= 15:
        raise InvalidPhoneNumber("Enter a valid phone number with 7 to 15 digits")
    return digits


def meaningful_name(name: str | None) -> str | None:
    value = " ".join((name or "").split())
    if not value or value.lower() in {"customer", "unknown", "guest", "n/a"}:
        return None
    return value[:120]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_or_create_client(
    db: Session,
    phone: str,
    name: str | None = None,
    *,
    last_activity_at: datetime | None = None,
) -> tuple[Client, bool]:
    normalized = normalize_phone(phone)
    client = db.query(Client).filter(Client.phone == normalized).first()
    candidate = meaningful_name(name)
    if client:
        if candidate and not meaningful_name(client.name):
            client.name = candidate
        if last_activity_at and (not client.last_activity_at or _utc(last_activity_at) > _utc(client.last_activity_at)):
            client.last_activity_at = last_activity_at
        return client, False
    client = Client(
        name=candidate or "Customer",
        phone=normalized,
        last_activity_at=last_activity_at,
    )
    db.add(client)
    db.flush()
    return client, True


def link_customer_records(db: Session, customer: Customer, *, activity_at: datetime | None = None) -> Client:
    client, _ = get_or_create_client(db, customer.phone, customer.name, last_activity_at=activity_at)
    phone_owner = db.query(Customer).filter(
        Customer.phone == client.phone,
        Customer.id != customer.id,
    ).first()
    if not phone_owner:
        customer.phone = client.phone
    if not client.email and customer.email:
        client.email = customer.email
    for appointment in customer.appointments:
        appointment.client_id = client.id
    state = db.query(ConversationState).filter(ConversationState.customer_id == customer.id).first()
    if state:
        state.client_id = client.id
    return client


def backfill_clients(db: Session) -> dict[str, int]:
    created = linked = skipped = 0
    for customer in db.query(Customer).order_by(Customer.id).all():
        try:
            timestamps = [customer.created_at]
            timestamps += [a.created_at for a in customer.appointments if a.created_at]
            timestamps += [m.created_at for m in customer.messages if m.created_at]
            activity = max((_utc(item) for item in timestamps if item), default=None)
            _, was_created = get_or_create_client(db, customer.phone, customer.name, last_activity_at=activity)
            client = link_customer_records(db, customer, activity_at=activity)
            linked += len(customer.appointments) + int(
                db.query(ConversationState).filter(ConversationState.customer_id == customer.id).first() is not None
            )
            created += int(was_created)
        except InvalidPhoneNumber:
            skipped += 1
    db.commit()
    return {"created": created, "linked": linked, "skipped": skipped}


def touch_client(db: Session, client: Client, at: datetime | None = None) -> None:
    value = at or datetime.now(timezone.utc)
    if not client.last_activity_at or _utc(value) > _utc(client.last_activity_at):
        client.last_activity_at = value
