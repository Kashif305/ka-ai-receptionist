import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.whatsapp import receive_whatsapp_webhook
from app.core.config import Settings, settings
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message
from app.models.service import Service
from app.services.marketing_consent_service import begin_consent_prompt
from app.services.whatsapp_service import send_whatsapp_text


class WebhookRequest:
    def __init__(self, message_id: str, body: str, *, suppress: bool = False):
        self.message_id = message_id
        self.body = body
        self.headers = {"X-KA-QA-Suppress-Outbound": "true"} if suppress else {}

    async def json(self):
        return {"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "15550004001", "profile": {"name": "Amina"}}],
            "messages": [{"id": self.message_id, "type": "text", "text": {"body": self.body}}],
        }}]}]}


class WhatsAppQaSuppressionTests(unittest.TestCase):
    def setUp(self):
        self.original_env = settings.app_env
        self.original_enabled = settings.ka_qa_outbound_suppression_enabled
        settings.app_env = "test"
        settings.ka_qa_outbound_suppression_enabled = True
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        settings.app_env = self.original_env
        settings.ka_qa_outbound_suppression_enabled = self.original_enabled
        self.db.close()
        self.engine.dispose()

    def webhook(self, message_id: str, body: str, *, suppress: bool = True):
        return asyncio.run(
            receive_whatsapp_webhook(
                WebhookRequest(message_id, body, suppress=suppress), self.db
            )
        )

    def test_suppression_is_disabled_by_default(self):
        self.assertFalse(Settings(_env_file=None).ka_qa_outbound_suppression_enabled)

    def test_header_without_config_does_not_suppress(self):
        settings.ka_qa_outbound_suppression_enabled = False
        with patch("app.services.whatsapp_service.requests.post") as provider:
            send_whatsapp_text("15550004001", "hello", suppress_outbound=True)
        provider.assert_called_once()

    def test_config_without_header_does_not_suppress(self):
        with patch("app.services.whatsapp_service.requests.post") as provider:
            send_whatsapp_text("15550004001", "hello", suppress_outbound=False)
        provider.assert_called_once()

    def test_production_environment_never_suppresses(self):
        for production_name in ("production", "prod"):
            settings.app_env = production_name
            with self.subTest(app_env=production_name), patch(
                "app.services.whatsapp_service.requests.post"
            ) as provider:
                send_whatsapp_text("15550004001", "hello", suppress_outbound=True)
                provider.assert_called_once()

    def test_nonproduction_flag_and_header_suppress_provider_and_persist_timeline(self):
        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="Expected reply"),
            patch("app.services.whatsapp_service.requests.post") as provider,
        ):
            result = self.webhook("suppressed-timeline", "hello")
        provider.assert_not_called()
        self.assertEqual(result, {"status": "received", "qa_outbound_suppressed": True})
        self.assertEqual(self.db.query(Message).filter_by(direction="inbound").count(), 1)
        outbound = self.db.query(Message).filter_by(direction="outbound").one()
        self.assertEqual(outbound.body, "Expected reply")

    def test_suppressed_booking_flow_still_creates_appointment(self):
        service = Service(name="QA service", duration_minutes=30, active=True)
        self.db.add(service)
        self.db.commit()

        def book(db, customer, _message):
            db.add(Appointment(
                customer_id=customer.id,
                service_id=service.id,
                start_at=datetime.now(timezone.utc) + timedelta(days=1),
                end_at=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
                status="confirmed",
                source="whatsapp",
            ))
            db.commit()
            return "Appointment confirmed"

        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", side_effect=book),
            patch("app.services.whatsapp_service.requests.post") as provider,
        ):
            result = self.webhook("suppressed-booking", "confirm")
        provider.assert_not_called()
        self.assertTrue(result["qa_outbound_suppressed"])
        self.assertEqual(self.db.query(Appointment).filter_by(source="whatsapp").count(), 1)

    def test_suppressed_consent_flow_still_records_consent(self):
        customer = Customer(name="Amina", phone="15550004001", whatsapp_id="15550004001")
        client = Client(name="Amina", phone="15550004001", is_active=True)
        self.db.add_all([customer, client])
        self.db.flush()
        state = ConversationState(
            customer_id=customer.id,
            client_id=client.id,
            current_state="main_menu",
            current_step="awaiting_menu_choice",
            context_json="{}",
        )
        self.db.add(state)
        begin_consent_prompt(client, state)
        self.db.commit()
        with patch("app.services.whatsapp_service.requests.post") as provider:
            result = self.webhook("suppressed-consent", "YES")
        provider.assert_not_called()
        self.db.refresh(client)
        self.assertTrue(result["qa_outbound_suppressed"])
        self.assertTrue(client.marketing_opt_in)
        self.assertEqual(client.marketing_opt_in_source, "whatsapp")

    def test_unsuppressed_webhook_invokes_provider_and_duplicates_remain_idempotent(self):
        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="Expected reply"),
            patch("app.services.whatsapp_service.requests.post") as provider,
        ):
            first = self.webhook("normal-delivery", "hello", suppress=False)
            duplicate = self.webhook("normal-delivery", "hello")
        provider.assert_called_once()
        self.assertFalse(first["qa_outbound_suppressed"])
        self.assertEqual(duplicate, {"status": "duplicate_ignored"})
        self.assertEqual(self.db.query(Message).filter_by(direction="outbound").count(), 1)


if __name__ == "__main__":
    unittest.main()
