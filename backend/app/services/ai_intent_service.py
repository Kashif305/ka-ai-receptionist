import json
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


def classify_intent(message: str) -> IntentResult:
    text = message.strip()

    if text.lower() in {"1", "2", "3", "4", "5", "6"}:
        return IntentResult(intent="unknown", command=text, confidence=1.0)

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

Return ONLY valid JSON:
{{
  "intent": "book | reschedule | cancel | services | staff | my_appointment | unknown",
  "command": "1 | 2 | 3 | 4 | 5 | 6 | unknown",
  "confidence": 0.0
}}

Mapping:
book -> 1
reschedule -> 2
cancel -> 3
services/pricing -> 4
staff/human/help -> 5
my appointment/status/upcoming -> 6
unknown -> unknown
""",
        )

        raw = response.output_text.strip()
        data = json.loads(raw)
        return IntentResult(**data)

    except Exception as exc:
        print("AI_INTENT_ERROR:", exc)
        return IntentResult(intent="unknown", command="unknown", confidence=0.0)
