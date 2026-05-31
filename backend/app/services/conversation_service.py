import json
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.service import Service


BUSINESS_TZ = ZoneInfo("America/New_York")


MAIN_MENU = """Hello 👋

Thank you for contacting KA AI Receptionist.

Please choose:

1️⃣ Book Appointment
2️⃣ Reschedule Appointment
3️⃣ Cancel Appointment
4️⃣ Services & Pricing
5️⃣ Speak With Staff
6️⃣ My Appointment
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

TIME_MENU = """Tomorrow works.

Please choose a time:

1️⃣ 2:00 PM
2️⃣ 3:00 PM
3️⃣ 4:00 PM
"""

STAFF_REPLY = "No problem. A staff member will follow up with you soon."


SERVICE_MAP = {
    "1": {"name": "Eyebrow Threading", "duration": 20, "price": 12.00},
    "2": {"name": "Facial", "duration": 60, "price": 65.00},
    "3": {"name": "Haircut", "duration": 30, "price": 25.00},
}


BUSINESS_OPEN_HOUR = 12
BUSINESS_CLOSE_HOUR = 21
CLOSED_WEEKDAYS = {0}  # Monday = 0


def is_business_open_at(start_at: datetime) -> bool:
    local_dt = start_at.astimezone(BUSINESS_TZ)

    if local_dt.weekday() in CLOSED_WEEKDAYS:
        return False

    return BUSINESS_OPEN_HOUR <= local_dt.hour < BUSINESS_CLOSE_HOUR


def business_hours_message() -> str:
    return """Sorry, we are closed at that time.

Business hours:
Tuesday–Sunday: 12:00 PM – 9:00 PM
Monday: Closed"""


TIME_MAP = {
    "1": time(14, 0),
    "2": time(15, 0),
    "3": time(16, 0),
}



def format_business_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    local_dt = dt.astimezone(BUSINESS_TZ)
    return local_dt.strftime("%A, %B %d at %I:%M %p")


def get_or_create_state(db: Session, customer: Customer) -> ConversationState:
    state = db.query(ConversationState).filter(
        ConversationState.customer_id == customer.id
    ).first()

    if state:
        return state

    state = ConversationState(
        customer_id=customer.id,
        current_state="main_menu",
        current_step="start",
        context_json="{}",
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def get_context(state: ConversationState) -> dict:
    if not state.context_json:
        return {}
    try:
        return json.loads(state.context_json)
    except json.JSONDecodeError:
        return {}


def save_context(db: Session, state: ConversationState, context: dict) -> None:
    state.context_json = json.dumps(context)
    db.commit()


def get_or_create_service(db: Session, service_name: str, duration: int, price: float) -> Service:
    service = db.query(Service).filter(Service.name == service_name).first()

    if service:
        return service

    service = Service(
        name=service_name,
        description=f"{service_name} service",
        duration_minutes=duration,
        price=price,
        active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def create_real_appointment(
    db: Session,
    customer: Customer,
    service: Service,
    start_at: datetime,
) -> Appointment | None:
    end_at = start_at + timedelta(minutes=service.duration_minutes)

    if is_slot_booked(db, start_at):
        return None

    appointment = Appointment(
        customer_id=customer.id,
        service_id=service.id,
        start_at=start_at,
        end_at=end_at,
        status="confirmed",
        source="whatsapp",
        notes="Created from WhatsApp booking flow",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment




def is_slot_booked(db: Session, start_at: datetime) -> bool:
    return (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at == start_at)
        .first()
        is not None
    )


def get_available_time_choices(db: Session, selected_date, service: Service) -> str:
    lines = []

    for key, slot_time in TIME_MAP.items():
        start_at = datetime.combine(
            selected_date,
            slot_time,
            tzinfo=BUSINESS_TZ,
        )

        if not is_slot_booked(db, start_at):
            label = start_at.strftime("%I:%M %p").lstrip("0")
            lines.append(f"{key}️⃣ {label}")

    if not lines:
        return "No appointment slots are available for that day.\n\nPlease choose another date or type menu to start over."

    return "Available times:\n\n" + "\n".join(lines)


def get_next_confirmed_appointment(db: Session, customer: Customer) -> Appointment | None:
    now = datetime.now(BUSINESS_TZ)

    return (
        db.query(Appointment)
        .filter(Appointment.customer_id == customer.id)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at >= now)
        .order_by(Appointment.start_at.asc())
        .first()
    )


def reschedule_appointment(
    db: Session,
    appointment: Appointment,
    new_start_at: datetime,
) -> bool:
    service = db.get(Service, appointment.service_id)
    if not service:
        return False

    new_end_at = new_start_at + timedelta(minutes=service.duration_minutes)

    conflict = (
        db.query(Appointment)
        .filter(Appointment.id != appointment.id)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at == new_start_at)
        .first()
    )

    if conflict:
        return False

    appointment.start_at = new_start_at
    appointment.end_at = new_end_at
    appointment.notes = "Rescheduled from WhatsApp flow"
    db.commit()
    db.refresh(appointment)
    return True



def get_upcoming_appointment_reply(db: Session, customer: Customer) -> str:
    appointment = get_next_confirmed_appointment(db, customer)

    if not appointment:
        return "I could not find any upcoming confirmed appointment for you."

    service = db.get(Service, appointment.service_id)
    service_name = service.name if service else "Appointment"

    return f"""Your next appointment ✅

Service: {service_name}
Date/Time: {format_business_datetime(appointment.start_at)}
Status: {appointment.status.title()}"""


def handle_customer_message(db: Session, customer: Customer, message_body: str) -> str:
    text = message_body.strip().lower()
    state = get_or_create_state(db, customer)

    if text in {"hello", "hi", "hey", "menu", "start"}:
        state.current_state = "main_menu"
        state.current_step = "awaiting_menu_choice"
        state.context_json = "{}"
        db.commit()
        return MAIN_MENU

    if state.current_state == "main_menu" or state.current_step == "awaiting_menu_choice":
        if text == "1":
            state.current_state = "booking"
            state.current_step = "select_service"
            state.context_json = "{}"
            db.commit()
            return SERVICE_MENU

        if text == "2":
            appointment = get_next_confirmed_appointment(db, customer)

            if not appointment:
                return "I could not find an active upcoming appointment to reschedule."

            context = {
                "appointment_id": appointment.id,
                "service_id": appointment.service_id,
            }

            state.current_state = "reschedule"
            state.current_step = "select_reschedule_time"
            save_context(db, state, context)
            return f"""I found your upcoming appointment:

{format_business_datetime(appointment.start_at)}

Please choose a new time for tomorrow:

1️⃣ 2:00 PM
2️⃣ 3:00 PM
3️⃣ 4:00 PM"""

        if text == "3":
            appointment = (
                db.query(Appointment)
                .filter(Appointment.customer_id == customer.id)
                .filter(Appointment.status == "confirmed")
                .order_by(Appointment.start_at.asc())
                .first()
            )

            if not appointment:
                return "I could not find an active appointment to cancel."

            appointment.status = "cancelled"
            db.commit()

            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()

            return f"""Your appointment has been cancelled ✅

Cancelled appointment:
{format_business_datetime(appointment.start_at)}"""

        if text == "4":
            return "Our demo services include Eyebrow Threading, Facial, and Haircut."

        if text == "5":
            state.current_state = "human_handoff"
            state.current_step = "waiting_for_staff"
            db.commit()
            return STAFF_REPLY

        if text == "6":
            return get_upcoming_appointment_reply(db, customer)

        return MAIN_MENU


    if state.current_state == "reschedule" and state.current_step == "select_reschedule_time":
        if text in TIME_MAP:
            context = get_context(state)
            appointment_id = context.get("appointment_id")

            if not appointment_id:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 2 to start rescheduling again."

            appointment = db.get(Appointment, appointment_id)
            if not appointment or appointment.status != "confirmed":
                return "I could not find that active appointment anymore."

            selected_time = TIME_MAP[text]
            tomorrow = datetime.now(BUSINESS_TZ).date() + timedelta(days=1)

            new_start_at = datetime.combine(
                tomorrow,
                selected_time,
                tzinfo=BUSINESS_TZ,
            )

            if not is_business_open_at(new_start_at):
                return business_hours_message()

            ok = reschedule_appointment(db, appointment, new_start_at)

            if not ok:
                available = get_available_time_choices(
                    db,
                    tomorrow,
                    db.get(Service, appointment.service_id),
                )
                return f"Sorry, that time is already booked.\n\n{available}"

            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()

            return f"""Your appointment has been rescheduled ✅

New appointment:
{format_business_datetime(appointment.start_at)}"""

        return "Please choose 1, 2, or 3 for the new appointment time."


    if state.current_state == "booking" and state.current_step == "select_service":
        if text in SERVICE_MAP:
            selected = SERVICE_MAP[text]
            service = get_or_create_service(
                db,
                selected["name"],
                selected["duration"],
                selected["price"],
            )

            context = {
                "service_id": service.id,
                "service_name": service.name,
                "duration_minutes": service.duration_minutes,
            }

            state.current_step = "select_date"
            save_context(db, state, context)
            return DATE_MENU

        return SERVICE_MENU

    if state.current_state == "booking" and state.current_step == "select_date":
        context = get_context(state)

        if text == "1":
            tomorrow = datetime.now(BUSINESS_TZ).date() + timedelta(days=1)
            context["appointment_date"] = tomorrow.isoformat()
            state.current_step = "select_time"
            save_context(db, state, context)
            return TIME_MENU

        if text == "2":
            return "This week availability is coming next. For now, please choose tomorrow by replying 1."

        if text == "3":
            return "Custom date support is coming next. For now, please choose tomorrow by replying 1."

        return DATE_MENU

    if state.current_state == "booking" and state.current_step == "select_time":
        if text in TIME_MAP:
            context = get_context(state)

            service_id = context.get("service_id")
            appointment_date = context.get("appointment_date")

            if not service_id or not appointment_date:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 1 to start booking again."

            service = db.get(Service, service_id)
            if not service:
                return "Service was not found. Please reply 1 to start again."

            selected_time = TIME_MAP[text]
            appointment_day = datetime.fromisoformat(appointment_date).date()

            start_at = datetime.combine(
                appointment_day,
                selected_time,
                tzinfo=BUSINESS_TZ,
            )

            if not is_business_open_at(start_at):
                return business_hours_message()

            appointment = create_real_appointment(
                db=db,
                customer=customer,
                service=service,
                start_at=start_at,
            )

            if appointment is None:
                available = get_available_time_choices(db, appointment_day, service)
                return f"Sorry, that time is already booked.\n\n{available}"

            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()

            return f"""You're booked ✅

Service: {service.name}
Date: {appointment.start_at.astimezone(BUSINESS_TZ).strftime('%A, %B %d, %Y')}
Time: {appointment.start_at.astimezone(BUSINESS_TZ).strftime('%I:%M %p')}

Thank you for using KA AI Receptionist."""

        return "Please choose 1, 2, or 3 for the appointment time."

    return MAIN_MENU
