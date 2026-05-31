import requests

from app.core.config import settings


def send_whatsapp_text(
    to_phone: str,
    message: str,
):
    url = (
        f"https://graph.facebook.com/v23.0/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

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

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    print("WHATSAPP_SEND_STATUS", response.status_code)
    print(response.text)

    return response
