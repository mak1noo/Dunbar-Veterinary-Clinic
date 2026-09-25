"""Offline operation status endpoint."""
from flask import Blueprint, current_app, render_template

from app.services.offline import offline_report


offline_bp = Blueprint("offline", __name__)


@offline_bp.get("/offline-status")
def offline_status():
    return render_template("offline_status.html", report=offline_report(current_app))
