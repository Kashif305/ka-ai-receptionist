import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.dashboard_analytics import build_analytics, period_bounds
from app.core.database import Base
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.customer import Customer
from app.models.promotion import CampaignRecipient, Coupon, CouponRedemption, PromotionCampaign
from app.models.service import Service
from app.models.staff import Staff


class DashboardAnalyticsTests(unittest.TestCase):
    NOW = datetime(2026, 3, 12, 16, tzinfo=timezone.utc)

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def appointment(self, at, status="confirmed", *, service=None, staff=None, client=None, phone=None):
        service = service or Service(name=f"Service {self.db.query(Service).count()}", duration_minutes=30)
        if service.id is None:
            self.db.add(service)
        customer = Customer(name="Customer", phone=phone or f"555{self.db.query(Customer).count():07d}")
        self.db.add(customer)
        self.db.flush()
        row = Appointment(
            customer_id=customer.id, client_id=client.id if client else None,
            service_id=service.id, assigned_staff_id=staff.id if staff else None,
            start_at=at, end_at=at + timedelta(minutes=30), status=status,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def test_period_boundaries_and_business_timezone(self):
        today = period_bounds("today", now=self.NOW)
        seven = period_bounds("last_7_days", now=self.NOW)
        month = period_bounds("this_month", now=self.NOW)
        self.assertEqual((today["start_date"], today["end_date"]), (date(2026, 3, 12), date(2026, 3, 12)))
        self.assertEqual(today["start_at"], datetime(2026, 3, 12, 4, tzinfo=timezone.utc))
        self.assertEqual((seven["start_date"], seven["end_date"]), (date(2026, 3, 6), date(2026, 3, 12)))
        self.assertEqual(month["start_date"], date(2026, 3, 1))
        # The range crosses the US DST change: local midnights use different offsets.
        self.assertEqual(seven["start_at"], datetime(2026, 3, 6, 5, tzinfo=timezone.utc))
        self.assertEqual(seven["end_at"], datetime(2026, 3, 13, 4, tzinfo=timezone.utc))

    def test_status_counts_rate_zero_denominator_and_empty_period(self):
        for hour, status in enumerate(("confirmed", "completed", "cancelled", "pending"), 12):
            self.appointment(datetime(2026, 3, 12, hour, tzinfo=timezone.utc), status)
        result = build_analytics(self.db, "today", now=self.NOW)
        self.assertEqual(result["overview"], {
            "total_appointments": 4, "confirmed_appointments": 1, "completed_appointments": 1,
            "cancelled_appointments": 1, "cancellation_rate": 25.0,
            "new_clients": 3, "returning_clients": 0,
        })
        empty = build_analytics(self.db, "custom", now=self.NOW, start_date=date(2025, 1, 1), end_date=date(2025, 1, 2))
        self.assertEqual(empty["overview"]["total_appointments"], 0)
        self.assertEqual(empty["overview"]["cancellation_rate"], 0.0)
        self.assertIsNone(empty["services"]["most_booked_service"])
        self.assertIsNone(empty["promotions"]["delivery_rate"])

    def test_service_ranking_inactive_history_staff_and_value(self):
        inactive = Service(name="Legacy Facial", duration_minutes=60, price=Decimal("80"), active=False)
        other = Service(name="Brow", duration_minutes=20, price=Decimal("25"), active=True)
        staff = Staff(name="Samina", active=True)
        self.db.add_all([inactive, other, staff]); self.db.flush()
        self.appointment(datetime(2026, 3, 10, 14), "completed", service=inactive, staff=staff)
        self.appointment(datetime(2026, 3, 11, 14), "completed", service=inactive)
        self.appointment(datetime(2026, 3, 12, 18), "confirmed", service=other, staff=staff)
        result = build_analytics(self.db, "last_7_days", now=self.NOW)
        self.assertEqual(result["services"]["most_booked_service"]["service_name"], "Legacy Facial")
        self.assertFalse(result["services"]["rows"][0]["active"])
        self.assertEqual(result["services"]["rows"][0]["completed_count"], 2)
        unassigned = next(row for row in result["staff"] if row["staff_id"] is None)
        assigned = next(row for row in result["staff"] if row["staff_id"] == staff.id)
        self.assertEqual((unassigned["appointment_count"], unassigned["completed_count"]), (1, 1))
        self.assertEqual((assigned["appointment_count"], assigned["upcoming_count"]), (2, 1))
        self.assertEqual(result["value"]["completed_service_value"], 160.0)
        self.assertIn("not collected revenue", result["value"]["definition"])

    def test_new_returning_repeat_and_cancelled_client_activity(self):
        returning = Client(name="Returning", phone="5551000001")
        new = Client(name="New", phone="5551000002")
        cancelled_only = Client(name="Cancelled", phone="5551000003")
        self.db.add_all([returning, new, cancelled_only]); self.db.flush()
        self.appointment(datetime(2026, 2, 1, 15), "completed", client=returning)
        self.appointment(datetime(2026, 3, 10, 15), "completed", client=returning)
        self.appointment(datetime(2026, 3, 11, 15), "confirmed", client=returning)
        self.appointment(datetime(2026, 3, 12, 15), "confirmed", client=new)
        self.appointment(datetime(2026, 3, 12, 16), "cancelled", client=cancelled_only)
        clients = build_analytics(self.db, "last_7_days", now=self.NOW)["clients"]
        self.assertEqual(clients, {"new_clients": 1, "returning_clients": 1, "unique_clients": 2, "repeat_clients": 1})

    def test_promotion_events_rates_and_coupon_redemptions(self):
        campaign = PromotionCampaign(
            name="Spring", body_text="Hello", audience_type="all_opted_in",
            created_at=datetime(2026, 3, 10, 15),
        )
        clients = [Client(name=f"C{i}", phone=f"555200000{i}") for i in range(5)]
        self.db.add_all([campaign, *clients]); self.db.flush()
        base = {"campaign_id": campaign.id, "phone_snapshot": "555", "created_at": datetime(2026, 3, 10, 16)}
        rows = [
            CampaignRecipient(**base, client_id=clients[0].id, status="submitted", provider_message_id="m0"),
            CampaignRecipient(**base, client_id=clients[1].id, status="sent", provider_message_id="m1", sent_at=datetime(2026, 3, 10, 17)),
            CampaignRecipient(**base, client_id=clients[2].id, status="delivered", provider_message_id="m2", delivered_at=datetime(2026, 3, 10, 18)),
            CampaignRecipient(**base, client_id=clients[3].id, status="read", provider_message_id="m3", delivered_at=datetime(2026, 3, 10, 18), read_at=datetime(2026, 3, 10, 19), replied_at=datetime(2026, 3, 10, 20)),
            CampaignRecipient(**base, client_id=clients[4].id, status="failed", failed_at=datetime(2026, 3, 10, 18)),
        ]
        coupon_a = Coupon(code="SPRING", discount_type="percentage", discount_value=10, is_active=True)
        coupon_b = Coupon(code="OLD", discount_type="fixed_amount", discount_value=5, is_active=False)
        self.db.add_all([*rows, coupon_a, coupon_b]); self.db.flush()
        for coupon in (coupon_a, coupon_a, coupon_b):
            self.db.add(CouponRedemption(coupon_id=coupon.id, redeemed_at=datetime(2026, 3, 11, 15)))
        self.db.commit()
        result = build_analytics(self.db, "last_7_days", now=self.NOW)
        promotion = result["promotions"]
        self.assertEqual((promotion["submitted"], promotion["delivered"], promotion["read"], promotion["replied"], promotion["failed"]), (4, 2, 1, 1, 1))
        self.assertEqual((promotion["delivery_rate"], promotion["read_rate"], promotion["reply_rate"]), (50.0, 50.0, 50.0))
        self.assertEqual(result["coupons"]["active_coupons"], 1)
        self.assertEqual(result["coupons"]["total_redemptions"], 3)
        self.assertEqual(result["coupons"]["most_redeemed_coupon"]["code"], "SPRING")


if __name__ == "__main__":
    unittest.main()
