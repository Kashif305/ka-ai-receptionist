from datetime import datetime, timedelta, timezone

from app.models.client import Client
from app.models.conversation_state import ConversationState


POSITIVE_CONSENT_PHRASES = {
    "yes",
    "i agree",
    "accept",
    "yes please",
    "sure",
    "send me offers",
}
NEGATIVE_CONSENT_PHRASES = {"no", "decline", "no thanks", "not interested"}
CONSENT_PROMPT = (
    "Would you like to receive occasional offers, discounts, and promotions from "
    "Samina Beauty Salon?\n\nPlease reply “Yes, I agree” or “No thanks”."
)
CONSENT_REASK_INTERVAL = timedelta(days=90)
AWAITING_CONSENT_STATE = "marketing_consent"
AWAITING_CONSENT_STEP = "awaiting_marketing_consent"


def normalize_consent_reply(message: str) -> str:
    return " ".join(message.casefold().split())


def consent_reply(message: str) -> bool | None:
    normalized = normalize_consent_reply(message)
    if normalized in POSITIVE_CONSENT_PHRASES:
        return True
    if normalized in NEGATIVE_CONSENT_PHRASES:
        return False
    return None


def consent_status(client: Client) -> str:
    if client.marketing_opt_in:
        return "opted_in"
    if client.marketing_opt_out_at is not None:
        return "opted_out"
    return "not_asked"


def is_awaiting_consent(state: ConversationState | None) -> bool:
    return bool(
        state
        and state.current_state == AWAITING_CONSENT_STATE
        and state.current_step == AWAITING_CONSENT_STEP
    )


def eligible_for_consent_prompt(
    client: Client | None,
    state: ConversationState | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not client or not client.is_active or not state or consent_status(client) != "not_asked":
        return False
    current = now or datetime.now(timezone.utc)
    asked_at = client.marketing_consent_asked_at
    if asked_at is None:
        return True
    if asked_at.tzinfo is None:
        asked_at = asked_at.replace(tzinfo=timezone.utc)
    return current - asked_at.astimezone(timezone.utc) >= CONSENT_REASK_INTERVAL


def is_natural_prompt_point(routed_message: str, reply: str) -> bool:
    return reply.startswith("You're booked ✅") or routed_message.strip() == "4"


def begin_consent_prompt(client: Client, state: ConversationState, now: datetime | None = None) -> None:
    client.marketing_consent_asked_at = now or datetime.now(timezone.utc)
    state.current_state = AWAITING_CONSENT_STATE
    state.current_step = AWAITING_CONSENT_STEP
    state.context_json = "{}"


def clear_consent_wait(state: ConversationState) -> None:
    state.current_state = "main_menu"
    state.current_step = "awaiting_menu_choice"
    state.context_json = "{}"


def record_consent_decision(client: Client, accepted: bool, now: datetime | None = None) -> None:
    decided_at = now or datetime.now(timezone.utc)
    client.marketing_opt_in = accepted
    client.marketing_opt_in_source = "whatsapp"
    if accepted:
        client.marketing_opt_in_at = decided_at
        client.marketing_opt_out_at = None
    else:
        client.marketing_opt_in_at = None
        client.marketing_opt_out_at = decided_at
