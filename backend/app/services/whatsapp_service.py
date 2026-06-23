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

    patterns = [
        r"(\d+)️⃣\s+([0-9:]+\s[AP]M)",
        r"(\d+)\.\s+\*?([0-9:]+\s[AP]M)\*?",
        r"🔹\s*(\d+)\s+\*?([0-9:]+\s[AP]M)\*?",
        r"◆\s*(\d+)\s+\*?([0-9:]+\s[AP]M)\*?",
        r"▸\s*(\d+)\s+\*?([0-9:]+\s[AP]M)\*?",
        r"\[\s*(\d+)\s*\]\s+\*?([0-9:]+\s[AP]M)\*?",
    ]

    seen: set[str] = set()

    for pattern in patterns:
        for key, label in re.findall(pattern, message):
            if key in seen:
                continue

            seen.add(key)
            rows.append({
                "id": f"command_{key}",
                "title": label,
                "description": "Tap to choose this time",
            })

    return rows


def _extract_date_rows(message: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for key, label in re.findall(r"(\d+)\.\s+([^\n]+)", message):
        rows.append({
            "id": f"command_{key}",
            "title": label[:24],
            "description": "Tap to choose this date",
        })

    return rows


def send_whatsapp_smart_response(to_phone: str, message: str):
    clean = message.strip()

    if "How may I assist you today?" in clean:
        return send_whatsapp_list(
            to_phone=to_phone,
            header="KA AI Receptionist",
            body=clean.split("1️⃣ Book Appointment")[0].strip(),
            button_text="Get Started",
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

    if "Available dates:" in clean:
        rows = _extract_date_rows(clean)

        if rows:
            return send_whatsapp_list(
                to_phone=to_phone,
                header="Choose Date",
                body=clean.split("Available dates:")[0].strip() or "Please choose an available appointment date.",
                button_text="Select Date",
                rows=rows,
            )

    if "Please choose a new date:" in clean:
        return send_whatsapp_list(
            to_phone=to_phone,
            header="Choose New Date",
            body="When would you like to move your appointment?",
            button_text="Select Date",
            rows=[
                {"id": "command_1", "title": "Tomorrow", "description": "Move to tomorrow"},
                {"id": "command_2", "title": "Day After Tomorrow", "description": "Move forward two days"},
                {"id": "command_3", "title": "Next Weekday", "description": "Choose the next weekday"},
                {"id": "command_4", "title": "Custom Date", "description": "Enter your own date"},
            ],
        )

    if "Before I cancel" in clean:
        return send_whatsapp_list(
            to_phone=to_phone,
            header="Cancel Appointment",
            body="Before I cancel, would you like to reschedule instead?",
            button_text="Choose Action",
            rows=[
                {"id": "command_1", "title": "Reschedule Instead", "description": "Move your appointment to another time"},
                {"id": "command_2", "title": "Confirm Cancellation", "description": "Cancel this appointment"},
                {"id": "command_3", "title": "Keep Appointment", "description": "Do not cancel"},
            ],
        )


    if "Review Appointment" in clean and "Confirm Appointment" in clean:
        review_body = clean.split("What would you like to do?")[0].strip()

        return send_whatsapp_list(
            to_phone=to_phone,
            header="Review Appointment",
            body=review_body,
            button_text="Choose Action",
            rows=[
                {"id": "command_1", "title": "Confirm Appointment", "description": "Book this appointment"},
                {"id": "command_2", "title": "Change Time", "description": "Choose a different time"},
                {"id": "command_3", "title": "Cancel Booking", "description": "Do not create this booking"},
            ],
        )


    if "Please choose a time" in clean or "Available times" in clean or "Available Times" in clean:
        rows = _extract_time_rows(clean)

        if 0 < len(rows) <= 10:
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
