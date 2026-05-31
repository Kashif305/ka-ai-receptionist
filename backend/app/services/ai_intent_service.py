import json
import re
from typing import Literal

from pydantic import BaseModel

from app.core.config import settings


class IntentResult(BaseModel):
    intent: Literal[
        "book",
        "reschedule",
        "cancel",
        "services",
        "staff",
        "my_appointment",
        "unknown",
    ]
    command: Literal["1", "2", "3", "4", "5", "6", "unknown"]
    confidence: float


def _fallback_intent(text: str) -> IntentResult:
    lowered = text.strip().lower()

    if lowered in {"1", "2", "3", "4", "5", "6"}:
        return IntentResult(intent="unknown", command=lowered, confidence=1.0)

    if any(word in lowered for word in ["cancel", "delete"]):
        return IntentResult(intent="cancel", command="3", confidence=0.8)

    if any(word in lowered for word in ["reschedule", "move", "change"]):
        return IntentResult(intent="reschedule", command="2", confidence=0.8)

    if any(word in lowered for word in ["when", "my appointment", "status", "upcoming"]):
        return IntentResult(intent="my_appointment", command="6", confidence=0.8)

    if any(word in lowered for word in ["book", "appointment", "schedule", "reserve"]):
        return IntentResult(intent="book", command="1", confidence=0.8)

    if any(word in lowered for word in ["service", "services", "price", "pricing", "cost"]):
        return IntentResult(intent="services", command="4", confidence=0.8)

    if any(word in lowered for word in ["staff", "human", "person", "help"]):
        return IntentResult(intent="staff", command="5", confidence=0.8)

    return IntentResult(intent="unknown", command="unknown", confidence=0.0)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")

    return json.loads(match.group(0))


def classify_intent(message: str) -> IntentResult:
    text = message.strip()

    # First use simple deterministic fallback for obvious cases.
    fallback = _fallback_intent(text)
    if fallback.command != "unknown" and fallback.confidence >= 0.8:
        return fallback

    if not settings.ai_intent_enabled or not settings.openai_api_key:
        return IntentResult(intent="unknown", command="unknown", confidence=0.0)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        response = client.responses.create(
            model=settings.openai_model,
            input=f"""
You are an intent classifier for a WhatsApp AI receptionist.

Classify this customer message:
{text}

Return only a JSON object. No markdown. No explanation.

Allowed intents:
book, reschedule, cancel, services, staff, my_appointment, unknown

Allowed commands:
"1", "2", "3", "4", "5", "6", "unknown"

Mapping:
book -> "1"
reschedule -> "2"
cancel -> "3"
services/pricing -> "4"
staff/human/help -> "5"
my appointment/status/upcoming -> "6"
unknown -> "unknown"

Example output:
{{"intent":"book","command":"1","confidence":0.95}}
""",
        )

        raw = response.output_text.strip()
        data = _extract_json(raw)

        if "command" in data:
            data["command"] = str(data["command"])

        if "confidence" in data:
            data["confidence"] = float(data["confidence"])

        return IntentResult(**data)

    except Exception as exc:
        print("AI_INTENT_ERROR:", exc)
        return _fallback_intent(text)
