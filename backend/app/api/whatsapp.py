from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.message import Message
from app.services.ai_intent_service import classify_intent
from app.services.conversation_service import handle_customer_message
from app.services.whatsapp_service import send_whatsapp_smart_response


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


def normalize_incoming_message(message: dict) -> tuple[str | None, str | None]:
    message_type = message.get("type")

    if message_type == "text":
        body = message.get("text", {}).get("body")
        return body, body

    if message_type == "interactive":
        interactive = message.get("interactive", {})

        if "list_reply" in interactive:
            reply = interactive["list_reply"]
            command_id = reply.get("id", "")
            title = reply.get("title", "")

            if command_id.startswith("command_"):
                return command_id.replace("command_", ""), title

            return title, title

        if "button_reply" in interactive:
            reply = interactive["button_reply"]
            command_id = reply.get("id", "")
            title = reply.get("title", "")

            if command_id.startswith("command_"):
                return command_id.replace("command_", ""), title

            return title, title

    return None, None


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

        message_body, display_body = normalize_incoming_message(message)

        if not message_body:
            return {"status": "ignored_non_supported_message"}

        phone = contact["wa_id"]
        customer_name = contact["profile"]["name"]

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
            body=display_body or message_body,
        )

        db.add(new_message)
        db.commit()

        print(f"WHATSAPP SAVED | customer={customer.name} | message={display_body or message_body}")

        intent_result = classify_intent(message_body)

        routed_message = message_body
        if intent_result.command != "unknown" and intent_result.confidence >= 0.65:
            print(
                f"AI_INTENT | message={message_body} | intent={intent_result.intent} | command={intent_result.command} | confidence={intent_result.confidence}"
            )

            # Natural-language AI commands should start from the main menu layer,
            # not from a stale booking/reschedule step.
            if message_body.strip().lower() not in {"1", "2", "3", "4", "5", "6"}:
                state = (
                    db.query(ConversationState)
                    .filter(ConversationState.customer_id == customer.id)
                    .first()
                )
                if state:
                    state.current_state = "main_menu"
                    state.current_step = "awaiting_menu_choice"
                    state.context_json = "{}"
                    db.commit()

            routed_message = intent_result.command

        auto_reply = handle_customer_message(db, customer, routed_message)

        send_whatsapp_smart_response(phone, auto_reply)

    except Exception as exc:
        print("WEBHOOK PARSE ERROR:", exc)

    return {"status": "received"}
