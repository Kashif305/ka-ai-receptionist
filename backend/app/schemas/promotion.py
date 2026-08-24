import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator


CampaignStatus = Literal[
    "draft", "scheduled", "preparing", "sending", "completed",
    "partially_completed", "failed", "cancelled",
]
AudienceType = Literal[
    "all_opted_in", "selected_clients", "service_history", "inactive_days",
    "birthday_month", "never_booked",
]
DiscountType = Literal["percentage", "fixed_amount"]


class CouponInput(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    discount_type: DiscountType
    discount_value: Decimal
    service_id: int | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    redemption_limit: int | None = Field(default=None, gt=0)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = "".join(value.strip().upper().split())
        if not normalized or not all(char.isalnum() or char in {"-", "_"} for char in normalized):
            raise ValueError("Coupon code may contain only letters, numbers, hyphens, and underscores")
        return normalized

    @field_validator("starts_at", "expires_at")
    @classmethod
    def business_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=ZoneInfo("America/New_York"))
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_offer(self):
        if self.discount_value <= 0:
            raise ValueError("Discount value must be greater than zero")
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.starts_at and self.expires_at:
            start = self.starts_at.replace(tzinfo=self.starts_at.tzinfo or timezone.utc)
            expiration = self.expires_at.replace(tzinfo=self.expires_at.tzinfo or timezone.utc)
            if expiration.astimezone(timezone.utc) < start.astimezone(timezone.utc):
                raise ValueError("Expiration cannot precede the start date")
        return self


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    headline: str | None = Field(default=None, max_length=240)
    body_text: str = Field(min_length=1)
    footer_text: str | None = Field(default=None, max_length=240)
    message_template_name: str = Field(default="", max_length=160)
    message_template_language: str = Field(default="", max_length=16)
    audience_type: AudienceType
    audience_config: dict[str, Any] | None = None
    flyer_url: str | None = Field(default=None, max_length=500)
    coupon: CouponInput | None = None

    @field_validator("message_template_name")
    @classmethod
    def template_api_name(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[a-z0-9_]+", value):
            raise ValueError("Meta template API name may contain only lowercase letters, numbers, and underscores")
        return value

    @field_validator("message_template_language")
    @classmethod
    def template_language_code(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", value):
            raise ValueError("Meta template language must be a code such as en_US")
        return value


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    headline: str | None = Field(default=None, max_length=240)
    body_text: str | None = Field(default=None, min_length=1)
    footer_text: str | None = Field(default=None, max_length=240)
    message_template_name: str | None = Field(default=None, max_length=160)
    message_template_language: str | None = Field(default=None, max_length=16)
    audience_type: AudienceType | None = None
    audience_config: dict[str, Any] | None = None
    flyer_url: str | None = Field(default=None, max_length=500)
    coupon: CouponInput | None = None


class ScheduleInput(BaseModel):
    scheduled_at: datetime


class CouponRedemptionInput(BaseModel):
    client_id: int | None = None
    appointment_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)
    redeemed_by: str | None = Field(default=None, max_length=120)
