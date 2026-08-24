import tempfile
import unittest
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.dashboard_promotions import cancel_promotion, delete_promotion, schedule_promotion, update_promotion
from app.api.whatsapp import is_marketing_opt_out, receive_whatsapp_webhook
from app.core.config import settings
from app.core.database import Base
from app.integrations.whatsapp_cloud import CampaignSendResult
from app.integrations.whatsapp_cloud import WhatsAppCampaignProvider
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.promotion import CampaignRecipient, Coupon, PromotionCampaign
from app.models.service import Service
from app.schemas.promotion import CampaignUpdate, CouponInput, ScheduleInput
from app.services.promotion_audience_service import resolve_campaign_audience
from app.services.promotion_media_service import LocalPromotionMediaStorage, MediaValidationError
from app.services.promotion_service import (
    PromotionError,
    prepare_campaign,
    process_due_campaigns,
    redeem_coupon,
    send_campaign,
    update_delivery_status,
    validate_campaign,
)


class FakeProvider:
    def __init__(self, failures: set[int] | None = None, transient: bool = False):
        self.failures = failures or set()
        self.transient = transient
        self.calls = []

    def send_campaign_template(self, recipient, campaign, coupon=None):
        self.calls.append(recipient.client_id)
        if recipient.client_id in self.failures:
            return CampaignSendResult(
                False,
                error_code="temporary" if self.transient else "rejected",
                error_message="provider failure",
                transient=self.transient,
            )
        return CampaignSendResult(True, provider_message_id=f"wamid.{campaign.id}.{recipient.client_id}")


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def client(self, phone: str, *, consent=True, active=True, opted_out=False, birthday=None, activity=None):
        client = Client(
            name=f"Client {phone}",
            phone=phone,
            is_active=active,
            marketing_opt_in=consent,
            marketing_opt_in_at=datetime(2026, 1, 1, tzinfo=timezone.utc) if consent else None,
            marketing_opt_in_source="whatsapp" if consent else None,
            marketing_opt_out_at=datetime(2026, 2, 1, tzinfo=timezone.utc) if opted_out else None,
            birthday=birthday,
            last_activity_at=activity,
        )
        self.db.add(client)
        self.db.flush()
        return client

    def campaign(self, audience_type="all_opted_in", config=None, **changes):
        values = {
            "name": "Summer offer",
            "status": "draft",
            "message_template_name": "summer_offer",
            "message_template_language": "en_US",
            "headline": "Save today",
            "body_text": "A special offer for you",
            "audience_type": audience_type,
            "audience_config": config,
        }
        values.update(changes)
        campaign = PromotionCampaign(**values)
        self.db.add(campaign)
        self.db.commit()
        return campaign

    def test_campaign_draft_creation_and_template_validation(self):
        campaign = self.campaign()
        self.assertEqual(campaign.status, "draft")
        campaign.message_template_name = ""
        with self.assertRaisesRegex(PromotionError, "template name"):
            validate_campaign(campaign)

    def test_template_exact_api_name_language_and_provider_failure_are_preserved(self):
        recipient = Mock(phone_snapshot="15550000000", client_name_snapshot="Ayesha")
        campaign = self.campaign(name="Kids back to school", message_template_name="kids_back_to_school", message_template_language="en_US")
        response = Mock(status_code=400, content=b"error")
        response.json.return_value = {"error": {"code": 132001, "message": "Template name does not exist in the translation"}}
        with patch.object(settings, "whatsapp_phone_number_id", "phone-id"), patch.object(settings, "whatsapp_access_token", "secret"), patch("app.integrations.whatsapp_cloud.requests.post", return_value=response) as post:
            result = WhatsAppCampaignProvider().send_campaign_template(recipient, campaign)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["template"]["name"], "kids_back_to_school")
        self.assertEqual(payload["template"]["language"]["code"], "en_US")
        self.assertNotEqual(payload["template"]["name"], campaign.name)
        self.assertEqual((result.accepted, result.error_code, result.error_message), (False, "132001", "Template name does not exist in the translation"))

    def test_invalid_template_configuration_fails_before_provider(self):
        self.client("5550001009")
        provider = FakeProvider()
        campaign = self.campaign(message_template_name="Kids back to school")
        with self.assertRaisesRegex(PromotionError, "exact Meta API name"):
            send_campaign(self.db, campaign, provider)
        self.assertEqual(provider.calls, [])

    def test_meta_132001_is_visible_and_never_counted_as_delivery(self):
        self.client("5550001010")
        class MissingTemplateProvider:
            def send_campaign_template(self, recipient, campaign, coupon=None):
                return CampaignSendResult(False, error_code="132001", error_message="Template name does not exist in the translation")
        campaign = self.campaign()
        result = send_campaign(self.db, campaign, MissingTemplateProvider())
        recipient = self.db.query(CampaignRecipient).one()
        self.assertEqual((result["submitted"], result["failed"], campaign.status), (0, 1, "failed"))
        self.assertEqual((recipient.status, recipient.failure_code, recipient.failure_message), ("failed", "132001", "Template name does not exist in the translation"))
        self.assertIsNone(recipient.delivered_at)

    def test_update_cancellation_deletion_and_schedule_restrictions(self):
        campaign = self.campaign()
        updated = update_promotion(campaign.id, CampaignUpdate(headline="Updated"), self.db)
        self.assertEqual(updated["headline"], "Updated")
        with self.assertRaises(HTTPException):
            schedule_promotion(
                campaign.id,
                ScheduleInput(scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1)),
                self.db,
            )
        cancelled = cancel_promotion(campaign.id, self.db)
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(HTTPException):
            update_promotion(campaign.id, CampaignUpdate(headline="Too late"), self.db)
        with self.assertRaises(HTTPException):
            delete_promotion(campaign.id, self.db)
        draft = self.campaign(name="Disposable")
        response = delete_promotion(draft.id, self.db)
        self.assertEqual(response.status_code, 204)

    def test_audience_global_consent_and_phone_exclusions(self):
        eligible = self.client("5550001001")
        self.client("5550001002", consent=False)
        self.client("5550001003", consent=False, opted_out=True)
        self.client("5550001004", active=False)
        self.client("bad-phone")
        duplicate = self.client("+1 (555) 000-1001")
        resolution = resolve_campaign_audience(self.db, "all_opted_in", None)
        self.assertEqual([row.client_id for row in resolution.eligible], [eligible.id])
        self.assertEqual(resolution.exclusions, {
            "duplicate_phone": 1,
            "inactive_client": 1,
            "malformed_phone": 1,
            "no_recorded_consent": 1,
            "opted_out": 1,
        })
        self.assertNotEqual(eligible.id, duplicate.id)

    def test_selected_clients_still_excludes_nonconsenting(self):
        eligible = self.client("5550001101")
        excluded = self.client("5550001102", consent=False)
        result = resolve_campaign_audience(
            self.db, "selected_clients", {"client_ids": [eligible.id, excluded.id]}
        )
        self.assertEqual([row.client_id for row in result.eligible], [eligible.id])
        self.assertEqual(result.exclusions["no_recorded_consent"], 1)

    def test_service_history_uses_confirmed_and_completed_only(self):
        confirmed = self.client("5550001201")
        cancelled = self.client("5550001202")
        service = Service(name="Threading", duration_minutes=20, active=True)
        self.db.add(service)
        self.db.flush()
        for client, status in ((confirmed, "confirmed"), (cancelled, "cancelled")):
            self.db.add(Appointment(
                customer_id=self._customer_id(client.phone), client_id=client.id, service_id=service.id,
                start_at=datetime(2026, 1, 1), end_at=datetime(2026, 1, 1, 0, 20), status=status,
            ))
        self.db.flush()
        result = resolve_campaign_audience(self.db, "service_history", {"service_ids": [service.id]})
        self.assertEqual([row.client_id for row in result.eligible], [confirmed.id])

    def _customer_id(self, phone):
        from app.models.customer import Customer
        customer = Customer(name="Customer", phone=f"c-{phone}")
        self.db.add(customer)
        self.db.flush()
        return customer.id

    def test_inactive_birthday_and_never_booked_audiences(self):
        old = self.client("5550001301", activity=datetime(2025, 1, 1), birthday=date(1990, 7, 2))
        never = self.client("5550001302", birthday=date(1992, 7, 8))
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        inactive_by_threshold = {
            days: resolve_campaign_audience(self.db, "inactive_days", {"days": days}, now=now)
            for days in (30, 60, 90)
        }
        birthdays = resolve_campaign_audience(self.db, "birthday_month", {"month": 7}, now=now)
        never_booked = resolve_campaign_audience(self.db, "never_booked", None, now=now)
        for inactive in inactive_by_threshold.values():
            self.assertEqual([row.client_id for row in inactive.eligible], [old.id])
        self.assertEqual({row.client_id for row in birthdays.eligible}, {old.id, never.id})
        self.assertEqual({row.client_id for row in never_booked.eligible}, {old.id, never.id})
        with self.assertRaises(ValueError):
            resolve_campaign_audience(self.db, "inactive_days", {"days": 45}, now=now)

    def test_preview_and_preparation_use_same_resolution_without_duplicates(self):
        client = self.client("5550001401")
        campaign = self.campaign()
        preview = resolve_campaign_audience(self.db, campaign.audience_type, campaign.audience_config)
        prepared_resolution, recipients = prepare_campaign(self.db, campaign)
        _, repeated = prepare_campaign(self.db, campaign)
        self.assertEqual(preview.eligible, prepared_resolution.eligible)
        self.assertEqual([row.client_id for row in recipients], [client.id])
        self.assertEqual(len(repeated), 1)
        self.assertEqual(self.db.query(CampaignRecipient).count(), 1)

    def test_send_partial_failure_provider_ids_and_idempotency(self):
        first = self.client("5550001501")
        second = self.client("5550001502")
        campaign = self.campaign()
        provider = FakeProvider(failures={second.id})
        result = send_campaign(self.db, campaign, provider)
        self.assertEqual(result["status"], "partially_completed")
        self.assertEqual((result["submitted"], result["failed"]), (1, 1))
        accepted = self.db.query(CampaignRecipient).filter_by(client_id=first.id).one()
        self.assertEqual(accepted.status, "submitted")
        self.assertTrue(accepted.provider_message_id.startswith("wamid."))
        with self.assertRaises(PromotionError):
            send_campaign(self.db, campaign, provider)
        self.assertEqual(len(provider.calls), 2)

    def test_no_eligible_recipients_fails_without_provider_call(self):
        self.client("5550001601", consent=False)
        provider = FakeProvider()
        with self.assertRaisesRegex(PromotionError, "no eligible"):
            send_campaign(self.db, self.campaign(), provider)
        self.assertEqual(provider.calls, [])

    def test_transient_provider_failure_is_recorded_without_blind_retry(self):
        client = self.client("5550001651")
        provider = FakeProvider(failures={client.id}, transient=True)
        campaign = self.campaign()
        result = send_campaign(self.db, campaign, provider)
        recipient = self.db.query(CampaignRecipient).one()
        self.assertEqual((result["status"], recipient.status, recipient.failure_code), ("failed", "failed", "temporary"))
        self.assertEqual(provider.calls, [client.id])

    def test_scheduled_campaign_claim_is_idempotent(self):
        self.client("5550001701")
        due = self.campaign(
            status="scheduled", scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        provider = FakeProvider()
        first = process_due_campaigns(self.db, provider)
        second = process_due_campaigns(self.db, provider)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(due.status, "completed")
        self.assertEqual(len(provider.calls), 1)

    def test_delivery_webhooks_are_idempotent_and_do_not_regress(self):
        client = self.client("5550001801")
        campaign = self.campaign()
        send_campaign(self.db, campaign, FakeProvider())
        recipient = self.db.query(CampaignRecipient).filter_by(client_id=client.id).one()
        now = datetime.now(timezone.utc)
        self.assertTrue(update_delivery_status(self.db, recipient.provider_message_id, "delivered", now))
        self.assertTrue(update_delivery_status(self.db, recipient.provider_message_id, "sent", now - timedelta(minutes=1)))
        self.assertEqual(recipient.status, "delivered")
        self.assertTrue(update_delivery_status(self.db, recipient.provider_message_id, "read", now))
        self.assertEqual(recipient.status, "read")
        self.assertFalse(update_delivery_status(self.db, "unknown", "sent", now))

    def test_failed_webhook_records_error(self):
        client = self.client("5550001901")
        campaign = self.campaign()
        send_campaign(self.db, campaign, FakeProvider())
        recipient = self.db.query(CampaignRecipient).filter_by(client_id=client.id).one()
        update_delivery_status(
            self.db, recipient.provider_message_id, "failed", datetime.now(timezone.utc),
            failure_code="131047", failure_message="Re-engagement message",
        )
        self.assertEqual((recipient.status, recipient.failure_code), ("failed", "131047"))

    def test_coupon_validation_unique_code_redemption_limit_and_deactivation(self):
        with self.assertRaises(ValidationError):
            CouponInput(code="TOO-MUCH", discount_type="percentage", discount_value=Decimal("101"))
        with self.assertRaises(ValidationError):
            CouponInput(code="ZERO", discount_type="fixed_amount", discount_value=Decimal("0"))
        with self.assertRaises(ValidationError):
            CouponInput(
                code="DATES", discount_type="percentage", discount_value=Decimal("20"),
                starts_at=datetime(2026, 2, 2), expires_at=datetime(2026, 2, 1),
            )
        service = Service(name="Facial", duration_minutes=60, active=True)
        self.db.add(service)
        self.db.flush()
        coupon = Coupon(
            code="SAVE5", discount_type="fixed_amount", discount_value=5,
            service_id=service.id, redemption_limit=1, is_active=True,
        )
        self.db.add(coupon)
        self.db.commit()
        self.assertEqual(coupon.service_id, service.id)
        redemption = redeem_coupon(self.db, coupon, notes="Owner redemption")
        self.assertEqual(redemption.coupon_id, coupon.id)
        with self.assertRaisesRegex(PromotionError, "limit"):
            redeem_coupon(self.db, coupon)
        coupon.is_active = False
        with self.assertRaisesRegex(PromotionError, "inactive"):
            redeem_coupon(self.db, coupon)
        duplicate = Coupon(code="SAVE5", discount_type="fixed_amount", discount_value=5)
        self.db.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_expired_coupon_cannot_be_redeemed(self):
        coupon = Coupon(
            code="OLD", discount_type="percentage", discount_value=20, is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        self.db.add(coupon)
        self.db.commit()
        with self.assertRaisesRegex(PromotionError, "expired"):
            redeem_coupon(self.db, coupon)

    def test_coupon_immediate_future_expiration_and_new_york_input_semantics(self):
        immediate = Coupon(code="NOW", discount_type="percentage", discount_value=20, is_active=True)
        validate_campaign(self.campaign(coupon=immediate))
        local = CouponInput(code="LOCAL", discount_type="percentage", discount_value=20, starts_at=datetime(2026, 8, 23, 9), expires_at=datetime(2026, 8, 26, 23, 59))
        self.assertEqual(local.starts_at, datetime(2026, 8, 23, 13, tzinfo=timezone.utc))
        self.assertEqual(local.expires_at, datetime(2026, 8, 27, 3, 59, tzinfo=timezone.utc))
        future = Coupon(code="FUTURE", discount_type="percentage", discount_value=20, is_active=True, starts_at=datetime.now(timezone.utc) + timedelta(hours=1))
        with self.assertRaisesRegex(PromotionError, "not active yet"):
            validate_campaign(self.campaign(coupon=future))
        expired = Coupon(code="EXPIRED", discount_type="percentage", discount_value=20, is_active=True, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        with self.assertRaisesRegex(PromotionError, "expired"):
            validate_campaign(self.campaign(coupon=expired))

    def test_media_validation_sanitizes_and_rejects_bad_content(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalPromotionMediaStorage(directory, "/media/promotions")
            stored = storage.save("../../Summer Flyer.PNG", "image/png", b"\x89PNG\r\n\x1a\ncontent")
            self.assertTrue(stored.filename.startswith("Summer-Flyer-"))
            self.assertEqual(Path(directory, stored.filename).parent.resolve(), Path(directory).resolve())
            with self.assertRaises(MediaValidationError):
                storage.save("flyer.exe", "application/octet-stream", b"data")
            with self.assertRaises(MediaValidationError):
                storage.save("flyer.jpg", "image/jpeg", b"not-a-jpeg")
            old_limit = settings.promotion_media_max_bytes
            settings.promotion_media_max_bytes = 4
            try:
                with self.assertRaises(MediaValidationError):
                    storage.save("flyer.png", "image/png", b"\x89PNG\r\n\x1a\n")
            finally:
                settings.promotion_media_max_bytes = old_limit

    def test_opt_out_matching_is_conservative(self):
        for phrase in ("STOP", " unsubscribe ", "No   Offers", "stop offers"):
            self.assertTrue(is_marketing_opt_out(phrase))
        self.assertFalse(is_marketing_opt_out("Please stop moving my appointment"))
        self.assertFalse(is_marketing_opt_out("stop by tomorrow"))

    def test_opt_out_webhook_updates_canonical_client_and_preserves_message(self):
        from unittest.mock import patch
        from app.models.customer import Customer
        from app.models.message import Message

        customer = Customer(name="Amina", phone="15550002001", whatsapp_id="15550002001")
        client = Client(name="Amina", phone="15550002001", is_active=True, marketing_opt_in=True)
        self.db.add_all([customer, client])
        self.db.commit()

        class Request:
            async def json(self):
                return {"entry": [{"changes": [{"value": {
                    "contacts": [{"wa_id": "15550002001", "profile": {"name": "Amina"}}],
                    "messages": [{"id": "inbound-stop", "type": "text", "text": {"body": " STOP "}}],
                }}]}]}

        with patch("app.api.whatsapp.send_whatsapp_smart_response"):
            result = asyncio.run(receive_whatsapp_webhook(Request(), self.db))
        self.db.refresh(client)
        self.assertEqual(result["status"], "marketing_opt_out_confirmed")
        self.assertFalse(client.marketing_opt_in)
        self.assertIsNotNone(client.marketing_opt_out_at)
        self.assertEqual(self.db.query(Message).filter_by(direction="inbound").count(), 1)


if __name__ == "__main__":
    unittest.main()
