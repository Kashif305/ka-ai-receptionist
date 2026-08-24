import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.dashboard import dashboard_appointments
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff


NY = ZoneInfo("America/New_York")


class DashboardAppointmentFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.threading = Service(name="Threading", duration_minutes=20, active=True)
        self.facial = Service(name="Facial", duration_minutes=60, active=True)
        self.amna = Staff(name="Amna", active=True)
        self.sara = Staff(name="Sara", active=True)
        self.db.add_all([self.threading, self.facial, self.amna, self.sara])
        self.db.flush()
        self.add("Ayesha Khan", self.threading, self.amna, datetime(2026, 11, 1, 9, 30, tzinfo=NY))
        self.add("ayesha Malik", self.facial, self.sara, datetime(2026, 11, 1, 13, 0, tzinfo=NY))
        self.add("Noor Ali", self.threading, None, datetime(2026, 11, 1, 18, 0, tzinfo=NY))
        # UTC date is Nov 1 but the exact New York business date is Oct 31.
        self.add("Boundary Client", self.threading, self.amna, datetime(2026, 10, 31, 23, 30, tzinfo=NY))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, name, service, staff, start):
        customer = Customer(name=name, phone=f"1555{self.db.query(Customer).count():07d}")
        self.db.add(customer)
        self.db.flush()
        self.db.add(Appointment(customer_id=customer.id, service_id=service.id, assigned_staff_id=staff.id if staff else None, start_at=start.astimezone(timezone.utc), end_at=(start + timedelta(minutes=service.duration_minutes)).astimezone(timezone.utc), status="confirmed"))

    def get(self, **changes):
        values = {"search": None, "selected_date": None, "service_id": None, "staff_id": None, "time_of_day": None, "db": self.db}
        values.update(changes)
        return dashboard_appointments(**values)

    def test_clear_customer_date_service_staff_and_time_filters(self):
        self.assertEqual(len(self.get()), 4)
        self.assertEqual({row["customer_name"] for row in self.get(search="AYESHA")}, {"Ayesha Khan", "ayesha Malik"})
        self.assertEqual(len(self.get(selected_date=date(2026, 11, 1))), 3)
        self.assertEqual(len(self.get(service_id=self.facial.id)), 1)
        self.assertEqual(len(self.get(staff_id=self.sara.id)), 1)
        self.assertEqual({row["customer_name"] for row in self.get(time_of_day="evening")}, {"Noor Ali", "Boundary Client"})

    def test_combined_filters_use_and_semantics_and_empty_results(self):
        rows = self.get(search="ayesha", selected_date=date(2026, 11, 1), service_id=self.threading.id, staff_id=self.amna.id, time_of_day="morning")
        self.assertEqual([row["customer_name"] for row in rows], ["Ayesha Khan"])
        self.assertEqual(self.get(search="missing", service_id=self.threading.id), [])

    def test_new_york_boundary_and_invalid_time(self):
        self.assertEqual([row["customer_name"] for row in self.get(selected_date=date(2026, 10, 31))], ["Boundary Client"])
        with self.assertRaises(HTTPException) as error:
            self.get(time_of_day="late")
        self.assertEqual((error.exception.status_code, error.exception.detail), (422, "Invalid time filter"))


if __name__ == "__main__":
    unittest.main()
