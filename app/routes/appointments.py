"""Cancelling appointments without deleting their history."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.models import STATUS_BOOKED, STATUS_CANCELLED, Appointment, db
from app.services.scheduling import cancel_appointment as mark_cancelled

appointments_bp = Blueprint("appointments", __name__)


@appointments_bp.route("/appointments/<int:appointment_id>/cancel", methods=["GET", "POST"])
def cancel_appointment(appointment_id):
    """Show and apply a cancellation without deleting the appointment."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        abort(404, description="Appointment not found.")

    if request.method == "POST":
        changed = mark_cancelled(appointment)
        if changed:
            db.session.commit()
        return redirect(
            url_for(
                "appointments.cancel_appointment",
                appointment_id=appointment.id,
                changed="1" if changed else "0",
            )
        )

    return render_template(
        "cancel_appointment.html",
        appointment=appointment,
        changed=request.args.get("changed") == "1",
        attempted="changed" in request.args,
    )
