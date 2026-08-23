from dataclasses import dataclass
from datetime import timezone
from typing import Any

import requests

from app.core.config import settings


@dataclass(frozen=True)
class CampaignSendResult:
    accepted: bool
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    transient: bool = False


class WhatsAppCampaignProvider:
    def send_campaign_template(self, recipient, campaign, coupon=None) -> CampaignSendResult:
        if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
            return CampaignSendResult(False, error_code="credentials_unavailable", error_message="WhatsApp credentials are unavailable")
        if campaign.flyer_url and not campaign.flyer_url.startswith(("https://", "http://")):
            return CampaignSendResult(False, error_code="media_not_public", error_message="Flyer must have a publicly reachable URL for Meta")

        expiration = ""
        if coupon and coupon.expires_at:
            value = coupon.expires_at
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            expiration = value.astimezone(timezone.utc).date().isoformat()
        offer = campaign.headline or campaign.body_text
        if coupon:
            suffix = "%" if coupon.discount_type == "percentage" else ""
            offer = f"{coupon.discount_value:g}{suffix} off"
        variables = [
            recipient.client_name_snapshot or "Customer",
            campaign.headline or "",
            offer,
            coupon.code if coupon else "",
            expiration,
            settings.business_name,
        ]
        components: list[dict[str, Any]] = []
        if campaign.flyer_url:
            components.append({"type": "header", "parameters": [{"type": "image", "image": {"link": campaign.flyer_url}}]})
        components.append({"type": "body", "parameters": [{"type": "text", "text": value} for value in variables]})
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient.phone_snapshot,
            "type": "template",
            "template": {
                "name": campaign.message_template_name,
                "language": {"code": campaign.message_template_language},
                "components": components,
            },
        }
        url = f"https://graph.facebook.com/v23.0/{settings.whatsapp_phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=settings.whatsapp_request_timeout_seconds
            )
            data = response.json() if response.content else {}
        except requests.RequestException as exc:
            return CampaignSendResult(False, error_code="network_error", error_message=str(exc)[:500], transient=True)
        except ValueError:
            data = {}

        if 200 <= response.status_code < 300:
            message_id = ((data.get("messages") or [{}])[0]).get("id")
            if message_id:
                return CampaignSendResult(True, provider_message_id=message_id)
            return CampaignSendResult(False, error_code="missing_message_id", error_message="Meta accepted the request without a message ID")
        error = data.get("error") or {}
        return CampaignSendResult(
            False,
            error_code=str(error.get("code") or response.status_code),
            error_message=str(error.get("message") or "Meta rejected the campaign message")[:1000],
            transient=response.status_code >= 500 or response.status_code in {408, 429},
        )
