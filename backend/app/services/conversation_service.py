from sqlalchemy.orm import Session

from app.models.conversation_state import ConversationState
from app.models.customer import Customer


MAIN_MENU = """Hello 👋

Thank you for contacting KA AI Receptionist.

Please choose:

1️⃣ Book Appointment
2️⃣ Reschedule Appointment
3️⃣ Cancel Appointment
4️⃣ Services & Pricing
5️⃣ Speak With Staff
"""

SERVICE_MENU = """Great — let's book your appointment.

What service would you like?

1️⃣ Eyebrow Threading
2️⃣ Facial
3️⃣ Haircut
"""

DATE_MENU = """Perfect.

When would you like to come in?

1️⃣ Tomorrow
2️⃣ This Week
3️⃣ Custom Date
"""

STAFF_REPLY = """No problem. A staff member will follow up with you soon."""


def get_or_create_state(db: Session, customer: Customer) -> ConversationState:
    state = (
        db.query(ConversationState)
        .filter(ConversationState.customer_id == customer.id)
        .first()
    )

    if state:
        return state

    state = ConversationState(
        customer_id=customer.id,
        current_state="main_menu",
        current_step="start",
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def handle_customer_message(db: Session, customer: Customer, message_body: str) -> str:
    text = message_body.strip().lower()
    state = get_or_create_state(db, customer)

    if text in {"hello", "hi", "hey", "menu", "start"}:
        state.current_state = "main_menu"
        state.current_step = "awaiting_menu_choice"
        db.commit()
        return MAIN_MENU

    if state.current_state == "main_menu" or state.current_step == "awaiting_menu_choice":
        if text == "1":
            state.current_state = "booking"
            state.current_step = "select_service"
            db.commit()
            return SERVICE_MENU

        if text == "2":
            return "Reschedule flow is coming next. For now, please send your current appointment time."

        if text == "3":
            return "Cancel flow is coming next. For now, please send your appointment time to cancel."

        if text == "4":
            return "Our demo services include Eyebrow Threading, Facial, and Haircut. Pricing setup is coming next."

        if text == "5":
            state.current_state = "human_handoff"
            state.current_step = "waiting_for_staff"
            db.commit()
            return STAFF_REPLY

        return MAIN_MENU

    if state.current_state == "booking" and state.current_step == "select_service":
        if text in {"1", "2", "3"}:
            service_map = {
                "1": "Eyebrow Threading",
                "2": "Facial",
                "3": "Haircut",
            }
            state.current_step = "select_date"
            state.context_json = f'{{"service":"{service_map[text]}"}}'
            db.commit()
            return DATE_MENU

        return SERVICE_MENU

    if state.current_state == "booking" and state.current_step == "select_date":
        if text == "1":
            state.current_step = "select_time"
            db.commit()
            return """Tomorrow works.

Please choose a time:

1️⃣ 2:00 PM
2️⃣ 3:00 PM
3️⃣ 4:00 PM
"""

        if text == "2":
            return "This week availability is coming next. For now, please choose tomorrow by replying 1."

        if text == "3":
            return "Please type your preferred date, for example: Monday afternoon."

        return DATE_MENU

    if state.current_state == "booking" and state.current_step == "select_time":
        if text in {"1", "2", "3"}:
            time_map = {
                "1": "2:00 PM",
                "2": "3:00 PM",
                "3": "4:00 PM",
            }
            chosen_time = time_map[text]
            state.current_state = "main_menu"
            state.current_step = "completed"
            db.commit()
            return f"""You're almost booked ✅

Demo appointment time selected:
{chosen_time}

Next sprint will connect this to the real appointments table."""

        return "Please choose 1, 2, or 3 for the appointment time."

    return MAIN_MENU
