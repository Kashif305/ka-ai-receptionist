from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings


router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge

    raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")


@router.post("")
async def receive_whatsapp_webhook(request: Request):
    payload = await request.json()

    print("WHATSAPP_WEBHOOK_RECEIVED:")
    print(payload)

    return {"status": "received"}
