"""Home, farm run and health endpoints."""
from datetime import date

from flask import Blueprint, render_template, request

from app.services.scheduling import farm_run_for_day

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/farm-run")
def farm_run():
    raw_date = request.args.get("date")
    date_error = None
    if raw_date:
        try:
            selected_date = date.fromisoformat(raw_date)
        except ValueError:
            selected_date = date.today()
            date_error = "Date must be in YYYY-MM-DD format. Showing today instead."
    else:
        selected_date = date.today()

    return render_template(
        "farm_run.html",
        selected_date=selected_date,
        visits=farm_run_for_day(selected_date),
        date_error=date_error,
    )


@main_bp.get("/healthz")
def healthz():
    return {"status": "ok"}
