import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.whatsapp import receive_whatsapp_webhook
from app.core.database import Base
from app.models.client import Client
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message
from app.services.marketing_consent_service import (
    CONSENT_PROMPT,
    begin_consent_prompt,
    consent_reply,
    consent_status,
    eligible_for_consent_prompt,
)


class Request:
    def __init__(self, message_id: str, body: str):
        self.message_id = message_id
        self.body = body

    async def json(self):
        return {"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "15550003001", "profile": {"name": "Amina"}}],
            "messages": [{"id": self.message_id, "type": "text", "text": {"body": self.body}}],
        }}]}]}


class MarketingConsentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(name="Amina", phone="15550003001", whatsapp_id="15550003001")
        self.client = Client(name="Amina", phone="15550003001", is_active=True)
        self.db.add_all([self.customer, self.client])
        self.db.flush()
        self.state = ConversationState(
            customer_id=self.customer.id,
            client_id=self.client.id,
            current_state="main_menu",
            current_step="awaiting_menu_choice",
            context_json="{}",
        )
        self.db.add(self.state)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def webhook(self, message_id: str, body: str):
        with patch("app.api.whatsapp.send_whatsapp_smart_response"):
            return asyncio.run(receive_whatsapp_webhook(Request(message_id, body), self.db))

    def await_consent(self):
        begin_consent_prompt(self.client, self.state)
        self.db.commit()

    def test_unknown_state_and_prompt_eligibility(self):
        self.assertEqual(consent_status(self.client), "not_asked")
        self.assertTrue(eligible_for_consent_prompt(self.client, self.state))
        now = datetime.now(timezone.utc)
        self.client.marketing_consent_asked_at = now
        self.assertFalse(eligible_for_consent_prompt(self.client, self.state, now=now + timedelta(days=1)))
        self.assertTrue(eligible_for_consent_prompt(self.client, self.state, now=now + timedelta(days=91)))

    def test_exact_positive_and_negative_phrase_rules(self):
        for phrase in ("YES", " I   AGREE ", "accept", "Yes Please", "sure", "SEND ME OFFERS"):
            self.assertIs(consent_reply(phrase), True)
        for phrase in ("NO", " decline ", "No   Thanks", "NOT INTERESTED"):
            self.assertIs(consent_reply(phrase), False)
        for phrase in ("sounds good", "okay", "maybe", "I agree to the appointment"):
            self.assertIsNone(consent_reply(phrase))

    def test_prompt_is_persisted_and_not_repeated(self):
        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="Our services and prices"),
            patch("app.api.whatsapp.send_whatsapp_smart_response"),
        ):
            self.webhook("prompt-1", "4")
        self.db.refresh(self.client)
        self.db.refresh(self.state)
        self.assertIsNotNone(self.client.marketing_consent_asked_at)
        self.assertEqual(self.state.current_step, "awaiting_marketing_consent")
        outbound = self.db.query(Message).filter_by(direction="outbound").one()
        self.assertIn(CONSENT_PROMPT, outbound.body)
        asked_at = self.client.marketing_consent_asked_at

        # A non-answer resumes transactional handling without recording consent.
        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="Our services and prices"),
            patch("app.api.whatsapp.send_whatsapp_smart_response"),
        ):
            self.webhook("prompt-2", "4")
        self.db.refresh(self.client)
        self.assertEqual(self.client.marketing_consent_asked_at, asked_at)
        self.assertEqual(consent_status(self.client), "not_asked")
        self.assertEqual(self.db.query(Message).filter(Message.body.contains(CONSENT_PROMPT)).count(), 1)

    def test_positive_answers_record_timestamp_source_and_bypass_booking_parser(self):
        for index, phrase in enumerate(("YES", "I AGREE", "ACCEPT")):
            if index:
                self.client.marketing_opt_in = False
                self.client.marketing_opt_in_at = None
                self.client.marketing_opt_out_at = None
            self.await_consent()
            with patch("app.api.whatsapp.classify_intent") as classify, patch(
                "app.api.whatsapp.handle_customer_message"
            ) as booking_parser:
                result = self.webhook(f"positive-{index}", phrase)
            self.db.refresh(self.client)
            self.assertEqual(result["status"], "marketing_consent_recorded")
            self.assertTrue(self.client.marketing_opt_in)
            self.assertIsNotNone(self.client.marketing_opt_in_at)
            self.assertEqual(self.client.marketing_opt_in_source, "whatsapp")
            self.assertIsNone(self.client.marketing_opt_out_at)
            classify.assert_not_called()
            booking_parser.assert_not_called()

    def test_declines_record_opt_out_and_transactional_booking_continues(self):
        for index, phrase in enumerate(("NO", "DECLINE")):
            self.client.marketing_opt_in = False
            self.client.marketing_opt_in_at = None
            self.client.marketing_opt_out_at = None
            self.await_consent()
            self.webhook(f"negative-{index}", phrase)
            self.db.refresh(self.client)
            self.assertFalse(self.client.marketing_opt_in)
            self.assertIsNotNone(self.client.marketing_opt_out_at)
            self.assertEqual(self.client.marketing_opt_in_source, "whatsapp")

        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="Choose a service") as parser,
        ):
            self.webhook("after-decline", "1")
        parser.assert_called_once()

    def test_ambiguous_reply_does_not_change_consent(self):
        self.await_consent()
        with (
            patch("app.api.whatsapp.classify_intent", return_value=None),
            patch("app.api.whatsapp.handle_customer_message", return_value="How can I help?") as parser,
        ):
            self.webhook("ambiguous", "sounds good")
        self.db.refresh(self.client)
        self.assertEqual(consent_status(self.client), "not_asked")
        parser.assert_called_once()

    def test_global_stop_and_repeat_delivery_are_idempotent(self):
        self.client.marketing_opt_in = True
        self.client.marketing_opt_in_at = datetime.now(timezone.utc)
        self.db.commit()
        first = self.webhook("same-stop", "STOP")
        decided_at = self.client.marketing_opt_out_at
        second = self.webhook("same-stop", "STOP")
        self.db.refresh(self.client)
        self.assertEqual(first["status"], "marketing_opt_out_confirmed")
        self.assertEqual(second["status"], "duplicate_ignored")
        self.assertEqual(self.client.marketing_opt_out_at, decided_at)
        self.assertFalse(self.client.marketing_opt_in)

    def test_decided_clients_are_never_prompted(self):
        self.client.marketing_opt_in = True
        self.client.marketing_opt_in_at = datetime.now(timezone.utc)
        self.assertFalse(eligible_for_consent_prompt(self.client, self.state))
        self.client.marketing_opt_in = False
        self.client.marketing_opt_out_at = datetime.now(timezone.utc)
        self.assertFalse(eligible_for_consent_prompt(self.client, self.state))


if __name__ == "__main__":
    unittest.main()
