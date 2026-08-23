from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PromotionCampaign(Base):
    __tablename__ = "promotion_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", server_default="draft", index=True)
    message_template_name: Mapped[str] = mapped_column(String(160), default="", server_default="")
    message_template_language: Mapped[str] = mapped_column(String(16), default="", server_default="")
    headline: Mapped[str | None] = mapped_column(String(240), nullable=True)
    body_text: Mapped[str] = mapped_column(Text)
    footer_text: Mapped[str | None] = mapped_column(String(240), nullable=True)
    flyer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audience_type: Mapped[str] = mapped_column(String(32), index=True)
    audience_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    coupon = relationship("Coupon", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    recipients = relationship("CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan")


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotion_campaigns.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(24))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redemption_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redemption_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaign = relationship("PromotionCampaign", back_populates="coupon")
    service = relationship("Service")
    redemptions = relationship("CouponRedemption", back_populates="coupon")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "client_id", name="uq_campaign_recipient_client"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("promotion_campaigns.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    phone_snapshot: Mapped[str] = mapped_column(String(32))
    client_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    consent_source_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_at_snapshot: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaign = relationship("PromotionCampaign", back_populates="recipients")
    client = relationship("Client")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"), index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    redeemed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    coupon = relationship("Coupon", back_populates="redemptions")
    client = relationship("Client")
    appointment = relationship("Appointment")
