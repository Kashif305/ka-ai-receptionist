import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.dashboard_conversations import (
    conversation_detail,
    conversation_messages,
    list_conversations,
    update_conversation_notes,
)
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message
from app.models.service import Service
from app.schemas.dashboard import DashboardConversationNotesUpdate


class DashboardConversationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        customer = Customer(name="Amina Khan", phone="15550001111", email="amina@example.com")
        service = Service(name="Haircut", duration_minutes=45, active=True)
        self.db.add_all([customer, service])
        self.db.flush()
        self.state = ConversationState(
            customer_id=customer.id,
            current_state="main_menu",
            current_step="start",
            context_json='{"ai_summary": "Customer booked a haircut."}',
        )
        self.db.add_all(
            [
                self.state,
                Message(customer_id=customer.id, direction="inbound", body="I need a haircut"),
                Message(customer_id=customer.id, direction="outbound", body="Your haircut is booked"),
                Appointment(
                    customer_id=customer.id,
                    service_id=service.id,
                    start_at=datetime(2026, 7, 25, 14, tzinfo=timezone.utc),
                    end_at=datetime(2026, 7, 25, 14, 45, tzinfo=timezone.utc),
                    status="confirmed",
                    source="whatsapp",
                ),
            ]
        )
        self.db.commit()
        self.db.refresh(self.state)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_list_detail_and_chronological_messages(self):
        item = list_conversations(self.db)[0]
        self.assertEqual(item["status"], "booked")
        self.assertEqual(item["last_message_preview"], "Your haircut is booked")
        self.assertFalse(item["unread"])

        detail = conversation_detail(self.state.id, self.db)
        self.assertEqual(detail["appointment"]["service_name"], "Haircut")
        self.assertEqual(detail["ai_summary"], "Customer booked a haircut.")

        messages = conversation_messages(self.state.id, self.db)
        self.assertEqual([item["direction"] for item in messages], ["incoming", "outgoing"])
        self.assertEqual(messages[1]["sender"], "AI Receptionist")

    def test_internal_notes_persist_and_unknown_conversation_is_404(self):
        response = update_conversation_notes(
            self.state.id,
            DashboardConversationNotesUpdate(notes="Call before confirming changes."),
            self.db,
        )
        self.assertEqual(response["notes"], "Call before confirming changes.")
        detail = conversation_detail(self.state.id, self.db)
        self.assertEqual(detail["internal_notes"], "Call before confirming changes.")
        with self.assertRaises(HTTPException) as error:
            conversation_detail(9999, self.db)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
