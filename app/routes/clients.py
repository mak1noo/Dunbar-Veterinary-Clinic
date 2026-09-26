"""Client records: the register of households and farm businesses.

Stories MSD426GXUST3-39 and MSD426GXUST3-40. Nothing can be booked, a
consultation in one of the two rooms or a farm visit against a property, until
the client is on file, so this is the screen the front desk uses first.

It is also the screen it keeps coming back to. The register is a working
document: a number changes, a name was written down wrong, a household moves,
and reception has to be able to open the record and put it right without
starting the client again and orphaning the bookings already made against it.
So a client has a page of their own, and that page leads to the form that
corrects it.

The rules live in ``app.services.records``; this module is the HTTP layer that turns
the registration form into a ``Client`` row, shows the row back, and writes a
correction over the top of it.
"""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.models import Animal, Client, STATUS_BOOKED, db
from app.services.records import (
    animal_columns,
    animal_details,
    client_columns,
    remove_animal,
    restore_animal,
    validate_animal,
    validate_client,
)
from app.services.scheduling import appointments_for_client

clients_bp = Blueprint("clients", __name__, url_prefix="/clients")


def _submitted():
    """The form values as sent, so a rejected form can be handed straight back."""
    return {
        "name": request.form.get("name", ""),
        "phone": request.form.get("phone", ""),
        "email": request.form.get("email", ""),
        "postal_address": request.form.get("postal_address", ""),
        "notes": request.form.get("notes", ""),
        "sms_consent": request.form.get("sms_consent") == "on",
    }


def _on_file(record):
    """The record's own values in the shape the form fields expect."""
    return {
        "name": record.name,
        "phone": record.phone,
        "email": record.email or "",
        "postal_address": record.postal_address or "",
        "notes": record.notes or "",
        "sms_consent": record.sms_consent,
    }


def _problems_with(chosen):
    """What is wrong with a submitted client form, in the order to fix it."""
    return validate_client(
        name=chosen["name"],
        phone=chosen["phone"],
        email=chosen["email"],
        postal_address=chosen["postal_address"],
    )


def _record_or_404(client_id):
    """The client on file, or a 404 rather than a page with nothing on it."""
    record = db.session.get(Client, client_id)
    if record is None:
        abort(404)
    return record


@clients_bp.get("/")
def list_clients():
    """The client list, in the order the paper register is kept: by name."""
    clients = Client.query.order_by(db.func.lower(Client.name)).all()
    added_id = request.args.get("added", type=int)
    added = db.session.get(Client, added_id) if added_id else None
    return render_template("clients/list.html", clients=clients, added=added)


@clients_bp.get("/new")
def new_client():
    """Show the client registration form."""
    return render_template("clients/create.html", chosen={}, problems=[])


@clients_bp.post("/new")
def create_client():
    """Create the client record, or hand the form back with the problems."""
    chosen = _submitted()
    problems = _problems_with(chosen)
    if problems:
        # 400: the request was understood, the details are just not usable yet.
        return render_template("clients/create.html", chosen=chosen, problems=problems), 400

    record = Client(**client_columns(**chosen))
    db.session.add(record)
    db.session.commit()

    return redirect(url_for("clients.list_clients", added=record.id), code=303)


@clients_bp.get("/<int:client_id>")
def show_client(client_id):
    """One client's page: everything on file, and the way in to change it."""
    record = _record_or_404(client_id)
    changed_animal = _animal_from_query("animal_changed", record)
    return render_template(
        "clients/detail.html",
        record=record,
        updated=request.args.get("updated") == "1",
        updated_animal=_animal_from_query("updated_animal", record),
        changed_animal=changed_animal,
        live_bookings=(
            [] if changed_animal is None or changed_animal.active
            else _live_bookings(changed_animal)
        ),
    )


@clients_bp.get("/<int:client_id>/appointments")
def client_appointments(client_id):
    """Every appointment for one client, across all dates."""
    record = _record_or_404(client_id)
    return render_template(
        "client_appointments.html",
        client_record=record,
        appointments=appointments_for_client(record.id),
    )


@clients_bp.get("/<int:client_id>/edit")
def edit_client(client_id):
    """Show the correction form, filled in with what the register holds."""
    record = _record_or_404(client_id)
    return render_template(
        "clients/edit.html",
        record=record,
        chosen=_on_file(record),
        problems=[],
    )


@clients_bp.post("/<int:client_id>/edit")
def update_client(client_id):
    """Write the correction over the record, or hand the form back.

    The row is changed rather than replaced. Booking history is kept against
    the client id, so a correction has to leave the id, and every appointment
    already made against it, exactly where they are.
    """
    record = _record_or_404(client_id)
    chosen = _submitted()
    problems = _problems_with(chosen)
    if problems:
        # Nothing is written: the register keeps the details it already had.
        return render_template("clients/edit.html", record=record, chosen=chosen, problems=problems), 400

    for column, value in client_columns(**chosen).items():
        setattr(record, column, value)
    db.session.commit()

    return redirect(url_for("clients.show_client", client_id=record.id, updated=1), code=303)


def _animal_submitted():
    """The animal form values as sent, so a rejected form can be handed back."""
    return {
        "name": request.form.get("name", ""),
        "species": request.form.get("species", ""),
        "breed": request.form.get("breed", ""),
        "sex": request.form.get("sex", ""),
        "date_of_birth": request.form.get("date_of_birth", ""),
        "desexed": request.form.get("desexed") == "on",
        "microchip": request.form.get("microchip", ""),
        "notes": request.form.get("notes", ""),
    }


def _problems_with_animal(chosen):
    """What is wrong with a submitted animal form, in the order to fix it."""
    return validate_animal(
        name=chosen["name"],
        species=chosen["species"],
        breed=chosen["breed"],
        sex=chosen["sex"],
        date_of_birth=chosen["date_of_birth"],
        microchip=chosen["microchip"],
    )


def _animal_from_query(parameter, record):
    """The animal named in the query string, when it belongs to this client.

    The banner after a change is driven by the animal the redirect named, and
    only ever by one that sits on this client's page: a query string is not a
    way to put somebody else's animal on the screen.
    """
    animal_id = request.args.get(parameter, type=int)
    if not animal_id:
        return None
    animal = db.session.get(Animal, animal_id)
    if animal is None or animal.client_id != record.id:
        return None
    return animal


def _animal_or_404(client_id, animal_id):
    """The animal on file for that client, or a 404.

    Both ids are in the address, and the two have to agree. An animal is only
    ever reached through the client it belongs to, so a request that names one
    client's page and another client's animal is a 404 rather than a correction
    written against the wrong household.
    """
    record = _record_or_404(client_id)
    animal = db.session.get(Animal, animal_id)
    if animal is None or animal.client_id != record.id:
        abort(404)
    return record, animal


def _live_bookings(animal):
    """The bookings still in the appointment book for this animal."""
    return [booking for booking in animal.appointments if booking.status == STATUS_BOOKED]


@clients_bp.get("/<int:client_id>/animals/<int:animal_id>/edit")
def edit_animal(client_id, animal_id):
    """Show the correction form for one animal, filled in with what is on file."""
    record, animal = _animal_or_404(client_id, animal_id)
    return render_template(
        "animals/edit.html",
        record=record,
        animal=animal,
        chosen=animal_details(animal),
        problems=[],
    )


@clients_bp.post("/<int:client_id>/animals/<int:animal_id>/edit")
def update_animal(client_id, animal_id):
    """Write the correction over the animal, or hand the form back.

    The row is changed rather than replaced, for the same reason a client
    correction is: the animal's id is what every appointment already booked
    against it is filed under, so a correction has to leave the id, the owner
    and the booking history exactly where they are.
    """
    record, animal = _animal_or_404(client_id, animal_id)
    chosen = _animal_submitted()
    problems = _problems_with_animal(chosen)
    if problems:
        # Nothing is written: the animal keeps the details it already had.
        return render_template(
            "animals/edit.html",
            record=record,
            animal=animal,
            chosen=chosen,
            problems=problems,
        ), 400

    for column, value in animal_columns(**chosen).items():
        setattr(animal, column, value)
    db.session.commit()

    return redirect(
        url_for("clients.show_client", client_id=record.id, updated_animal=animal.id),
        code=303,
    )


@clients_bp.post("/<int:client_id>/animals/<int:animal_id>/active")
def set_animal_active(client_id, animal_id):
    """Take an animal off the books, or put it back on them.

    Removing an animal is a flag rather than a delete, for the same reason
    stopping a client is: a record is history as well as a way of booking work.
    An animal that is off the books stops being offered when a consultation is
    booked, while its own row, every appointment already made against it and
    the client it belongs to all stay exactly where they are.
    """
    record, animal = _animal_or_404(client_id, animal_id)
    back_on_the_books = request.form.get("active") == "1"
    changed = restore_animal(animal) if back_on_the_books else remove_animal(animal)
    if changed:
        db.session.commit()
    return redirect(
        url_for("clients.show_client", client_id=record.id, animal_changed=animal.id),
        code=303,
    )
