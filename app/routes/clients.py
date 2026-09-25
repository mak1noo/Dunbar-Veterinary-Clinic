"""Client records: the register of households and farm businesses.

Stories MSD426GXUST3-39, MSD426GXUST3-40 and MSD426GXUST3-44. Nothing can be booked, a
consultation in one of the two rooms or a farm visit against a property, until
the client is on file, so this is the screen the front desk uses first.

It is also the screen it keeps coming back to. The register is a working
document: a number changes, a name was written down wrong, a household moves,
and reception has to be able to open the record and put it right without
starting the client again and orphaning the bookings already made against it.
So a client has a page of their own, and that page leads to the form that
corrects it, and the forms that hang records off the client: the animals it owns
and the farm properties its visits are booked against.

The rules live in ``app.services.records``; this module is the HTTP layer that turns
the registration form into a ``Client`` row, shows the row back, and writes a
correction over the top of it.
"""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.models import Client, Property, db
from app.services.records import (
    RUN_DAY_NAMES,
    client_columns,
    property_columns,
    validate_client,
    validate_property,
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


def _property_submitted():
    """The farm property form values as sent, so a rejected form can be handed back."""
    return {
        "name": request.form.get("name", ""),
        "locality": request.form.get("locality", ""),
        "preferred_run_day": request.form.get("preferred_run_day", ""),
    }


def _problems_with_property(chosen):
    """What is wrong with a submitted farm property form, in the order to fix it."""
    return validate_property(
        name=chosen["name"],
        locality=chosen["locality"],
        preferred_run_day=chosen["preferred_run_day"],
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
    added_property_id = request.args.get("added_property", type=int)
    added_property = db.session.get(Property, added_property_id) if added_property_id else None
    if added_property is not None and added_property.client_id != record.id:
        # Only ever highlight a property that belongs to the client on screen.
        added_property = None
    return render_template(
        "clients/detail.html",
        record=record,
        updated=request.args.get("updated") == "1",
        added_property=added_property,
        run_days=RUN_DAY_NAMES,
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


@clients_bp.get("/<int:client_id>/properties/new")
def new_property(client_id):
    """Show the form for recording a farm property against one client.

    A farm visit is booked against a property, and a property always belongs
    to the client whose run it is on, so there is no top-level form for one:
    it is added from the client page. A client who is not on file has nothing
    to add to, and gets the same 404 as any other missing record.
    """
    record = _record_or_404(client_id)
    return render_template(
        "properties/create.html",
        record=record,
        chosen={},
        problems=[],
        run_days=RUN_DAY_NAMES,
    )


@clients_bp.post("/<int:client_id>/properties/new")
def create_property(client_id):
    """Record the farm property against that client, or hand the form back.

    The client comes from the address the form was posted to, never from the
    form itself, so the property cannot land on the wrong client's record.
    """
    record = _record_or_404(client_id)
    chosen = _property_submitted()
    problems = _problems_with_property(chosen)
    if problems:
        return render_template(
            "properties/create.html",
            record=record,
            chosen=chosen,
            problems=problems,
            run_days=RUN_DAY_NAMES,
        ), 400

    farm_property = Property(client_id=record.id, **property_columns(**chosen))
    db.session.add(farm_property)
    db.session.commit()

    return redirect(
        url_for("clients.show_client", client_id=record.id, added_property=farm_property.id),
        code=303,
    )
