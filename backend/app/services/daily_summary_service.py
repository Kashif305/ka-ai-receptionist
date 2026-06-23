import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.owner_summary_service import get_owner_summary_reply
from app.services.whatsapp_service import send_whatsapp_text


BUSINESS_TZ = ZoneInfo("America/New_York")
_SENT_KEYS: set[str] = set()


def _owner_numbers() -> list[str]:
    return [
        phone.strip().replace("+", "")
        for phone in settings.owner_phone_numbers.split(",")
        if phone.strip()
    ]


def _should_send_now(now: datetime) -> bool:
    try:
        target_hour, target_minute = settings.daily_summary_time.split(":")
        return now.hour == int(target_hour) and now.minute == int(target_minute)
    except Exception:
        return False


async def daily_summary_loop():
    print("DAILY_SUMMARY_LOOP_STARTED")

    while True:
        try:
            if not settings.daily_summary_enabled:
                await asyncio.sleep(60)
                continue

            now = datetime.now(BUSINESS_TZ)

            if _should_send_now(now):
                send_key = now.strftime("%Y-%m-%d-%H-%M")

                if send_key not in _SENT_KEYS:
                    db = SessionLocal()
                    try:
                        for owner_phone in _owner_numbers():
                            summary = get_owner_summary_reply(
                                db,
                                owner_phone,
                                "tomorrow's appointments",
                            )

                            if summary:
                                send_whatsapp_text(owner_phone, summary)

                        _SENT_KEYS.add(send_key)

                    finally:
                        db.close()

            await asyncio.sleep(60)

        except Exception as exc:
            print("DAILY_SUMMARY_ERROR:", exc)
            await asyncio.sleep(60)
