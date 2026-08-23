from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.promotion import CampaignRecipient, Coupon, CouponRedemption, PromotionCampaign
from app.models.service import Service
from app.models.staff import Staff
from app.schemas.analytics import AnalyticsDashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
BUSINESS_TIMEZONE = ZoneInfo("America/New_York")
PeriodKey = Literal["today", "last_7_days", "last_30_days", "this_month", "custom"]
PERIOD_LABELS = {
    "today": "Today",
    "last_7_days": "Last 7 Days",
    "last_30_days": "Last 30 Days",
    "this_month": "This Month",
    "custom": "Custom",
}


def period_bounds(
    period: PeriodKey,
    *,
    now: datetime | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    local_now = (now or datetime.now(timezone.utc)).astimezone(BUSINESS_TIMEZONE)
    today = local_now.date()
    if period == "today":
        first = last = today
    elif period == "last_7_days":
        first, last = today - timedelta(days=6), today
    elif period == "last_30_days":
        first, last = today - timedelta(days=29), today
    elif period == "this_month":
        first, last = today.replace(day=1), today
    else:
        if start_date is None or end_date is None:
            raise ValueError("Custom periods require start_date and end_date")
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        first, last = start_date, end_date
    start_local = datetime.combine(first, time.min, tzinfo=BUSINESS_TIMEZONE)
    end_local = datetime.combine(last + timedelta(days=1), time.min, tzinfo=BUSINESS_TIMEZONE)
    return {
        "key": period,
        "label": PERIOD_LABELS[period],
        "start_date": first,
        "end_date": last,
        "start_at": start_local.astimezone(timezone.utc),
        "end_at": end_local.astimezone(timezone.utc),
        "timezone": str(BUSINESS_TIMEZONE),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_analytics(
    db: Session,
    period: PeriodKey = "last_30_days",
    *,
    now: datetime | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    bounds = period_bounds(period, now=current, start_date=start_date, end_date=end_date)
    start_at, end_at = bounds["start_at"], bounds["end_at"]
    in_period = (Appointment.start_at >= start_at, Appointment.start_at < end_at)

    counts = db.query(
        func.count(Appointment.id),
        func.sum(case((Appointment.status == "confirmed", 1), else_=0)),
        func.sum(case((Appointment.status == "completed", 1), else_=0)),
        func.sum(case((Appointment.status == "cancelled", 1), else_=0)),
    ).filter(*in_period).one()
    total, confirmed, completed, cancelled = (int(value or 0) for value in counts)

    service_rows = [
        {
            "service_id": service_id,
            "service_name": name,
            "active": active,
            "appointment_count": int(appointment_count),
            "completed_count": int(completed_count or 0),
        }
        for service_id, name, active, appointment_count, completed_count in (
            db.query(
                Service.id,
                Service.name,
                Service.active,
                func.count(Appointment.id),
                func.sum(case((Appointment.status == "completed", 1), else_=0)),
            )
            .join(Appointment, Appointment.service_id == Service.id)
            .filter(*in_period)
            .group_by(Service.id, Service.name, Service.active)
            .order_by(func.count(Appointment.id).desc(), Service.name.asc())
            .all()
        )
    ]

    staff_rows = [
        {
            "staff_id": staff_id,
            "staff_name": name or "Unassigned",
            "active": active,
            "appointment_count": int(appointment_count),
            "completed_count": int(completed_count or 0),
            "upcoming_count": int(upcoming_count or 0),
        }
        for staff_id, name, active, appointment_count, completed_count, upcoming_count in (
            db.query(
                Staff.id,
                Staff.name,
                Staff.active,
                func.count(Appointment.id),
                func.sum(case((Appointment.status == "completed", 1), else_=0)),
                func.sum(case((Appointment.status == "confirmed", case((Appointment.start_at >= current, 1), else_=0)), else_=0)),
            )
            .select_from(Appointment)
            .outerjoin(Staff, Appointment.assigned_staff_id == Staff.id)
            .filter(*in_period)
            .group_by(Staff.id, Staff.name, Staff.active)
            .order_by(func.count(Appointment.id).desc(), Staff.name.asc())
            .all()
        )
    ]

    # Canonical clients are preferred; customer IDs preserve identity for unlinked history.
    identity = case(
        (Appointment.client_id.is_not(None), "client:" + func.cast(Appointment.client_id, String)),
        else_="customer:" + func.cast(Appointment.customer_id, String),
    )
    valid = Appointment.status != "cancelled"
    first_activity = (
        db.query(identity.label("identity"), func.min(Appointment.start_at).label("first_at"))
        .filter(valid)
        .group_by(identity)
        .subquery()
    )
    period_activity = (
        db.query(identity.label("identity"), func.count(Appointment.id).label("period_count"))
        .filter(valid, *in_period)
        .group_by(identity)
        .subquery()
    )
    client_rows = (
        db.query(first_activity.c.first_at, period_activity.c.period_count)
        .join(period_activity, period_activity.c.identity == first_activity.c.identity)
        .all()
    )
    new_clients = sum(1 for first_at, _ in client_rows if _as_utc(first_at) >= start_at)
    returning_clients = sum(1 for first_at, _ in client_rows if _as_utc(first_at) < start_at)
    repeat_clients = sum(1 for _, count in client_rows if count >= 2)

    campaign_ids = select(PromotionCampaign.id).where(
        PromotionCampaign.created_at >= start_at, PromotionCampaign.created_at < end_at
    )
    promotion_counts = db.query(
        func.count(CampaignRecipient.id),
        func.sum(case((CampaignRecipient.provider_message_id.is_not(None), 1), else_=0)),
        func.sum(case((CampaignRecipient.sent_at.is_not(None), 1), else_=0)),
        func.sum(case((CampaignRecipient.delivered_at.is_not(None), 1), else_=0)),
        func.sum(case((CampaignRecipient.read_at.is_not(None), 1), else_=0)),
        func.sum(case((CampaignRecipient.replied_at.is_not(None), 1), else_=0)),
        func.sum(case((CampaignRecipient.failed_at.is_not(None), 1), else_=0)),
    ).filter(CampaignRecipient.campaign_id.in_(campaign_ids)).one()
    recipients, submitted, sent, delivered, read, replied, failed = (int(v or 0) for v in promotion_counts)
    campaigns_created = db.query(func.count(PromotionCampaign.id)).filter(
        PromotionCampaign.created_at >= start_at, PromotionCampaign.created_at < end_at
    ).scalar() or 0

    redemption_rows = [
        {"coupon_id": coupon_id, "code": code, "redemption_count": int(count)}
        for coupon_id, code, count in (
            db.query(Coupon.id, Coupon.code, func.count(CouponRedemption.id))
            .join(CouponRedemption, CouponRedemption.coupon_id == Coupon.id)
            .filter(CouponRedemption.redeemed_at >= start_at, CouponRedemption.redeemed_at < end_at)
            .group_by(Coupon.id, Coupon.code)
            .order_by(func.count(CouponRedemption.id).desc(), Coupon.code.asc())
            .all()
        )
    ]
    active_coupons = db.query(func.count(Coupon.id)).filter(
        Coupon.is_active.is_(True),
        (Coupon.starts_at.is_(None) | (Coupon.starts_at <= current)),
        (Coupon.expires_at.is_(None) | (Coupon.expires_at >= current)),
        (Coupon.redemption_limit.is_(None) | (Coupon.redemption_count < Coupon.redemption_limit)),
    ).scalar() or 0
    completed_value = db.query(func.coalesce(func.sum(Service.price), 0)).select_from(Appointment).join(
        Service, Appointment.service_id == Service.id
    ).filter(*in_period, Appointment.status == "completed").scalar() or 0

    value_definition = (
        "Sum of current service prices for completed appointments in the selected period; "
        "missing prices contribute $0. This is booked-list-price value, not collected revenue."
    )
    return {
        "period": bounds,
        "overview": {
            "total_appointments": total,
            "confirmed_appointments": confirmed,
            "completed_appointments": completed,
            "cancelled_appointments": cancelled,
            "cancellation_rate": _rate(cancelled, total) or 0.0,
            "new_clients": new_clients,
            "returning_clients": returning_clients,
        },
        "services": {"most_booked_service": service_rows[0] if service_rows else None, "rows": service_rows},
        "staff": staff_rows,
        "clients": {
            "new_clients": new_clients,
            "returning_clients": returning_clients,
            "unique_clients": len(client_rows),
            "repeat_clients": repeat_clients,
        },
        "promotions": {
            "campaigns_created": int(campaigns_created), "campaign_recipients": recipients,
            "submitted": submitted, "sent": sent, "delivered": delivered, "read": read,
            "replied": replied, "failed": failed, "delivery_rate": _rate(delivered, submitted),
            "read_rate": _rate(read, delivered), "reply_rate": _rate(replied, delivered),
        },
        "coupons": {
            "active_coupons": int(active_coupons), "total_redemptions": sum(r["redemption_count"] for r in redemption_rows),
            "most_redeemed_coupon": redemption_rows[0] if redemption_rows else None, "rows": redemption_rows,
        },
        "value": {"completed_service_value": float(completed_value), "currency": "USD", "definition": value_definition},
        "definitions": {
            "appointments": "Appointments whose scheduled start falls in the selected period; status counts are exact current statuses.",
            "cancellation_rate": "Cancelled appointments divided by all appointments in the selected period.",
            "clients": "Unique non-cancelled appointment identities. New means the first known non-cancelled appointment is in the period; returning means it was earlier.",
            "repeat_clients": "Unique clients with at least two non-cancelled appointments in the selected period.",
            "promotions": "Campaigns created in the period and their recipient outcomes. Submitted requires provider acceptance; delivery requires a delivery event.",
            "coupons": "Redemption events recorded in the period; active coupons are usable as of now.",
            "completed_service_value": value_definition,
        },
    }


@router.get("/analytics", response_model=AnalyticsDashboard)
def dashboard_analytics(
    period: PeriodKey = Query("last_30_days"),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    try:
        return build_analytics(db, period, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
