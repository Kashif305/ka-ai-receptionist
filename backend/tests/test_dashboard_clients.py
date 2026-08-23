import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.dashboard_clients import create_client, list_clients, update_client
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.service import Service
from app.schemas.client import ClientCreate, ClientUpdate
from app.services.client_service import backfill_clients, get_or_create_client, normalize_phone
from app.services.conversation_service import get_or_create_state


class DashboardClientTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def payload(self, **changes):
        values = {"name": "Amina Khan", "phone": "(555) 000-1111", "email": None, "birthday": None, "notes": "VIP", "is_active": True, "marketing_opt_in": False, "marketing_opt_in_source": None}
        values.update(changes); return ClientCreate(**values)

    def test_phone_normalization_and_duplicate_prevention(self):
        self.assertEqual(normalize_phone("+1 (555) 000-1111"), "15550001111")
        created = create_client(self.payload(), self.db)
        self.assertEqual(created["phone"], "15550001111")
        with self.assertRaises(HTTPException) as error:
            create_client(self.payload(phone="+1 555 000 1111"), self.db)
        self.assertEqual(error.exception.status_code, 409)

    def test_conversation_auto_creates_and_reuses_client(self):
        customer = Customer(name="Amina Khan", phone="5550001111")
        self.db.add(customer); self.db.commit()
        first = get_or_create_state(self.db, customer)
        second = get_or_create_state(self.db, customer)
        self.assertEqual(first.client_id, second.client_id)
        self.assertEqual(self.db.query(Client).count(), 1)

    def test_appointment_link_and_backfill_are_idempotent(self):
        customer = Customer(name="Amina", phone="5550001111")
        service = Service(name="Haircut", duration_minutes=30, active=True)
        self.db.add_all([customer, service]); self.db.flush()
        appointment = Appointment(customer_id=customer.id, service_id=service.id, start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc) + timedelta(minutes=30))
        self.db.add(appointment); self.db.commit()
        first = backfill_clients(self.db); second = backfill_clients(self.db)
        self.db.refresh(appointment)
        self.assertEqual(first["created"], 1); self.assertEqual(second["created"], 0)
        self.assertIsNotNone(appointment.client_id); self.assertEqual(self.db.query(Client).count(), 1)

    def test_backfill_merges_phone_formats_and_skips_malformed_values(self):
        self.db.add_all([
            Customer(name="Amina", phone="555-000-1111"),
            Customer(name="Amina K", phone="15550001111"),
            Customer(name="Bad", phone="not-a-phone"),
        ])
        self.db.commit()
        result = backfill_clients(self.db)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(self.db.query(Client).count(), 1)

    def test_backfill_handles_naive_and_aware_activity_timestamps(self):
        customer = Customer(
            name="Amina",
            phone="5550001111",
            created_at=datetime(2026, 1, 1, 12),
        )
        service = Service(name="Haircut", duration_minutes=30, active=True)
        self.db.add_all([customer, service])
        self.db.flush()
        appointment = Appointment(
            customer_id=customer.id,
            service_id=service.id,
            start_at=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 2, 12, 30, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 2, 9, tzinfo=timezone(timedelta(hours=-5))),
        )
        self.db.add(appointment)

        result = backfill_clients(self.db)

        client = self.db.query(Client).one()
        self.assertEqual(result["created"], 1)
        self.assertEqual(client.last_activity_at, datetime(2026, 1, 2, 14))

    def test_manual_create_notes_inactive_search_and_filters(self):
        result = create_client(self.payload(is_active=False), self.db)
        self.assertEqual(result["notes"], "VIP")
        self.assertEqual(len(list_clients(search="Amina", status="all", limit=100, offset=0, db=self.db)), 1)
        self.assertEqual(len(list_clients(search=None, status="inactive", limit=100, offset=0, db=self.db)), 1)
        self.assertEqual(len(list_clients(search=None, status="active", limit=100, offset=0, db=self.db)), 0)
        self.assertEqual(len(list_clients(search=None, status="never_booked", limit=100, offset=0, db=self.db)), 1)

    def test_consent_source_and_timestamp_transitions(self):
        with self.assertRaises(ValidationError):
            self.payload(marketing_opt_in=True)
        result = create_client(self.payload(marketing_opt_in=True, marketing_opt_in_source="whatsapp"), self.db)
        self.assertIsNotNone(result["marketing_opt_in_at"])
        updated = update_client(result["id"], ClientUpdate(marketing_opt_in=False), self.db)
        self.assertIsNotNone(updated["marketing_opt_out_at"])
        with self.assertRaises(HTTPException) as error:
            update_client(result["id"], ClientUpdate(marketing_opt_in=True), self.db)
        self.assertEqual(error.exception.status_code, 422)
        opted_in = update_client(result["id"], ClientUpdate(marketing_opt_in=True, marketing_opt_in_source="phone"), self.db)
        self.assertIsNone(opted_in["marketing_opt_out_at"])

    def test_update_fields_and_duplicate_phone_conflict(self):
        first = create_client(self.payload(), self.db)
        second = create_client(self.payload(name="Zara", phone="5550002222", notes=None), self.db)
        changed = update_client(first["id"], ClientUpdate(name="Amina Ali", notes="Call first"), self.db)
        self.assertEqual(changed["name"], "Amina Ali"); self.assertEqual(changed["notes"], "Call first")
        with self.assertRaises(HTTPException) as error:
            update_client(second["id"], ClientUpdate(phone="+1 555 000 1111"), self.db)
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
