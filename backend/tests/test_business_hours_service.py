import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.database import Base
from app.models.business_hours import BusinessClosure
from app.services.business_hours_service import (
    BusinessHoursError,
    get_weekly_hours,
    is_business_open_for_interval,
    validate_interval_within_business_hours,
)


BUSINESS_TZ = ZoneInfo("America/New_York")


class BusinessHoursServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.hours = get_weekly_hours(self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def open_monday(self):
        monday = self.hours[0]
        monday.is_open = True
        monday.open_time = time(9)
        monday.close_time = time(17)
        self.db.commit()

    def test_defaults_to_seven_closed_days(self):
        self.assertEqual([hour.weekday for hour in self.hours], list(range(7)))
        self.assertTrue(all(not hour.is_open for hour in self.hours))

    def test_full_interval_required_and_closing_boundary_allowed(self):
        self.open_monday()
        start = datetime(2026, 7, 27, 16, 30, tzinfo=BUSINESS_TZ)
        end = datetime(2026, 7, 27, 17, 0, tzinfo=BUSINESS_TZ)
        self.assertTrue(is_business_open_for_interval(self.db, start, end))
        with self.assertRaisesRegex(BusinessHoursError, "outside business hours"):
            validate_interval_within_business_hours(
                self.db, start, datetime(2026, 7, 27, 17, 1, tzinfo=BUSINESS_TZ)
            )

    def test_closure_overrides_weekly_hours_inclusively(self):
        self.open_monday()
        self.db.add(
            BusinessClosure(
                start_date=date(2026, 7, 26),
                end_date=date(2026, 7, 28),
                reason="Vacation",
            )
        )
        self.db.commit()
        with self.assertRaisesRegex(BusinessHoursError, "selected date range"):
            validate_interval_within_business_hours(
                self.db,
                datetime(2026, 7, 27, 10, 0, tzinfo=BUSINESS_TZ),
                datetime(2026, 7, 27, 10, 30, tzinfo=BUSINESS_TZ),
            )

    def test_nonexistent_daylight_saving_time_is_rejected(self):
        sunday = self.hours[6]
        sunday.is_open = True
        sunday.open_time = time(1)
        sunday.close_time = time(4)
        self.db.commit()
        with self.assertRaisesRegex(BusinessHoursError, "daylight-saving"):
            validate_interval_within_business_hours(
                self.db,
                datetime(2026, 3, 8, 2, 30, tzinfo=BUSINESS_TZ),
                datetime(2026, 3, 8, 3, 0, tzinfo=BUSINESS_TZ),
            )


if __name__ == "__main__":
    unittest.main()
