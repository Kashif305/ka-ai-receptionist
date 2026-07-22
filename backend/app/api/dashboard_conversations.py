import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message
from app.schemas.dashboard import (
    DashboardConversationDetail,
    DashboardConversationListItem,
    DashboardConversationMessage,
    DashboardConversationNotes,
    DashboardConversationNotesUpdate,
)


router = APIRouter(prefix="/dashboard/conversations", tags=["dashboard"])


def _context(state: ConversationState) -> dict:
    try:
        value = json.loads(state.context_json or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _latest_appointment(state: ConversationState) -> Appointment | None:
    appointments = state.customer.appointments
    return max(appointments, key=lambda item: (item.created_at, item.id), default=None)


def _status(state: ConversationState, appointment: Appointment | None) -> str:
    if appointment and appointment.status in {"cancelled", "canceled"}:
        return "cancelled"
    if appointment and appointment.status == "completed":
        return "completed"
    if appointment and appointment.status in {"confirmed", "booked"}:
        return "booked"
    if state.current_state == "human_handoff":
        return "waiting"
    return "active"


def _messages(state: ConversationState) -> list[Message]:
    return sorted(state.customer.messages, key=lambda item: (item.created_at, item.id))


def _created_at(state: ConversationState, messages: list[Message]) -> datetime:
    return messages[0].created_at if messages else state.customer.created_at


def _last_activity(state: ConversationState, messages: list[Message]) -> datetime:
    return messages[-1].created_at if messages else state.updated_at


def _query(db: Session):
    return db.query(ConversationState).options(
        selectinload(ConversationState.customer).selectinload(Customer.messages),
        selectinload(ConversationState.customer)
        .selectinload(Customer.appointments)
        .selectinload(Appointment.service),
        selectinload(ConversationState.customer)
        .selectinload(Customer.appointments)
        .selectinload(Appointment.assigned_staff),
    )


def _get_conversation(db: Session, conversation_id: int) -> ConversationState:
    state = _query(db).filter(ConversationState.id == conversation_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return state


@router.get("", response_model=list[DashboardConversationListItem])
def list_conversations(db: Session = Depends(get_db)):
    result = []
    for state in _query(db).all():
        messages = _messages(state)
        appointment = _latest_appointment(state)
        result.append(
            {
                "id": state.id,
                "customer_name": state.customer.name,
                "customer_phone": state.customer.phone,
                "last_message_preview": messages[-1].body[:160] if messages else None,
                "last_activity_at": _last_activity(state, messages),
                "status": _status(state, appointment),
                "appointment_id": appointment.id if appointment else None,
                "ai_summary": _context(state).get("ai_summary"),
                "unread": False,
            }
        )
    return sorted(result, key=lambda item: item["last_activity_at"], reverse=True)


@router.get("/{conversation_id}", response_model=DashboardConversationDetail)
def conversation_detail(conversation_id: int, db: Session = Depends(get_db)):
    state = _get_conversation(db, conversation_id)
    messages = _messages(state)
    appointment = _latest_appointment(state)
    return {
        "id": state.id,
        "customer": {
            "id": state.customer.id,
            "name": state.customer.name,
            "phone": state.customer.phone,
            "email": state.customer.email,
        },
        "status": _status(state, appointment),
        "created_at": _created_at(state, messages),
        "last_activity_at": _last_activity(state, messages),
        "ai_summary": _context(state).get("ai_summary"),
        "appointment": (
            {
                "id": appointment.id,
                "service_name": appointment.service.name,
                "staff_name": appointment.assigned_staff.name if appointment.assigned_staff else None,
                "start_at": appointment.start_at,
                "end_at": appointment.end_at,
                "status": appointment.status,
            }
            if appointment
            else None
        ),
        "internal_notes": state.customer.notes,
        "unread": False,
    }


@router.get("/{conversation_id}/messages", response_model=list[DashboardConversationMessage])
def conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    state = _get_conversation(db, conversation_id)
    return [
        {
            "id": message.id,
            "sender": state.customer.name or "Customer" if message.direction == "inbound" else "AI Receptionist",
            "body": message.body,
            "timestamp": message.created_at,
            "direction": "incoming" if message.direction == "inbound" else "outgoing",
            "delivery_status": None,
        }
        for message in _messages(state)
    ]


@router.patch("/{conversation_id}/notes", response_model=DashboardConversationNotes)
def update_conversation_notes(
    conversation_id: int,
    payload: DashboardConversationNotesUpdate,
    db: Session = Depends(get_db),
):
    state = _get_conversation(db, conversation_id)
    state.customer.notes = payload.notes.strip() or None
    db.commit()
    return {"conversation_id": state.id, "notes": state.customer.notes}
