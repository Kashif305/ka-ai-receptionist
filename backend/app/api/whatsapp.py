from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.customer import Customer
from app.models.message import Message
from app.services.conversation_service import handle_customer_message
from app.services.whatsapp_service import send_whatsapp_text


router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=str(hub_challenge or ""), media_type="text/plain")

    raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")


@router.post("")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        if "messages" not in value:
            return {"status": "ignored"}

        contact = value["contacts"][0]
        message = value["messages"][0]

        if message.get("type") != "text":
            return {"status": "ignored_non_text"}

        phone = contact["wa_id"]
        customer_name = contact["profile"]["name"]
        message_body = message["text"]["body"]

        customer = db.query(Customer).filter(Customer.phone == phone).first()

        if not customer:
            customer = Customer(
                name=customer_name,
                phone=phone,
                whatsapp_id=phone,
                notes="Auto-created from WhatsApp",
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)

        new_message = Message(
            customer_id=customer.id,
            channel="whatsapp",
            direction="inbound",
            external_message_id=message["id"],
            body=message_body,
        )

        db.add(new_message)
        db.commit()

        print(f"WHATSAPP SAVED | customer={customer.name} | message={message_body}")

        auto_reply = handle_customer_message(db, customer, message_body)

        send_whatsapp_text(phone, auto_reply)

    except Exception as exc:
        print("WEBHOOK PARSE ERROR:", exc)

    return {"status": "received"}
