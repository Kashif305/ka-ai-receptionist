from datetime import datetime, timezone

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
from app.services.owner_summary_service import get_owner_summary_reply
from app.services.whatsapp_service import send_whatsapp_smart_response
from app.services.client_service import get_or_create_client, normalize_phone, touch_client
from app.services.promotion_service import mark_recent_campaign_reply, update_delivery_status
from app.services.marketing_consent_service import (
    CONSENT_PROMPT,
    begin_consent_prompt,
    clear_consent_wait,
    consent_reply,
    eligible_for_consent_prompt,
    is_awaiting_consent,
    is_natural_prompt_point,
    record_consent_decision,
)


router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
MARKETING_OPT_OUT_PHRASES = {"stop", "unsubscribe", "no offers", "stop offers"}


def is_marketing_opt_out(message: str) -> bool:
    return " ".join(message.casefold().split()) in MARKETING_OPT_OUT_PHRASES


def _process_statuses(db: Session, statuses: list[dict]) -> int:
    processed = 0
    for item in statuses:
        provider_id = item.get("id")
        status = item.get("status")
        if not provider_id or not status:
            continue
        try:
            occurred_at = datetime.fromtimestamp(int(item.get("timestamp", 0)), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            occurred_at = datetime.now(timezone.utc)
        errors = item.get("errors") or []
        error = errors[0] if errors else {}
        if update_delivery_status(
            db,
            provider_id,
            status,
            occurred_at,
            failure_code=str(error.get("code")) if error.get("code") is not None else None,
            failure_message=error.get("title") or error.get("message"),
        ):
            processed += 1
    return processed


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

        if "statuses" in value:
            return {"status": "processed", "updated": _process_statuses(db, value["statuses"])}

        if "messages" not in value:
            return {"status": "ignored"}

        contact = value["contacts"][0]
        message = value["messages"][0]

        message_body, display_body = normalize_incoming_message(message)

        if not message_body:
            return {"status": "ignored_non_supported_message"}

        phone = normalize_phone(contact["wa_id"])
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

        client, _ = get_or_create_client(db, phone, customer_name)
        touch_client(db, client)

        if message.get("id") and db.query(Message).filter(
            Message.external_message_id == message["id"]
        ).first():
            db.rollback()
            return {"status": "duplicate_ignored"}

        new_message = Message(
            customer_id=customer.id,
            channel="whatsapp",
            direction="inbound",
            external_message_id=message["id"],
            body=display_body or message_body,
        )

        db.add(new_message)
        state = db.query(ConversationState).filter(ConversationState.customer_id == customer.id).first()
        if state:
            state.client_id = client.id
        mark_recent_campaign_reply(db, client.id)
        db.commit()

        print(f"WHATSAPP SAVED | customer={customer.name} | message={display_body or message_body}")

        if is_marketing_opt_out(message_body):
            client.marketing_opt_in = False
            client.marketing_opt_in_at = None
            client.marketing_opt_out_at = datetime.now(timezone.utc)
            client.marketing_opt_in_source = "whatsapp"
            if is_awaiting_consent(state):
                clear_consent_wait(state)
            confirmation = "You have been unsubscribed from promotional offers. You can still use this chat for appointments."
            send_whatsapp_smart_response(phone, confirmation)
            db.add(Message(customer_id=customer.id, channel="whatsapp", direction="outbound", body=confirmation))
            db.commit()
            return {"status": "marketing_opt_out_confirmed"}

        if is_awaiting_consent(state):
            decision = consent_reply(message_body)
            if decision is not None:
                record_consent_decision(client, decision)
                clear_consent_wait(state)
                confirmation = (
                    "Thanks — you're signed up for occasional offers."
                    if decision
                    else "No problem — you won't receive promotional offers."
                )
                send_whatsapp_smart_response(phone, confirmation)
                db.add(Message(customer_id=customer.id, channel="whatsapp", direction="outbound", body=confirmation))
                db.commit()
                return {"status": "marketing_consent_recorded", "marketing_opt_in": decision}

            # A non-consent reply resumes normal transactional handling and is
            # never coerced into a marketing decision.
            clear_consent_wait(state)
            db.commit()

        starter_words = {"hi", "hey", "hello", "start", "menu", "samina", "samina receptionist"}

        if message_body.strip().lower() in starter_words:
            intent_result = None
            routed_message = message_body
        else:
            intent_result = classify_intent(message_body)
            routed_message = message_body

        if intent_result and intent_result.command != "unknown" and intent_result.confidence >= 0.65:
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

        owner_reply = get_owner_summary_reply(db, phone, message_body)
        if owner_reply:
            send_whatsapp_smart_response(phone, owner_reply)
            db.add(Message(customer_id=customer.id, channel="whatsapp", direction="outbound", body=owner_reply))
            db.commit()
            return {"status": "owner_summary_sent"}

        auto_reply = handle_customer_message(db, customer, routed_message)

        state = db.query(ConversationState).filter(ConversationState.customer_id == customer.id).first()
        if (
            eligible_for_consent_prompt(client, state)
            and is_natural_prompt_point(routed_message, auto_reply)
        ):
            begin_consent_prompt(client, state)
            auto_reply = f"{auto_reply}\n\n{CONSENT_PROMPT}"

        send_whatsapp_smart_response(phone, auto_reply)
        db.add(Message(customer_id=customer.id, channel="whatsapp", direction="outbound", body=auto_reply))
        db.commit()

    except Exception as exc:
        print("WEBHOOK PARSE ERROR:", exc)

    return {"status": "received"}
