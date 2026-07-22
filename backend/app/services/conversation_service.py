import json
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff, StaffAvailability, StaffService
from app.core.config import settings
from urllib.parse import quote_plus
from app.services.staff_assignment_service import get_available_staff_for_service


BUSINESS_TZ = ZoneInfo("America/New_York")


MENU_OPTIONS = """1️⃣ Book Appointment
2️⃣ Reschedule Appointment
3️⃣ Cancel Appointment
4️⃣ Services & Pricing
5️⃣ Speak with Staff
6️⃣ My Appointment"""


def build_main_menu(customer: Customer | None = None, is_returning: bool = False) -> str:
    if customer and is_returning:
        first_name = (customer.name or "").split()[0] or "there"
        greeting = f"""✨ Welcome back, {first_name}!

Thank you for choosing Samina Beauty Salon again. My name is Samina Receptionist and I'm here to help."""
    else:
        greeting = """✨ Welcome to Samina Beauty Salon!

Thank you for contacting us. My name is Samina Receptionist and I'm here to help."""

    return f"""{greeting}

How may I assist you today?

{MENU_OPTIONS}"""


MAIN_MENU = build_main_menu()


DATE_MENU = """Perfect.

When would you like to come in?

1️⃣ Tomorrow
2️⃣ Day after tomorrow
3️⃣ Custom Date
"""

RESCHEDULE_DATE_MENU = """Please choose a new date:

1️⃣ Tomorrow
2️⃣ Day after tomorrow
3️⃣ Next available weekday
4️⃣ Custom Date
"""

TIME_MENU = """Tomorrow works.

Please choose a time:

1️⃣ 2:00 PM
2️⃣ 3:00 PM
3️⃣ 4:00 PM
"""


CANCEL_CONFIRM_MENU = """Before I cancel, would you like to reschedule instead?

1️⃣ Reschedule Appointment
2️⃣ Confirm Cancellation
3️⃣ Keep Appointment
"""

STAFF_REPLY = "No problem. A staff member will follow up with you soon."


def build_service_menu(db: Session) -> tuple[str, dict[str, int]]:
    services = (
        db.query(Service)
        .filter(Service.active.is_(True))
        .order_by(Service.name.asc())
        .all()
    )
    if not services:
        return (
            "We do not have any services available for booking right now. "
            "Please choose Speak With Staff for help.",
            {},
        )
    choices = {str(index): service.id for index, service in enumerate(services, 1)}
    options = "\n".join(
        f"{index}. {service.name}" for index, service in enumerate(services, 1)
    )
    return (
        "Great — let's book your appointment.\n\n"
        f"What service would you like?\n\n{options}",
        choices,
    )


BUSINESS_OPEN_HOUR = 12
BUSINESS_CLOSE_HOUR = 21
CLOSED_WEEKDAYS = set()  # Dev QA: allow all weekdays


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


def business_directions_text() -> str:
    if not settings.business_address:
        return ""

    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(settings.business_address)}"

    return f"""\n\n📍 {settings.business_name}
{settings.business_address}

Directions:
{maps_url}"""


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


def create_real_appointment(
    db: Session,
    customer: Customer,
    service: Service,
    start_at: datetime,
) -> Appointment | None:
    end_at = start_at + timedelta(minutes=service.duration_minutes)

    available_staff = get_available_staff_for_service(
        db=db,
        service=service,
        start_at=start_at,
    )

    if not available_staff:
        return None

    assigned_staff = available_staff[0]

    appointment = Appointment(
        customer_id=customer.id,
        service_id=service.id,
        assigned_staff_id=assigned_staff.id,
        start_at=start_at,
        end_at=end_at,
        status="confirmed",
        source="whatsapp",
        notes=f"Created from WhatsApp booking flow. Assigned staff: {assigned_staff.name}",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment



def is_slot_booked(db: Session, start_at: datetime, end_at: datetime) -> bool:
    return (
        db.query(Appointment)
        .filter(Appointment.status == "confirmed")
        .filter(Appointment.start_at < end_at)
        .filter(Appointment.end_at > start_at)
        .first()
        is not None
    )


def get_available_time_choices(
    db: Session,
    selected_date,
    service: Service,
    exclude_appointment_id: int | None = None,
) -> tuple[str, dict[str, str]]:
    """
    Build customer-facing time choices from staff availability.

    Source of truth:
    staff_availability
        ↓
    staff_services
        ↓
    existing appointments
        ↓
    available customer time choices
    """
    staff_windows = (
        db.query(StaffAvailability)
        .join(StaffService, StaffService.staff_id == StaffAvailability.staff_id)
        .join(Staff, Staff.id == StaffAvailability.staff_id)
        .filter(StaffAvailability.weekday == selected_date.weekday())
        .filter(StaffAvailability.active.is_(True))
        .filter(Staff.active.is_(True))
        .filter(StaffService.service_id == service.id)
        .order_by(StaffAvailability.start_time.asc())
        .all()
    )

    candidate_times: list[time] = []
    seen_times: set[time] = set()
    service_duration = timedelta(minutes=service.duration_minutes)

    for window in staff_windows:
        cursor = datetime.combine(selected_date, window.start_time)
        window_end = datetime.combine(selected_date, window.end_time)

        while cursor + service_duration <= window_end:
            slot_time = cursor.time()

            if slot_time not in seen_times:
                candidate_times.append(slot_time)
                seen_times.add(slot_time)

            cursor += timedelta(minutes=window.slot_duration_minutes)

    candidate_times.sort()

    lines = []
    time_choices: dict[str, str] = {}

    for slot_time in candidate_times:
        start_at = datetime.combine(
            selected_date,
            slot_time,
            tzinfo=BUSINESS_TZ,
        )

        available_staff = get_available_staff_for_service(
            db=db,
            service=service,
            start_at=start_at,
            exclude_appointment_id=exclude_appointment_id,
        )

        if available_staff:
            key = str(len(time_choices) + 1)
            label = start_at.strftime("%I:%M %p").lstrip("0")
            lines.append(f"🔹 {key}  *{label}*")
            time_choices[key] = slot_time.strftime("%H:%M")

    if not lines:
        return (
            "No appointment slots are available for that day.\n\nPlease choose another date or type menu to start over.",
            {},
        )

    return "✨ Available Times\n\n" + "\n".join(lines) + "\n\nTap a time below or reply with the number.", time_choices


def selected_context_time(context: dict, choice: str) -> time | None:
    value = context.get("time_choices", {}).get(choice)
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def time_choice_prompt(context: dict) -> str:
    choices = context.get("time_choices", {})
    if not choices:
        return "Please choose one of the displayed appointment times."
    return f"Please choose an appointment time from: {', '.join(choices)}."


def get_reschedule_date(choice: str) -> date | None:
    today = datetime.now(BUSINESS_TZ).date()

    if choice == "1":
        return today + timedelta(days=1)

    if choice == "2":
        return today + timedelta(days=2)

    if choice == "3":
        candidate = today + timedelta(days=3)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate

    return None


def get_booking_date(choice: str) -> date | None:
    today = datetime.now(BUSINESS_TZ).date()

    if choice == "1":
        return today + timedelta(days=1)

    if choice == "2":
        return today + timedelta(days=2)

    return None

def build_booking_date_choices() -> tuple[str, dict[str, str]]:
    today = datetime.now(BUSINESS_TZ).date()
    choices: dict[str, str] = {}
    lines: list[str] = []

    for index in range(1, 8):
        selected_date = today + timedelta(days=index)
        key = str(index)
        label = selected_date.strftime("%a, %b %d")

        if index == 1:
            label = f"Tomorrow — {label}"

        lines.append(f"{key}. {label}")
        choices[key] = selected_date.isoformat()

    more_key = "8"
    lines.append(f"{more_key}. More Dates...")
    choices[more_key] = "custom"

    message = "Available dates:\n\n" + "\n".join(lines)
    return message, choices


def get_services_and_pricing_reply(db: Session) -> str:
    services = (
        db.query(Service)
        .filter(Service.active.is_(True))
        .order_by(Service.name.asc())
        .all()
    )

    if not services:
        return "We do not have any active services listed right now. Please check back soon or choose Speak With Staff for help."

    lines = ["Services & Pricing:"]
    for service in services:
        price = f"${service.price:.2f}" if service.price is not None else "Price available on request"
        lines.append(
            f"• {service.name} — {service.duration_minutes} minutes — {price}"
        )

    return "\n\n".join([lines[0], "\n".join(lines[1:])])


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

    available_staff = get_available_staff_for_service(
        db=db,
        service=service,
        start_at=new_start_at,
        exclude_appointment_id=appointment.id,
    )

    if not available_staff:
        return False

    assigned_staff = available_staff[0]

    appointment.assigned_staff_id = assigned_staff.id
    appointment.start_at = new_start_at
    appointment.end_at = new_end_at
    appointment.notes = f"Rescheduled from WhatsApp flow. Assigned staff: {assigned_staff.name}"
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
Status: {appointment.status.title()}{business_directions_text()}"""



def cancel_next_confirmed_appointment(db: Session, customer: Customer) -> str:
    appointment = get_next_confirmed_appointment(db, customer)

    if not appointment:
        return "I could not find an active appointment to cancel."

    cancelled_at = format_business_datetime(appointment.start_at)

    appointment.status = "cancelled"
    appointment.notes = "Cancelled from WhatsApp flow"
    db.commit()

    return f"""Your appointment has been cancelled ✅

Cancelled appointment:
{cancelled_at}"""


def handle_customer_message(db: Session, customer: Customer, message_body: str) -> str:
    text = message_body.strip().lower()
    state = get_or_create_state(db, customer)

    # Safety: any main-menu cancel request must confirm before cancelling.
    if text == "3" and state.current_state == "main_menu":
        appointment = get_next_confirmed_appointment(db, customer)

        if not appointment:
            return "I could not find an active appointment to cancel."

        state.current_state = "cancel_confirm"
        state.current_step = "awaiting_cancel_choice"
        state.context_json = "{}"
        db.commit()

        return CANCEL_CONFIRM_MENU

    if text in {"samina receptionist", "samina", "hello", "hi", "hey", "menu", "start"}:
        state.current_state = "main_menu"
        state.current_step = "awaiting_menu_choice"
        state.context_json = "{}"
        db.commit()
        return build_main_menu(customer, is_returning=True)

    if state.current_state == "main_menu" or state.current_step == "awaiting_menu_choice":
        if text == "1":
            service_menu, service_choices = build_service_menu(db)
            if not service_choices:
                return service_menu
            state.current_state = "booking"
            state.current_step = "select_service"
            save_context(db, state, {"service_choices": service_choices})
            return service_menu

        if text == "2":
            appointment = get_next_confirmed_appointment(db, customer)

            if not appointment:
                return "I could not find an active upcoming appointment to reschedule."

            context = {
                "appointment_id": appointment.id,
                "service_id": appointment.service_id,
            }

            state.current_state = "reschedule"
            state.current_step = "select_reschedule_date"
            save_context(db, state, context)
            return f"""I found your upcoming appointment:

{format_business_datetime(appointment.start_at)}

{RESCHEDULE_DATE_MENU}"""

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
            return get_services_and_pricing_reply(db)

        if text == "5":
            state.current_state = "human_handoff"
            state.current_step = "waiting_for_staff"
            db.commit()
            return STAFF_REPLY

        if text == "6":
            return get_upcoming_appointment_reply(db, customer)




    if state.current_state == "cancel_confirm" and state.current_step == "awaiting_cancel_choice":
        if text in {"1", "reschedule appointment", "reschedule instead"}:
            appointment = get_next_confirmed_appointment(db, customer)

            if not appointment:
                state.current_state = "main_menu"
                state.current_step = "completed"
                state.context_json = "{}"
                db.commit()
                return "I could not find an active appointment to reschedule."

            context = {
                "appointment_id": appointment.id,
                "service_id": appointment.service_id,
            }

            state.current_state = "reschedule"
            state.current_step = "select_reschedule_date"
            save_context(db, state, context)

            return f"""Good choice — let's reschedule instead.

Current appointment:
{format_business_datetime(appointment.start_at)}

{RESCHEDULE_DATE_MENU}"""

        if text in {"2", "confirm cancellation", "confirm cancel", "cancel appointment"}:
            reply = cancel_next_confirmed_appointment(db, customer)
            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()
            return reply

        if text in {"3", "keep appointment", "do not cancel"}:
            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()
            return "No problem — your appointment is still confirmed ✅"

        return CANCEL_CONFIRM_MENU


    if state.current_state == "reschedule" and state.current_step == "select_reschedule_date":
        if text == "4":
            state.current_step = "awaiting_custom_reschedule_date"
            db.commit()
            return "Please enter your new appointment date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        selected_date = get_reschedule_date(text)
        if selected_date is None:
            return RESCHEDULE_DATE_MENU

        context = get_context(state)
        appointment_id = context.get("appointment_id")
        service_id = context.get("service_id")
        appointment = db.get(Appointment, appointment_id) if appointment_id else None
        service = db.get(Service, service_id) if service_id else None

        if not appointment or appointment.status != "confirmed" or not service:
            state.current_state = "main_menu"
            state.current_step = "awaiting_menu_choice"
            state.context_json = "{}"
            db.commit()
            return "I could not find that active appointment anymore. Please reply 2 to start again."

        available, time_choices = get_available_time_choices(
            db,
            selected_date,
            service,
            exclude_appointment_id=appointment.id,
        )

        if available.startswith("No appointment slots"):
            return f"{available}\n\n{RESCHEDULE_DATE_MENU}"

        context["appointment_date"] = selected_date.isoformat()
        context["time_choices"] = time_choices
        state.current_step = "select_reschedule_time"
        save_context(db, state, context)
        return f"New date: {selected_date.strftime('%A, %B %d, %Y')}\n\n{available}"

    if state.current_state == "reschedule" and state.current_step == "awaiting_custom_reschedule_date":
        try:
            selected_date = datetime.strptime(text, "%m/%d/%Y").date()
        except ValueError:
            return "That date is invalid. Please enter a valid date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        if selected_date.strftime("%m/%d/%Y") != text:
            return "That date is invalid. Please enter a valid date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        if selected_date < datetime.now(BUSINESS_TZ).date():
            return "That date is in the past. Please enter today or a future date in MM/DD/YYYY format."

        context = get_context(state)
        appointment_id = context.get("appointment_id")
        service_id = context.get("service_id")
        appointment = db.get(Appointment, appointment_id) if appointment_id else None
        service = db.get(Service, service_id) if service_id else None

        if not appointment or appointment.status != "confirmed" or not service:
            state.current_state = "main_menu"
            state.current_step = "awaiting_menu_choice"
            state.context_json = "{}"
            db.commit()
            return "I could not find that active appointment anymore. Please reply 2 to start again."

        available, time_choices = get_available_time_choices(
            db,
            selected_date,
            service,
            exclude_appointment_id=appointment.id,
        )

        if available.startswith("No appointment slots"):
            return f"Sorry, that day is fully booked for {service.name}.\n\nPlease enter another date in MM/DD/YYYY format."

        context["appointment_date"] = selected_date.isoformat()
        context["time_choices"] = time_choices
        state.current_step = "select_reschedule_time"
        save_context(db, state, context)
        return f"New date: {selected_date.strftime('%A, %B %d, %Y')}\n\n{available}"

    if state.current_state == "reschedule" and state.current_step == "select_reschedule_time":
        context = get_context(state)
        selected_time = selected_context_time(context, text)
        if selected_time is not None:
            appointment_id = context.get("appointment_id")
            appointment_date = context.get("appointment_date")

            if not appointment_id or not appointment_date:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 2 to start rescheduling again."

            appointment = db.get(Appointment, appointment_id)
            if not appointment or appointment.status != "confirmed":
                return "I could not find that active appointment anymore."

            selected_date = datetime.fromisoformat(appointment_date).date()

            new_start_at = datetime.combine(
                selected_date,
                selected_time,
                tzinfo=BUSINESS_TZ,
            )

            if not is_business_open_at(new_start_at):
                return business_hours_message()

            ok = reschedule_appointment(db, appointment, new_start_at)

            if not ok:
                available, time_choices = get_available_time_choices(
                    db,
                    selected_date,
                    db.get(Service, appointment.service_id),
                    exclude_appointment_id=appointment.id,
                )
                context["time_choices"] = time_choices
                save_context(db, state, context)
                return f"Sorry, that time is already booked.\n\n{available}"

            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()

            return f"""Your appointment has been rescheduled ✅

New appointment:
{format_business_datetime(appointment.start_at)}{business_directions_text()}"""

        return time_choice_prompt(context)


    if state.current_state == "booking" and state.current_step == "select_service":
        context = get_context(state)
        service_id = context.get("service_choices", {}).get(text)
        service = db.get(Service, service_id) if service_id else None
        if service and service.active:

            date_menu, date_choices = build_booking_date_choices()

            context = {
                "service_id": service.id,
                "service_name": service.name,
                "duration_minutes": service.duration_minutes,
                "date_choices": date_choices,
            }

            state.current_step = "select_date"
            save_context(db, state, context)
            return date_menu

        service_menu, service_choices = build_service_menu(db)
        save_context(db, state, {"service_choices": service_choices})
        return service_menu

    if state.current_state == "booking" and state.current_step == "select_date":
        context = get_context(state)
        date_choices = context.get("date_choices", {})
        selected_value = date_choices.get(text)

        if selected_value == "custom":
            state.current_step = "awaiting_custom_booking_date"
            db.commit()
            return "Please enter your appointment date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        if not selected_value:
            date_menu, date_choices = build_booking_date_choices()
            context["date_choices"] = date_choices
            save_context(db, state, context)
            return date_menu

        selected_date = datetime.fromisoformat(selected_value).date()

        service = db.get(Service, context.get("service_id"))
        if not service or not service.active:
            return "Service was not found. Please reply 1 to start again."

        available, time_choices = get_available_time_choices(db, selected_date, service)
        if not time_choices:
            date_menu, date_choices = build_booking_date_choices()
            context["date_choices"] = date_choices
            save_context(db, state, context)
            return f"Sorry, that day is fully booked for {service.name}.\n\nPlease choose another date:\n\n{date_menu}"

        context["appointment_date"] = selected_date.isoformat()
        context["time_choices"] = time_choices
        state.current_step = "select_time"
        save_context(db, state, context)
        return f"Date: {selected_date.strftime('%A, %B %d, %Y')}\n\n{available}"

    if state.current_state == "booking" and state.current_step == "awaiting_custom_booking_date":
        try:
            selected_date = datetime.strptime(text, "%m/%d/%Y").date()
        except ValueError:
            return "That date is invalid. Please enter a valid date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        if selected_date.strftime("%m/%d/%Y") != text:
            return "That date is invalid. Please enter a valid date in MM/DD/YYYY format.\n\nExample: 07/15/2026"

        if selected_date < datetime.now(BUSINESS_TZ).date():
            return "That date is in the past. Please enter today or a future date in MM/DD/YYYY format."

        context = get_context(state)
        service = db.get(Service, context.get("service_id"))
        if not service or not service.active:
            return "Service was not found. Please reply 1 to start again."

        available, time_choices = get_available_time_choices(db, selected_date, service)
        if not time_choices:
            return f"Sorry, that day is fully booked for {service.name}.\n\nPlease enter another date in MM/DD/YYYY format."

        context["appointment_date"] = selected_date.isoformat()
        context["time_choices"] = time_choices
        state.current_step = "select_time"
        save_context(db, state, context)
        return f"Date: {selected_date.strftime('%A, %B %d, %Y')}\n\n{available}"

    if state.current_state == "booking" and state.current_step == "select_time":
        context = get_context(state)
        selected_time = selected_context_time(context, text)
        if selected_time is not None:

            service_id = context.get("service_id")
            appointment_date = context.get("appointment_date")

            if not service_id or not appointment_date:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 1 to start booking again."

            service = db.get(Service, service_id)
            if not service or not service.active:
                return "Service was not found. Please reply 1 to start again."

            appointment_day = datetime.fromisoformat(appointment_date).date()

            start_at = datetime.combine(
                appointment_day,
                selected_time,
                tzinfo=BUSINESS_TZ,
            )

            if not is_business_open_at(start_at):
                return business_hours_message()

            available_staff = get_available_staff_for_service(
                db=db,
                service=service,
                start_at=start_at,
            )

            if not available_staff:
                available, time_choices = get_available_time_choices(db, appointment_day, service)
                context["time_choices"] = time_choices
                save_context(db, state, context)
                return f"Sorry, that time is already booked.\n\n{available}"

            assigned_staff = available_staff[0]

            context["review_start_at"] = start_at.isoformat()
            context["review_staff_id"] = assigned_staff.id
            context["review_staff_name"] = assigned_staff.name

            state.current_step = "review_appointment"
            save_context(db, state, context)

            return f"""Review Appointment

Staff: {assigned_staff.name}
Service: {service.name}
Date: {start_at.astimezone(BUSINESS_TZ).strftime('%A, %B %d, %Y')}
Time: {start_at.astimezone(BUSINESS_TZ).strftime('%I:%M %p')}

What would you like to do?

1️⃣ Confirm Appointment
2️⃣ Change Time
3️⃣ Cancel Booking{business_directions_text()}"""

        return time_choice_prompt(context)

    if state.current_state == "booking" and state.current_step == "review_appointment":
        context = get_context(state)

        if text == "1":
            service_id = context.get("service_id")
            review_start_at = context.get("review_start_at")

            if not service_id or not review_start_at:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 1 to start booking again."

            service = db.get(Service, service_id)
            start_at = datetime.fromisoformat(review_start_at)

            if not service or not service.active:
                return "Service was not found. Please reply 1 to start again."

            appointment = create_real_appointment(
                db=db,
                customer=customer,
                service=service,
                start_at=start_at,
            )

            if appointment is None:
                appointment_day = start_at.date()
                available, time_choices = get_available_time_choices(db, appointment_day, service)
                context["time_choices"] = time_choices
                state.current_step = "select_time"
                save_context(db, state, context)
                return f"Sorry, that time is no longer available.\n\n{available}"

            state.current_state = "main_menu"
            state.current_step = "completed"
            state.context_json = "{}"
            db.commit()

            staff_name = appointment.assigned_staff.name if appointment.assigned_staff else "Assigned staff"

            return f"""You're booked ✅

Staff: {staff_name}
Service: {service.name}
Date: {appointment.start_at.astimezone(BUSINESS_TZ).strftime('%A, %B %d, %Y')}
Time: {appointment.start_at.astimezone(BUSINESS_TZ).strftime('%I:%M %p')}

Thank you for choosing Samina Beauty Salon.{business_directions_text()}"""

        if text == "2":
            service_id = context.get("service_id")
            appointment_date = context.get("appointment_date")

            service = db.get(Service, service_id) if service_id else None
            selected_date = datetime.fromisoformat(appointment_date).date() if appointment_date else None

            if not service or not selected_date:
                state.current_state = "main_menu"
                state.current_step = "awaiting_menu_choice"
                state.context_json = "{}"
                db.commit()
                return "Something reset. Please reply 1 to start booking again."

            available, time_choices = get_available_time_choices(db, selected_date, service)
            context["time_choices"] = time_choices
            state.current_step = "select_time"
            save_context(db, state, context)
            return f"Please choose another time.\n\n{available}"

        if text == "3":
            state.current_state = "main_menu"
            state.current_step = "awaiting_menu_choice"
            state.context_json = "{}"
            db.commit()
            return "No problem — your booking was not created.\n\n" + build_main_menu(customer, is_returning=True)

        return """Please choose one option:

1️⃣ Confirm Appointment
2️⃣ Change Time
3️⃣ Cancel Booking"""



    return MAIN_MENU
