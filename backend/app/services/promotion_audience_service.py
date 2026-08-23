from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.services.client_service import InvalidPhoneNumber, normalize_phone


QUALIFYING_APPOINTMENT_STATUSES = {"confirmed", "completed"}
SUPPORTED_INACTIVE_DAYS = {30, 60, 90}


@dataclass(frozen=True)
class AudienceRow:
    client_id: int
    name: str | None
    phone: str
    consent_source: str | None
    consent_at: datetime | None


@dataclass(frozen=True)
class AudienceResolution:
    eligible: list[AudienceRow]
    exclusions: dict[str, int]

    def as_preview(self, limit: int = 50) -> dict:
        return {
            "eligible_count": len(self.eligible),
            "excluded_count": sum(self.exclusions.values()),
            "exclusion_reasons": self.exclusions,
            "preview_rows": [row.__dict__ for row in self.eligible[:limit]],
        }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_activity(client: Client) -> datetime | None:
    values = [client.last_activity_at]
    values.extend(
        appointment.start_at
        for appointment in client.appointments
        if appointment.status in QUALIFYING_APPOINTMENT_STATUSES
    )
    normalized = [_utc(value) for value in values if value]
    return max(normalized, default=None)


def _matches_audience(client: Client, audience_type: str, config: dict, now: datetime) -> bool:
    if audience_type == "all_opted_in":
        return True
    if audience_type == "selected_clients":
        return client.id in {int(value) for value in config.get("client_ids", [])}
    if audience_type == "service_history":
        service_ids = {int(value) for value in config.get("service_ids", [])}
        return any(
            appointment.service_id in service_ids and appointment.status in QUALIFYING_APPOINTMENT_STATUSES
            for appointment in client.appointments
        )
    if audience_type == "inactive_days":
        days = int(config.get("days", 0))
        if days not in SUPPORTED_INACTIVE_DAYS:
            raise ValueError("inactive_days audience requires days of 30, 60, or 90")
        latest = _latest_activity(client)
        return latest is not None and latest < now - timedelta(days=days)
    if audience_type == "birthday_month":
        local_now = now.astimezone(ZoneInfo(settings.business_timezone))
        month = int(config.get("month") or local_now.month)
        if month not in range(1, 13):
            raise ValueError("birthday_month audience requires a month from 1 to 12")
        return client.birthday is not None and client.birthday.month == month
    if audience_type == "never_booked":
        return len(client.appointments) == 0
    raise ValueError("Unsupported audience type")


def resolve_campaign_audience(
    db: Session,
    audience_type: str,
    audience_config: dict | None,
    *,
    now: datetime | None = None,
) -> AudienceResolution:
    current = _utc(now or datetime.now(timezone.utc))
    config = audience_config or {}
    eligible: list[AudienceRow] = []
    exclusions: Counter[str] = Counter()
    seen_phones: set[str] = set()

    for client in db.query(Client).order_by(Client.id).all():
        if not _matches_audience(client, audience_type, config, current):
            continue
        if not client.is_active:
            exclusions["inactive_client"] += 1
            continue
        if not client.marketing_opt_in:
            reason = "opted_out" if client.marketing_opt_out_at else "no_recorded_consent"
            exclusions[reason] += 1
            continue
        try:
            phone = normalize_phone(client.phone)
        except InvalidPhoneNumber:
            exclusions["malformed_phone"] += 1
            continue
        if phone in seen_phones:
            exclusions["duplicate_phone"] += 1
            continue
        seen_phones.add(phone)
        eligible.append(
            AudienceRow(
                client_id=client.id,
                name=client.name,
                phone=phone,
                consent_source=client.marketing_opt_in_source,
                consent_at=client.marketing_opt_in_at,
            )
        )

    return AudienceResolution(eligible=eligible, exclusions=dict(sorted(exclusions.items())))
