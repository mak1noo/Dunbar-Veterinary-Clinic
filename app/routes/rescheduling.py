"""Rescheduling existing appointments."""
from datetime import date, time
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.models import CONSULTATION, FARM_VISIT, STATUS_BOOKED, Appointment, db
from app.services.scheduling import reschedule_appointment as move_appointment

rescheduling_bp = Blueprint("rescheduling", __name__)


@rescheduling_bp.route(
    "/appointments/<int:appointment_id>/reschedule", methods=["GET", "POST"]
)
def reschedule_appointment(appointment_id):
    """Show and apply the move of a live appointment."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        abort(404, description="Appointment not found.")

    errors = []
    form_values = {
        "date": request.form.get("date", appointment.date.isoformat()),
        "time": request.form.get("time", appointment.start_time.strftime("%H:%M")),
        "room": request.form.get("room", appointment.room or ""),
        "estimated_hours": request.form.get(
            "estimated_hours", appointment.estimated_hours or ""
        ),
    }

    if request.method == "POST":
        if appointment.status != STATUS_BOOKED:
            errors.append("Only a live booking can be rescheduled.")
        else:
            try:
                selected_date = date.fromisoformat(form_values["date"])
            except ValueError:
                selected_date = None
                errors.append("Enter a valid appointment date.")

            try:
                selected_time = time.fromisoformat(form_values["time"])
            except ValueError:
                selected_time = None
                errors.append("Enter a valid appointment time.")

            selected_room = None
            selected_hours = None

            if appointment.kind == CONSULTATION:
                try:
                    selected_room = int(form_values["room"])
                except (TypeError, ValueError):
                    errors.append("Select consulting room 1 or 2.")
            elif appointment.kind == FARM_VISIT:
                try:
                    selected_hours = Decimal(form_values["estimated_hours"])
                except (InvalidOperation, TypeError):
                    errors.append("Enter an estimated duration in hours.")
            else:
                errors.append("Unsupported appointment kind.")

            if selected_date is not None and selected_time is not None and not errors:
                errors.extend(
                    move_appointment(
                        appointment,
                        day=selected_date,
                        start=selected_time,
                        room=selected_room,
                        estimated_hours=selected_hours,
                    )
                )

            if not errors:
                db.session.commit()
                return redirect(
                    url_for(
                        "rescheduling.reschedule_appointment",
                        appointment_id=appointment.id,
                        updated=1,
                    )
                )
    elif appointment.status != STATUS_BOOKED:
        errors.append("Only a live booking can be rescheduled.")

    return render_template(
        "reschedule_appointment.html",
        appointment=appointment,
        errors=errors,
        form_values=form_values,
        updated=request.args.get("updated") == "1",
    )
