from datetime import date, datetime

from pydantic import BaseModel


class AnalyticsPeriod(BaseModel):
    key: str
    label: str
    start_date: date
    end_date: date
    start_at: datetime
    end_at: datetime
    timezone: str


class AnalyticsOverview(BaseModel):
    total_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    cancellation_rate: float
    new_clients: int
    returning_clients: int


class ServiceAnalyticsRow(BaseModel):
    service_id: int
    service_name: str
    active: bool
    appointment_count: int
    completed_count: int


class ServicesAnalytics(BaseModel):
    most_booked_service: ServiceAnalyticsRow | None
    rows: list[ServiceAnalyticsRow]


class StaffAnalyticsRow(BaseModel):
    staff_id: int | None
    staff_name: str
    active: bool | None
    appointment_count: int
    completed_count: int
    upcoming_count: int


class ClientAnalytics(BaseModel):
    new_clients: int
    returning_clients: int
    unique_clients: int
    repeat_clients: int


class PromotionAnalytics(BaseModel):
    campaigns_created: int
    campaign_recipients: int
    submitted: int
    sent: int
    delivered: int
    read: int
    replied: int
    failed: int
    delivery_rate: float | None
    read_rate: float | None
    reply_rate: float | None


class CouponAnalyticsRow(BaseModel):
    coupon_id: int
    code: str
    redemption_count: int


class CouponAnalytics(BaseModel):
    active_coupons: int
    total_redemptions: int
    most_redeemed_coupon: CouponAnalyticsRow | None
    rows: list[CouponAnalyticsRow]


class ValueAnalytics(BaseModel):
    completed_service_value: float
    currency: str
    definition: str


class AnalyticsDefinitions(BaseModel):
    appointments: str
    cancellation_rate: str
    clients: str
    repeat_clients: str
    promotions: str
    coupons: str
    completed_service_value: str


class AnalyticsDashboard(BaseModel):
    period: AnalyticsPeriod
    overview: AnalyticsOverview
    services: ServicesAnalytics
    staff: list[StaffAnalyticsRow]
    clients: ClientAnalytics
    promotions: PromotionAnalytics
    coupons: CouponAnalytics
    value: ValueAnalytics
    definitions: AnalyticsDefinitions
