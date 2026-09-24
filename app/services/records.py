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
from datetime import date, datetime

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


# --- Correcting an animal record, and taking one off the books (story -43) --
#
# The rules an animal is recorded under are the rules its details are put right
# under, for the same reason the client rules are shared between the
# registration form and the correction form: a correction is not a way around
# the rules.
#
# "Removing" an animal is never a delete. The animal is taken off the books, so
# it stops being offered for new work, while its own row, its appointment
# history and the client it belongs to all stay exactly where they are.

SPECIES_MAX = 60  # matches Animal.species
BREED_MAX = 120  # matches Animal.breed
MICROCHIP_MAX = 40  # matches Animal.microchip

SEXES = ("female", "male", "unknown")


def parse_date_of_birth(value):
    """Read a date of birth off the form; return (date or None, problem or None).

    The form posts a date field as YYYY-MM-DD. A date that cannot be read, or
    one that has not happened yet, is a problem rather than something to guess
    at: an animal entered with the wrong date of birth is worse than one with
    no date on file at all.
    """
    value = clean(value)
    if not value:
        return None, None
    try:
        born = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter the date of birth as YYYY-MM-DD, for example 2019-04-17."
    if born > date.today():
        return None, "The date of birth cannot be in the future."
    return born, None


def validate_animal(*, name, species, breed=None, sex=None, date_of_birth=None, microchip=None):
    """Return the problems with an animal record (empty list = valid).

    The story only insists on a name and a species ("record at minimum the
    animal name and species"), and that is what the form marks required. The
    rest of the checks are here so that a field the front desk did fill in is
    not silently stored in a shape nobody meant: a mis-typed date of birth, or
    a sex that is not one of the choices offered. Correcting a record runs the
    same checks as recording one, so a correction is not a way around them.
    """
    problems = []

    name = clean(name)
    if not name:
        problems.append("Enter the animal's name.")
    elif len(name) > NAME_MAX:
        problems.append(f"Keep the animal's name to {NAME_MAX} characters or fewer.")

    species = clean(species)
    if not species:
        problems.append("Enter the species, for example dog, cat or horse.")
    elif len(species) > SPECIES_MAX:
        problems.append(f"Keep the species to {SPECIES_MAX} characters or fewer.")

    breed = clean(breed)
    if len(breed) > BREED_MAX:
        problems.append(f"Keep the breed to {BREED_MAX} characters or fewer.")

    sex = clean(sex).lower()
    if sex and sex not in SEXES:
        problems.append("Choose female, male or unknown for the sex.")

    microchip = clean(microchip)
    if len(microchip) > MICROCHIP_MAX:
        problems.append(f"Keep the microchip number to {MICROCHIP_MAX} characters or fewer.")

    _, born_problem = parse_date_of_birth(date_of_birth)
    if born_problem:
        problems.append(born_problem)

    return problems


def animal_columns(*, name, species, breed=None, sex=None, date_of_birth=None,
                   desexed=False, microchip=None, notes=None):
    """The cleaned column values for an animal record.

    client_id is deliberately not in here. An animal belongs to a client, and
    the only way to reach this function is through that client's own page, so
    the route passes the id of the client it already has in hand rather than
    taking one from the form.
    """
    born, _ = parse_date_of_birth(date_of_birth)
    return {
        "name": clean(name),
        "species": clean(species),
        "breed": clean(breed) or None,
        "sex": clean(sex).lower() or None,
        "desexed": bool(desexed),
        "date_of_birth": born,
        "microchip": clean(microchip) or None,
        "notes": clean(notes) or None,
    }


def animal_details(animal):
    """An animal's own values in the shape the correction form's fields expect.

    The date goes back to the form as YYYY-MM-DD, because that is what a date
    input reads and writes, and a value that was never filled in comes back as
    an empty box rather than the word None.
    """
    return {
        "name": animal.name,
        "species": animal.species,
        "breed": animal.breed or "",
        "sex": animal.sex or "",
        "date_of_birth": animal.date_of_birth.isoformat() if animal.date_of_birth else "",
        "desexed": animal.desexed,
        "microchip": animal.microchip or "",
        "notes": animal.notes or "",
    }


def remove_animal(animal):
    """Take an animal off the books, without deleting anything.

    Returns True when the animal was on the books and has just been taken off,
    and False when it was already off. The caller owns the transaction, the
    same way the scheduling rules leave the commit to their caller: the flag on
    the row is the whole change.
    """
    if not animal.active:
        return False
    animal.active = False
    return True


def restore_animal(animal):
    """Put an animal back on the books. Returns True when it changed."""
    if animal.active:
        return False
    animal.active = True
    return True
