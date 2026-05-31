from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.customer import Customer
from app.models.message import Message

router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["whatsapp"],
)


@router.get("")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.whatsapp_verify_token
    ):
        return hub_challenge

    raise HTTPException(status_code=403)


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

        contact = value["contacts"][0]
        message = value["messages"][0]

        phone = contact["wa_id"]
        customer_name = contact["profile"]["name"]

        customer = (
            db.query(Customer)
            .filter(Customer.phone == phone)
            .first()
        )

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
            body=message["text"]["body"],
        )

        db.add(new_message)
        db.commit()

        print(
            f"WHATSAPP SAVED | customer={customer.name} | message={message['text']['body']}"
        )

    except Exception as exc:
        print("WEBHOOK PARSE ERROR:", exc)

    return {"status": "received"}
