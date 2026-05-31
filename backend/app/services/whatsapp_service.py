import re
from typing import Any

import requests

from app.core.config import settings


def _send_whatsapp_payload(payload: dict[str, Any]):
    url = f"https://graph.facebook.com/v23.0/{settings.whatsapp_phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    print("WHATSAPP_SEND_STATUS", response.status_code)
    print(response.text)

    return response


def send_whatsapp_text(to_phone: str, message: str):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message,
        },
    }

    return _send_whatsapp_payload(payload)


def send_whatsapp_list(
    to_phone: str,
    body: str,
    button_text: str,
    rows: list[dict[str, str]],
    header: str = "KA AI Receptionist",
):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": header,
            },
            "body": {
                "text": body,
            },
            "action": {
                "button": button_text,
                "sections": [
                    {
                        "title": "Options",
                        "rows": rows,
                    }
                ],
            },
        },
    }

    return _send_whatsapp_payload(payload)


def _extract_time_rows(message: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for key, label in re.findall(r"([123])️⃣\s+([0-9:]+\s[AP]M)", message):
        rows.append(
            {
                "id": f"command_{key}",
                "title": label,
                "description": f"Choose {label}",
            }
        )

    return rows


def send_whatsapp_smart_response(to_phone: str, message: str):
    clean = message.strip()

    if clean.startswith("Hello 👋"):
        return send_whatsapp_list(
            to_phone=to_phone,
            header="KA AI Receptionist",
            body="How can I help you today?",
            button_text="Choose Option",
            rows=[
                {"id": "command_1", "title": "Book Appointment", "description": "Schedule a new appointment"},
                {"id": "command_2", "title": "Reschedule", "description": "Move an existing appointment"},
                {"id": "command_3", "title": "Cancel Appointment", "description": "Cancel your appointment"},
                {"id": "command_4", "title": "Services & Pricing", "description": "View available services"},
                {"id": "command_5", "title": "Speak With Staff", "description": "Request human help"},
                {"id": "command_6", "title": "My Appointment", "description": "View your next appointment"},
            ],
        )

    if "What service would you like?" in clean:
        return send_whatsapp_list(
            to_phone=to_phone,
            header="Choose Service",
            body="What service would you like to book?",
            button_text="Select Service",
            rows=[
                {"id": "command_1", "title": "Eyebrow Threading", "description": "20 minutes"},
                {"id": "command_2", "title": "Facial", "description": "60 minutes"},
                {"id": "command_3", "title": "Haircut", "description": "30 minutes"},
            ],
        )

    if "When would you like to come in?" in clean:
        return send_whatsapp_list(
            to_phone=to_phone,
            header="Choose Date",
            body="When would you like to come in?",
            button_text="Select Date",
            rows=[
                {"id": "command_1", "title": "Tomorrow", "description": "Book for tomorrow"},
                {"id": "command_2", "title": "This Week", "description": "Coming soon"},
                {"id": "command_3", "title": "Custom Date", "description": "Coming soon"},
            ],
        )

    if "Please choose a time" in clean or "Available times:" in clean:
        rows = _extract_time_rows(clean)

        if rows:
            body = "Please choose an available appointment time."
            if "Sorry, that time is already booked" in clean:
                body = "That time is already booked. Please choose another available time."

            return send_whatsapp_list(
                to_phone=to_phone,
                header="Choose Time",
                body=body,
                button_text="Select Time",
                rows=rows,
            )

    return send_whatsapp_text(to_phone, message)
