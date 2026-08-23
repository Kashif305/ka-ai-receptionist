from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.promotion import CampaignRecipient, Coupon, PromotionCampaign
from app.schemas.promotion import CampaignCreate, CampaignUpdate, CouponRedemptionInput, ScheduleInput
from app.services.promotion_media_service import LocalPromotionMediaStorage, MediaValidationError
from app.services.promotion_service import (
    EDITABLE_STATUSES,
    PromotionError,
    campaign_counts,
    preview_campaign,
    redeem_coupon,
    send_campaign,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard-promotions"])
CAMPAIGN_STATUSES = {
    "draft", "scheduled", "preparing", "sending", "completed",
    "partially_completed", "failed", "cancelled",
}


def _coupon_data(coupon: Coupon | None) -> dict | None:
    if coupon is None:
        return None
    return {
        "id": coupon.id,
        "code": coupon.code,
        "description": coupon.description,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "service_id": coupon.service_id,
        "starts_at": coupon.starts_at,
        "expires_at": coupon.expires_at,
        "redemption_limit": coupon.redemption_limit,
        "redemption_count": coupon.redemption_count,
        "is_active": coupon.is_active,
        "created_at": coupon.created_at,
        "updated_at": coupon.updated_at,
    }


def _recipient_data(recipient: CampaignRecipient) -> dict:
    return {
        "id": recipient.id,
        "client_id": recipient.client_id,
        "phone": recipient.phone_snapshot,
        "client_name": recipient.client_name_snapshot,
        "consent_source": recipient.consent_source_snapshot,
        "consent_at": recipient.consent_at_snapshot,
        "status": recipient.status,
        "queued_at": recipient.queued_at,
        "sent_at": recipient.sent_at,
        "delivered_at": recipient.delivered_at,
        "read_at": recipient.read_at,
        "replied_at": recipient.replied_at,
        "failed_at": recipient.failed_at,
        "failure_code": recipient.failure_code,
        "failure_message": recipient.failure_message,
    }


def _campaign_data(campaign: PromotionCampaign, *, include_recipients: bool = False) -> dict:
    result = {
        "id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "message_template_name": campaign.message_template_name,
        "message_template_language": campaign.message_template_language,
        "headline": campaign.headline,
        "body_text": campaign.body_text,
        "footer_text": campaign.footer_text,
        "flyer_url": campaign.flyer_url,
        "audience_type": campaign.audience_type,
        "audience_config": campaign.audience_config,
        "scheduled_at": campaign.scheduled_at,
        "started_at": campaign.started_at,
        "completed_at": campaign.completed_at,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "coupon": _coupon_data(campaign.coupon),
        "recipient_counts": campaign_counts(campaign),
    }
    if include_recipients:
        result["recipients"] = [_recipient_data(item) for item in sorted(campaign.recipients, key=lambda row: row.id)]
    return result


def _get_campaign(db: Session, campaign_id: int) -> PromotionCampaign:
    campaign = db.get(PromotionCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Promotion campaign not found")
    return campaign


def _set_coupon(campaign: PromotionCampaign, data) -> None:
    values = data.model_dump()
    values["code"] = values["code"].upper()
    if campaign.coupon:
        for key, value in values.items():
            setattr(campaign.coupon, key, value)
    else:
        campaign.coupon = Coupon(**values)


@router.get("/promotions")
def list_promotions(
    search: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(PromotionCampaign)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(PromotionCampaign.name.ilike(term), PromotionCampaign.headline.ilike(term)))
    if status:
        if status not in CAMPAIGN_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid campaign status")
        query = query.filter(PromotionCampaign.status == status)
    campaigns = query.order_by(PromotionCampaign.created_at.desc(), PromotionCampaign.id.desc()).offset(offset).limit(limit).all()
    return [_campaign_data(campaign) for campaign in campaigns]


@router.post("/promotions", status_code=201)
def create_promotion(payload: CampaignCreate, db: Session = Depends(get_db)):
    values = payload.model_dump(exclude={"coupon"})
    campaign = PromotionCampaign(**values, status="draft")
    if payload.coupon:
        _set_coupon(campaign, payload.coupon)
    db.add(campaign)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Coupon code already exists")
    db.refresh(campaign)
    return _campaign_data(campaign, include_recipients=True)


@router.get("/promotions/{campaign_id}")
def get_promotion(campaign_id: int, db: Session = Depends(get_db)):
    return _campaign_data(_get_campaign(db, campaign_id), include_recipients=True)


@router.patch("/promotions/{campaign_id}")
def update_promotion(campaign_id: int, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = _get_campaign(db, campaign_id)
    if campaign.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Campaign can only be edited while draft or scheduled")
    changes = payload.model_dump(exclude_unset=True, exclude={"coupon"})
    for key, value in changes.items():
        setattr(campaign, key, value)
    if "coupon" in payload.model_fields_set:
        if payload.coupon is None:
            campaign.coupon = None
        else:
            _set_coupon(campaign, payload.coupon)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Coupon code already exists")
    return _campaign_data(campaign, include_recipients=True)


@router.delete("/promotions/{campaign_id}", status_code=204)
def delete_promotion(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_campaign(db, campaign_id)
    if campaign.status != "draft" or any(item.queued_at for item in campaign.recipients):
        raise HTTPException(status_code=409, detail="Only an unattempted draft can be deleted; cancel it instead")
    db.delete(campaign)
    db.commit()
    return Response(status_code=204)


@router.post("/promotions/{campaign_id}/preview-audience")
def preview_promotion_audience(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_campaign(db, campaign_id)
    try:
        return preview_campaign(db, campaign).as_preview()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/promotions/{campaign_id}/send")
def send_promotion(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return send_campaign(db, _get_campaign(db, campaign_id))
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/promotions/{campaign_id}/schedule")
def schedule_promotion(campaign_id: int, payload: ScheduleInput, db: Session = Depends(get_db)):
    campaign = _get_campaign(db, campaign_id)
    if campaign.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Campaign cannot be scheduled in its current state")
    try:
        from app.services.promotion_service import validate_campaign
        validate_campaign(campaign)
    except PromotionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    local_value = payload.scheduled_at
    if local_value.tzinfo is None:
        local_value = local_value.replace(tzinfo=ZoneInfo(settings.business_timezone))
    scheduled_at = local_value.astimezone(timezone.utc)
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Scheduled time must be in the future")
    campaign.scheduled_at = scheduled_at
    campaign.status = "scheduled"
    db.commit()
    return _campaign_data(campaign)


@router.post("/promotions/{campaign_id}/cancel")
def cancel_promotion(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_campaign(db, campaign_id)
    if campaign.status not in {"draft", "scheduled"}:
        raise HTTPException(status_code=409, detail="Only draft or scheduled campaigns can be cancelled")
    campaign.status = "cancelled"
    db.commit()
    return _campaign_data(campaign)


@router.get("/promotions/{campaign_id}/recipients")
def list_promotion_recipients(
    campaign_id: int,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _get_campaign(db, campaign_id)
    query = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    if status:
        query = query.filter(CampaignRecipient.status == status)
    return [_recipient_data(item) for item in query.order_by(CampaignRecipient.id).offset(offset).limit(limit).all()]


@router.post("/promotions/media", status_code=201)
async def upload_promotion_media(request: Request, filename: str = Query(min_length=1, max_length=255)):
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.promotion_media_max_bytes:
        raise HTTPException(status_code=413, detail="Flyer exceeds the configured size limit")
    content = await request.body()
    try:
        return LocalPromotionMediaStorage().save(filename, content_type, content).__dict__
    except MediaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/coupons/{coupon_id}/redeem")
def redeem_coupon_endpoint(coupon_id: int, payload: CouponRedemptionInput, db: Session = Depends(get_db)):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    try:
        redemption = redeem_coupon(db, coupon, **payload.model_dump())
    except PromotionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "id": redemption.id,
        "coupon_id": redemption.coupon_id,
        "client_id": redemption.client_id,
        "appointment_id": redemption.appointment_id,
        "redeemed_at": redemption.redeemed_at,
        "redemption_count": coupon.redemption_count,
    }


@router.post("/coupons/{coupon_id}/deactivate")
def deactivate_coupon(coupon_id: int, db: Session = Depends(get_db)):
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    coupon.is_active = False
    db.commit()
    return _coupon_data(coupon)
