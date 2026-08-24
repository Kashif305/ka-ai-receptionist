import unittest
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.appointment_management import appointment_availability, reschedule_appointment
from app.api.dashboard_availability import service_availability
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.business_hours import BusinessClosure, BusinessHour
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff, StaffAvailability, StaffService
from app.schemas.appointment import AppointmentReschedule


BUSINESS_TZ = ZoneInfo("America/New_York")


class DashboardAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.selected_date = datetime.now(BUSINESS_TZ).date() + timedelta(days=14)
        self.db.add(
            BusinessHour(
                weekday=self.selected_date.weekday(),
                is_open=True,
                open_time=time(9),
                close_time=time(17),
            )
        )
        self.services = {}
        for name, duration in (("Facial", 60), ("Haircut", 30), ("Waxing", 45)):
            service = Service(name=name, duration_minutes=duration, active=True)
            self.db.add(service)
            self.services[name] = service
        self.db.flush()
        self.staff = self.add_staff("Amna Ahmad", self.services.values())
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_staff(self, name, services, *, active=True, available=True):
        staff = Staff(name=name, active=active)
        self.db.add(staff)
        self.db.flush()
        for service in services:
            self.db.add(StaffService(staff_id=staff.id, service_id=service.id))
        if available:
            self.db.add(
                StaffAvailability(
                    staff_id=staff.id,
                    weekday=self.selected_date.weekday(),
                    start_time=time(9),
                    end_time=time(17),
                    slot_duration_minutes=30,
                    active=True,
                )
            )
        return staff

    def get(self, service="Facial", **params):
        return service_availability(
            service_id=self.services[service].id,
            selected_date=self.selected_date,
            staff_id=params.get("staff_id"),
            db=self.db,
        )

    def test_facial_haircut_and_waxing_respect_service_duration(self):
        for name, duration in (("Facial", 60), ("Haircut", 30), ("Waxing", 45)):
            with self.subTest(service=name):
                body = self.get(name)
                self.assertEqual(body["service_name"], name)
                self.assertEqual(body["service_duration_minutes"], duration)
                self.assertTrue(body["slots"])
                start = body["slots"][0]["start_at"]
                end = body["slots"][0]["end_at"]
                self.assertEqual(end - start, timedelta(minutes=duration))
                self.assertIsNotNone(start.utcoffset())
                self.assertEqual(body["timezone"], "America/New_York")

    def test_multiple_staff_are_deduplicated_and_filterable(self):
        second = self.add_staff("Sara Khan", [self.services["Facial"]])
        self.db.commit()
        unfiltered = self.get()
        self.assertEqual(len(unfiltered["slots"]), 15)
        self.assertEqual(
            {item["id"] for item in unfiltered["slots"][0]["available_staff"]},
            {self.staff.id, second.id},
        )
        filtered = self.get(staff_id=second.id)
        self.assertTrue(filtered["slots"])
        self.assertTrue(
            all(
                slot["available_staff"] == [{"id": second.id, "name": second.name}]
                for slot in filtered["slots"]
            )
        )

    def test_staff_errors_are_clear(self):
        with self.assertRaises(HTTPException) as unknown:
            self.get(staff_id=9999)
        self.assertEqual((unknown.exception.status_code, unknown.exception.detail), (404, "Staff member not found"))
        inactive = self.add_staff("Inactive", [self.services["Facial"]], active=False)
        unassigned = self.add_staff("Unassigned", [self.services["Haircut"]])
        self.db.commit()
        with self.assertRaises(HTTPException) as inactive_response:
            self.get(staff_id=inactive.id)
        self.assertEqual(inactive_response.exception.status_code, 409)
        self.assertEqual(inactive_response.exception.detail, "Selected staff member is inactive")
        with self.assertRaises(HTTPException) as unassigned_response:
            self.get(staff_id=unassigned.id)
        self.assertEqual(unassigned_response.exception.status_code, 409)
        self.assertEqual(
            unassigned_response.exception.detail,
            "Selected staff member does not offer this service",
        )

    def test_service_and_parameter_errors_are_typed(self):
        with self.assertRaises(HTTPException) as unknown:
            service_availability(9999, self.selected_date, None, self.db)
        self.assertEqual((unknown.exception.status_code, unknown.exception.detail), (404, "Service not found"))
        self.services["Facial"].active = False
        self.db.commit()
        with self.assertRaises(HTTPException) as inactive:
            self.get()
        self.assertEqual((inactive.exception.status_code, inactive.exception.detail), (409, "Service is inactive"))
        with self.assertRaises(ValidationError):
            TypeAdapter(date).validate_python("not-a-date")

    def test_closed_day_closure_and_no_availability_return_empty_200(self):
        hour = self.db.query(BusinessHour).one()
        hour.is_open = False
        hour.open_time = None
        hour.close_time = None
        self.db.commit()
        response = self.get()
        self.assertEqual(response["slots"], [])

        hour.is_open = True
        hour.open_time = time(9)
        hour.close_time = time(17)
        self.db.add(
            BusinessClosure(
                start_date=self.selected_date,
                end_date=self.selected_date,
                reason="Holiday",
            )
        )
        self.db.commit()
        self.assertEqual(self.get()["slots"], [])

        self.db.query(BusinessClosure).delete()
        self.db.query(StaffAvailability).update({"active": False})
        self.db.commit()
        self.assertEqual(self.get()["slots"], [])

    def test_conflict_exact_close_and_past_slots(self):
        customer = Customer(name="Customer", phone="15550000000")
        self.db.add(customer)
        self.db.flush()
        conflict_start = datetime.combine(self.selected_date, time(10), BUSINESS_TZ)
        self.db.add(
            Appointment(
                customer_id=customer.id,
                service_id=self.services["Facial"].id,
                assigned_staff_id=self.staff.id,
                start_at=conflict_start,
                end_at=conflict_start + timedelta(hours=1),
                status="confirmed",
            )
        )
        self.db.commit()
        starts = {slot["start_at"].time() for slot in self.get()["slots"]}
        self.assertNotIn(time(10), starts)
        self.assertIn(time(16), starts)  # A 60-minute service may end exactly at 17:00.

        self.selected_date = datetime.now(BUSINESS_TZ).date() - timedelta(days=1)
        self.assertEqual(self.get()["slots"], [])

    def test_general_and_reschedule_endpoints_share_equivalent_results(self):
        customer = Customer(name="Customer", phone="15550000001")
        self.db.add(customer)
        self.db.flush()
        old_start = datetime.combine(self.selected_date + timedelta(days=1), time(10), BUSINESS_TZ)
        appointment = Appointment(
            customer_id=customer.id,
            service_id=self.services["Facial"].id,
            assigned_staff_id=self.staff.id,
            start_at=old_start,
            end_at=old_start + timedelta(hours=1),
            status="confirmed",
        )
        self.db.add(appointment)
        self.db.commit()
        general = self.get()["slots"]
        reschedule = appointment_availability(
            appointment.id,
            self.selected_date,
            None,
            self.db,
        )
        self.assertEqual(reschedule["slots"], general)

    def test_dashboard_slot_contract_reschedules_and_persists_staff(self):
        customer = Customer(name="Owner QA", phone="15550000002")
        self.db.add(customer)
        self.db.flush()
        old_start = datetime.combine(self.selected_date + timedelta(days=1), time(10), BUSINESS_TZ)
        appointment = Appointment(customer_id=customer.id, service_id=self.services["Facial"].id, assigned_staff_id=self.staff.id, start_at=old_start, end_at=old_start + timedelta(hours=1), status="confirmed")
        self.db.add(appointment)
        self.db.commit()
        slot = self.get()["slots"][0]
        result = reschedule_appointment(appointment.id, AppointmentReschedule(start_at=slot["start_at"], staff_id=slot["available_staff"][0]["id"], note="QA"), self.db)
        self.assertEqual(result.start_at.astimezone(BUSINESS_TZ), slot["start_at"])
        self.assertEqual(result.assigned_staff_id, self.staff.id)
        persisted = self.db.get(Appointment, appointment.id)
        persisted_start = persisted.start_at.replace(tzinfo=timezone.utc) if persisted.start_at.tzinfo is None else persisted.start_at
        self.assertEqual(persisted_start.astimezone(BUSINESS_TZ), slot["start_at"])

    def test_reschedule_rejects_noneligible_or_conflicting_staff(self):
        customer = Customer(name="Owner QA", phone="15550000003")
        other = self.add_staff("Other", [self.services["Haircut"]])
        self.db.add(customer)
        self.db.flush()
        old_start = datetime.combine(self.selected_date + timedelta(days=1), time(10), BUSINESS_TZ)
        appointment = Appointment(customer_id=customer.id, service_id=self.services["Facial"].id, assigned_staff_id=self.staff.id, start_at=old_start, end_at=old_start + timedelta(hours=1), status="confirmed")
        self.db.add(appointment)
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            reschedule_appointment(appointment.id, AppointmentReschedule(start_at=self.get()["slots"][0]["start_at"], staff_id=other.id), self.db)
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
