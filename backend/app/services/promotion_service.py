from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.whatsapp_cloud import WhatsAppCampaignProvider
from app.models.client import Client
from app.models.promotion import CampaignRecipient, Coupon, CouponRedemption, PromotionCampaign
from app.services.client_service import InvalidPhoneNumber, normalize_phone
from app.services.promotion_audience_service import AudienceResolution, resolve_campaign_audience


EDITABLE_STATUSES = {"draft", "scheduled"}
TERMINAL_STATUSES = {"completed", "partially_completed", "failed", "cancelled"}
DELIVERY_RANK = {"pending": 0, "queued": 1, "submitted": 2, "sent": 3, "delivered": 4, "read": 5, "replied": 6}


class PromotionError(ValueError):
    pass


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_coupon(coupon: Coupon, *, now: datetime | None = None, for_redemption: bool = False) -> None:
    if coupon.discount_value <= 0:
        raise PromotionError("Discount value must be greater than zero")
    if coupon.discount_type == "percentage" and coupon.discount_value > 100:
        raise PromotionError("Percentage discount cannot exceed 100")
    if coupon.discount_type not in {"percentage", "fixed_amount"}:
        raise PromotionError("Unsupported discount type")
    if coupon.starts_at and coupon.expires_at and utc(coupon.expires_at) < utc(coupon.starts_at):
        raise PromotionError("Expiration cannot precede the start date")
    if for_redemption:
        current = utc(now or datetime.now(timezone.utc))
        if not coupon.is_active:
            raise PromotionError("Coupon is inactive")
        if coupon.starts_at and current < utc(coupon.starts_at):
            raise PromotionError("Coupon is not active yet")
        if coupon.expires_at and current > utc(coupon.expires_at):
            raise PromotionError("Coupon is expired")
        if coupon.redemption_limit is not None and coupon.redemption_count >= coupon.redemption_limit:
            raise PromotionError("Coupon redemption limit has been reached")


def validate_campaign(campaign: PromotionCampaign) -> None:
    if campaign.status in TERMINAL_STATUSES:
        raise PromotionError(f"Campaign cannot be sent while {campaign.status}")
    if not campaign.message_template_name.strip():
        raise PromotionError("WhatsApp template name is required")
    if not campaign.message_template_language.strip():
        raise PromotionError("WhatsApp template language is required")
    if campaign.coupon:
        validate_coupon(campaign.coupon)


def preview_campaign(db: Session, campaign: PromotionCampaign) -> AudienceResolution:
    return resolve_campaign_audience(db, campaign.audience_type, campaign.audience_config)


def prepare_campaign(db: Session, campaign: PromotionCampaign) -> tuple[AudienceResolution, list[CampaignRecipient]]:
    validate_campaign(campaign)
    resolution = preview_campaign(db, campaign)
    existing = {recipient.client_id: recipient for recipient in campaign.recipients}
    prepared: list[CampaignRecipient] = []
    for row in resolution.eligible:
        recipient = existing.get(row.client_id)
        if recipient is None:
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                client_id=row.client_id,
                phone_snapshot=row.phone,
                client_name_snapshot=row.name,
                consent_source_snapshot=row.consent_source,
                consent_at_snapshot=row.consent_at,
                status="pending",
            )
            db.add(recipient)
        prepared.append(recipient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prepared = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.campaign_id == campaign.id)
            .order_by(CampaignRecipient.id)
            .all()
        )
    return resolution, prepared


def campaign_counts(campaign: PromotionCampaign) -> dict[str, int]:
    counts = Counter(recipient.status for recipient in campaign.recipients)
    return {status: count for status, count in sorted(counts.items())}


def send_campaign(db: Session, campaign: PromotionCampaign, provider=None) -> dict:
    if campaign.status in TERMINAL_STATUSES:
        raise PromotionError(f"Campaign cannot be sent while {campaign.status}")
    if campaign.status == "sending":
        raise PromotionError("Campaign is already sending")
    if provider is None:
        from app.core.config import settings
        if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
            raise PromotionError("WhatsApp credentials are unavailable")
    resolution, recipients = prepare_campaign(db, campaign)
    if not recipients:
        raise PromotionError("Campaign has no eligible recipients")

    started_at = campaign.started_at or datetime.now(timezone.utc)
    claimed = db.execute(
        update(PromotionCampaign)
        .where(
            PromotionCampaign.id == campaign.id,
            PromotionCampaign.status.in_(["draft", "scheduled", "preparing"]),
        )
        .values(status="sending", started_at=started_at)
    )
    db.commit()
    if claimed.rowcount != 1:
        raise PromotionError("Campaign is already sending or has finished")
    db.refresh(campaign)
    adapter = provider or WhatsAppCampaignProvider()
    accepted = failed = skipped = 0

    for recipient in recipients:
        if recipient.status != "pending":
            skipped += 1
            continue
        client = db.get(Client, recipient.client_id)
        try:
            current_phone = normalize_phone(client.phone) if client else None
        except InvalidPhoneNumber:
            current_phone = None
        if not client or not client.is_active or not client.marketing_opt_in or current_phone != recipient.phone_snapshot:
            recipient.status = "skipped"
            recipient.failure_code = "ineligible_at_send"
            recipient.failure_message = "Client was no longer eligible at send time"
            db.commit()
            skipped += 1
            continue

        recipient.status = "queued"
        recipient.queued_at = datetime.now(timezone.utc)
        db.commit()
        result = adapter.send_campaign_template(recipient, campaign, campaign.coupon)
        if result.accepted and result.provider_message_id:
            recipient.status = "submitted"
            recipient.provider_message_id = result.provider_message_id
            accepted += 1
        else:
            recipient.status = "failed"
            recipient.failed_at = datetime.now(timezone.utc)
            recipient.failure_code = result.error_code
            recipient.failure_message = result.error_message
            failed += 1
        db.commit()

    campaign.completed_at = datetime.now(timezone.utc)
    if accepted and not failed:
        campaign.status = "completed"
    elif accepted:
        campaign.status = "partially_completed"
    else:
        campaign.status = "failed"
    db.commit()
    return {
        "campaign_id": campaign.id,
        "status": campaign.status,
        "eligible": len(resolution.eligible),
        "excluded": sum(resolution.exclusions.values()),
        "exclusion_reasons": resolution.exclusions,
        "submitted": accepted,
        "failed": failed,
        "skipped": skipped,
    }


def process_due_campaigns(db: Session, provider=None, *, now: datetime | None = None, limit: int = 20) -> list[dict]:
    current = utc(now or datetime.now(timezone.utc))
    due_ids = [
        campaign_id
        for (campaign_id,) in (
            db.query(PromotionCampaign.id)
            .filter(PromotionCampaign.status == "scheduled", PromotionCampaign.scheduled_at <= current)
            .order_by(PromotionCampaign.scheduled_at, PromotionCampaign.id)
            .limit(limit)
            .all()
        )
    ]
    results = []
    for campaign_id in due_ids:
        claimed = db.execute(
            update(PromotionCampaign)
            .where(PromotionCampaign.id == campaign_id, PromotionCampaign.status == "scheduled")
            .values(status="preparing", started_at=current)
        )
        db.commit()
        if claimed.rowcount != 1:
            continue
        campaign = db.get(PromotionCampaign, campaign_id)
        try:
            results.append(send_campaign(db, campaign, provider=provider))
        except PromotionError as exc:
            campaign.status = "failed"
            campaign.completed_at = datetime.now(timezone.utc)
            db.commit()
            results.append({"campaign_id": campaign_id, "status": "failed", "error": str(exc)})
    return results


def update_delivery_status(
    db: Session,
    provider_message_id: str,
    status: str,
    occurred_at: datetime,
    *,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> bool:
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.provider_message_id == provider_message_id).first()
    if recipient is None or status not in {"sent", "delivered", "read", "failed"}:
        return False
    if status != "failed" and recipient.status != "failed":
        if DELIVERY_RANK.get(status, -1) < DELIVERY_RANK.get(recipient.status, -1):
            return True
        recipient.status = status
        setattr(recipient, f"{status}_at", utc(occurred_at))
    elif status == "failed" and DELIVERY_RANK.get(recipient.status, -1) <= DELIVERY_RANK["submitted"]:
        recipient.status = "failed"
        recipient.failed_at = utc(occurred_at)
        recipient.failure_code = failure_code
        recipient.failure_message = failure_message
    db.commit()
    return True


def mark_recent_campaign_reply(db: Session, client_id: int, *, now: datetime | None = None) -> bool:
    current = utc(now or datetime.now(timezone.utc))
    cutoff = current - timedelta(days=7)
    recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.client_id == client_id,
            CampaignRecipient.status.in_(["submitted", "sent", "delivered", "read"]),
            CampaignRecipient.queued_at >= cutoff,
        )
        .order_by(CampaignRecipient.queued_at.desc())
        .first()
    )
    if recipient is None:
        return False
    recipient.status = "replied"
    recipient.replied_at = current
    return True


def redeem_coupon(
    db: Session,
    coupon: Coupon,
    *,
    client_id: int | None = None,
    appointment_id: int | None = None,
    notes: str | None = None,
    redeemed_by: str | None = None,
) -> CouponRedemption:
    coupon = db.query(Coupon).filter(Coupon.id == coupon.id).with_for_update().one()
    validate_coupon(coupon, for_redemption=True)
    redemption = CouponRedemption(
        coupon_id=coupon.id,
        client_id=client_id,
        appointment_id=appointment_id,
        notes=notes,
        redeemed_by=redeemed_by,
    )
    coupon.redemption_count += 1
    db.add(redemption)
    db.commit()
    db.refresh(redemption)
    return redemption
