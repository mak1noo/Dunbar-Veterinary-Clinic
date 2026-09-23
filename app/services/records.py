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


# --- Finding an animal by name (story MSD426GXUST3-42) ---------------------

# The characters LIKE reads as wildcards rather than as themselves.
LIKE_SPECIAL = "%_\\"


def animal_name_pattern(term):
    """The LIKE pattern for a search by animal name, or None when nothing was typed.

    Story MSD426GXUST3-42. Reception searches by the animal's name rather
    than the owner's because the person asking is so often not the client on
    file, so the pattern is built to run across the whole register and to
    match anywhere in a name: "Jed" finds Jed, and so does "ed".

    The characters LIKE would normally treat as wildcards are escaped here, so
    a search for "100%" looks for those four characters instead of quietly
    matching every animal on the books. An empty search box returns None: an
    empty search is not a search for everything.
    """
    wanted = clean(term)
    if not wanted:
        return None
    escaped = "".join(
        "\\" + character if character in LIKE_SPECIAL else character
        for character in wanted
    )
    return f"%{escaped}%"
