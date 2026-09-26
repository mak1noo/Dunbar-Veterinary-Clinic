"""Client record rules: what the front desk must capture before work is booked.

Stories MSD426GXUST3-39 and MSD426GXUST3-40. The client record comes first:
nothing can be booked, in a consulting room or on a farm run, until the
household or farming business is on file with a name and a number to ring
back.

The register is a working document rather than a form filled in once. A name
gets misspelt over the counter, a mobile number is replaced, a household moves
and wants the account sent somewhere else, so the same rules that let a client
be added are the ones that let the record be put right afterwards.

The rules live here rather than in the route module so they can be unit tested
on their own, the same way the consulting timetable rules live in
``app.services.scheduling``. The column lengths in ``app.models`` are the other
half of the guarantee: this module stops a bad row before it is built, the
model stops it before it is stored.
"""
import re

NAME_MAX = 120  # matches Client.name
ADDRESS_MAX = 255  # matches Client.postal_address
PHONE_MIN_DIGITS = 8

PHONE_CHARACTERS = re.compile(r"^[0-9+()\-\s]+$")
EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def clean(value):
    """Trim a submitted form value; a missing value becomes an empty string."""
    return (value or "").strip()


def validate_client(*, name, phone, email=None, postal_address=None):
    """Return the problems with a client record (empty list = valid).

    Reception takes these details over the counter, so every message says what
    to do next rather than what went wrong inside the application. The same
    checks are used when a client is added and when the record is corrected:
    a correction is not a way around the rules.
    """
    problems = []

    name = clean(name)
    if not name:
        problems.append("Enter the client's full name.")
    elif len(name) > NAME_MAX:
        problems.append(f"Keep the name to {NAME_MAX} characters or fewer.")

    phone = clean(phone)
    digits = [character for character in phone if character.isdigit()]
    if not phone:
        problems.append("Enter a phone number so the clinic can ring the client back.")
    elif not PHONE_CHARACTERS.match(phone) or len(digits) < PHONE_MIN_DIGITS:
        problems.append(
            "That phone number does not look right. Use digits, spaces, +, - or "
            "brackets, for example 0417 552 118."
        )

    email = clean(email)
    if email and not EMAIL_SHAPE.match(email):
        problems.append("That email address does not look right. Check it for a typo.")

    postal_address = clean(postal_address)
    if len(postal_address) > ADDRESS_MAX:
        problems.append(f"Keep the postal address to {ADDRESS_MAX} characters or fewer.")

    return problems


def client_columns(*, name, phone, email=None, postal_address=None, notes=None, sms_consent=False):
    """The cleaned column values for a client record.

    Both the registration form (story -39) and the correction form (story -40)
    go through here, so the values written when a record is corrected are
    scrubbed exactly the way they were when it was first added.
    """
    return {
        "name": clean(name),
        "phone": clean(phone),
        "email": clean(email) or None,
        "postal_address": clean(postal_address) or None,
        "notes": clean(notes) or None,
        "sms_consent": bool(sms_consent),
    }


# --- Farm properties (story MSD426GXUST3-44) -------------------------------

LOCALITY_MAX = 120  # matches Property.locality

RUN_DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def parse_run_day(value):
    """Read a preferred run day off the form; return (day or None, problem or None).

    The farm run leaves on set days, so a property can name the day it is usually
    visited. It is an optional field: plenty of properties are seen whenever the
    run is next out that way, and a blank answer is stored as blank rather than
    guessed at.
    """
    value = clean(value)
    if not value:
        return None, None
    try:
        day = int(value)
    except ValueError:
        return None, "Choose a preferred run day from the list, or leave it blank."
    if day < 0 or day > len(RUN_DAY_NAMES) - 1:
        return None, "Choose a preferred run day from the list, or leave it blank."
    return day, None


def validate_property(*, name, locality, preferred_run_day=None):
    """Return the problems with a farm property record (empty list = valid).

    The story asks for a name and a locality ("record at minimum the property
    name and its locality"), because that is the pair a farm visit is booked
    against and the pair the run sheet groups by. Everything else on the
    property record is optional.
    """
    problems = []

    name = clean(name)
    if not name:
        problems.append("Enter the property name, for example Kalinga Park.")
    elif len(name) > NAME_MAX:
        problems.append(f"Keep the property name to {NAME_MAX} characters or fewer.")

    locality = clean(locality)
    if not locality:
        problems.append("Enter the locality so the farm run can be grouped by area.")
    elif len(locality) > LOCALITY_MAX:
        problems.append(f"Keep the locality to {LOCALITY_MAX} characters or fewer.")

    _, day_problem = parse_run_day(preferred_run_day)
    if day_problem:
        problems.append(day_problem)

    return problems


def property_columns(*, name, locality, preferred_run_day=None):
    """The cleaned column values for a farm property record.

    ``client_id`` is deliberately not in here, for the same reason it is not in
    ``animal_columns``: a property always belongs to a client, and the only way
    to reach this function is through that client's own page.
    """
    day, _ = parse_run_day(preferred_run_day)
    return {
        "name": clean(name),
        "locality": clean(locality),
        "preferred_run_day": day,
    }
