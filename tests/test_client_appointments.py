"""Tests for the all-dates client appointment view (MSD426GXUST3-52)."""
from datetime import date, time
from decimal import Decimal

from app.models import (
    CONSULTATION,
    FARM_VISIT,
    STATUS_BOOKED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    Animal,
    Appointment,
    Client,
    Property,
    db,
)
from app.services.scheduling import appointments_for_client


def _client_with_appointments():
    client = Client(name="Bridie Callaghan", phone="0417 884 260")
    animal = Animal(client=client, name="Moss", species="Dog")
    farm_property = Property(client=client, name="Stony Creek", locality="Bunjurgen")
    appointments = [
        Appointment(
            kind=FARM_VISIT,
            status=STATUS_CANCELLED,
            client=client,
            farm_property=farm_property,
            date=date(2026, 8, 10),
            start_time=time(14, 45),
            estimated_hours=Decimal("1.5"),
            reason="Bull soundness",
        ),
        Appointment(
            kind=CONSULTATION,
            status=STATUS_BOOKED,
            client=client,
            animal=animal,
            date=date(2026, 10, 1),
            start_time=time(9, 0),
            room=1,
            reason="Recheck stitches",
        ),
        Appointment(
            kind=CONSULTATION,
            status=STATUS_COMPLETED,
            client=client,
            animal=animal,
            date=date(2026, 8, 12),
            start_time=time(8, 30),
            room=2,
            reason="Vaccination",
        ),
    ]
    db.session.add(client)
    db.session.add_all(appointments)
    db.session.commit()
    return client


def test_client_appointments_are_sorted_across_all_dates(app):
    with app.app_context():
        client = _client_with_appointments()
        appointments = appointments_for_client(client.id)
        ordered = [
            (appointment.date, appointment.start_time, appointment.kind, appointment.status)
            for appointment in appointments
        ]

    assert ordered == [
        (date(2026, 8, 10), time(14, 45), FARM_VISIT, STATUS_CANCELLED),
        (date(2026, 8, 12), time(8, 30), CONSULTATION, STATUS_COMPLETED),
        (date(2026, 10, 1), time(9, 0), CONSULTATION, STATUS_BOOKED),
    ]


def test_client_appointments_page_shows_date_time_kind_and_status(app, client):
    with app.app_context():
        saved_client = _client_with_appointments()
        client_id = saved_client.id

    response = client.get(f"/clients/{client_id}/appointments")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Bridie Callaghan" in html
    assert "10 Aug 2026" in html
    assert "01 Oct 2026" in html
    assert "12 Aug 2026" in html
    assert "Farm visit" in html
    assert "Consultation" in html
    assert "Cancelled" in html
    assert "Completed" in html
    assert "Booked" in html
    assert html.index("10 Aug 2026") < html.index("12 Aug 2026") < html.index("01 Oct 2026")


def test_client_appointments_page_handles_no_appointments(app, client):
    with app.app_context():
        saved_client = Client(name="No Bookings", phone="0400 000 000")
        db.session.add(saved_client)
        db.session.commit()
        client_id = saved_client.id

    response = client.get(f"/clients/{client_id}/appointments")

    assert response.status_code == 200
    assert "No appointments booked" in response.get_data(as_text=True)


def test_client_appointments_page_returns_404_for_unknown_client(client):
    response = client.get("/clients/99999/appointments")

    assert response.status_code == 404


def test_client_detail_links_to_appointment_history(app, client):
    with app.app_context():
        saved_client = _client_with_appointments()
        client_id = saved_client.id

    page = client.get(f"/clients/{client_id}").get_data(as_text=True)

    assert f"/clients/{client_id}/appointments" in page
    assert "View appointment history" in page
