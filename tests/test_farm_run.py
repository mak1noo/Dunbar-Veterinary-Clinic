"""Tests for the ordered farm run view (MSD426GXUST3-51)."""
from datetime import date, time
from decimal import Decimal

from app.models import (
    FARM_VISIT,
    STATUS_BOOKED,
    STATUS_CANCELLED,
    Appointment,
    Client,
    Property,
    db,
)
from app.services.scheduling import farm_run_for_day


RUN_DAY = date(2026, 8, 11)


def _add_farm_visit(*, start_time, property_name, locality, phone, reason, head_count=None, status=STATUS_BOOKED):
    owner = Client(name=f"{property_name} owner", phone=phone)
    farm_property = Property(
        client=owner,
        name=property_name,
        locality=locality,
        access_notes=f"Access notes for {property_name}.",
    )
    visit = Appointment(
        kind=FARM_VISIT,
        status=status,
        client=owner,
        farm_property=farm_property,
        date=RUN_DAY,
        start_time=start_time,
        estimated_hours=Decimal("1.5"),
        head_count=head_count,
        reason=reason,
    )
    db.session.add(visit)
    return visit


def test_farm_run_is_ordered_by_start_time_and_excludes_cancelled(app):
    with app.app_context():
        _add_farm_visit(
            start_time=time(14, 45),
            property_name="Willow Bend",
            locality="Milford",
            phone="0438 907 221",
            reason="Bull soundness",
            head_count=4,
        )
        _add_farm_visit(
            start_time=time(11, 15),
            property_name="Kalinga Downs",
            locality="Coulson",
            phone="0427 118 553",
            reason="Preg test",
            head_count=120,
        )
        _add_farm_visit(
            start_time=time(12, 0),
            property_name="Cancelled Farm",
            locality="Boonah",
            phone="0400 000 000",
            reason="Should not appear",
            status=STATUS_CANCELLED,
        )
        db.session.commit()

        visits = farm_run_for_day(RUN_DAY)
        ordered_times = [visit.start_time for visit in visits]
        property_names = [visit.farm_property.name for visit in visits]
        first_head_count = visits[0].head_count

    assert ordered_times == [time(11, 15), time(14, 45)]
    assert property_names == ["Kalinga Downs", "Willow Bend"]
    assert first_head_count == 120


def test_empty_farm_run_returns_an_empty_list(app):
    with app.app_context():
        assert farm_run_for_day(date(2026, 8, 10)) == []


def test_farm_run_page_shows_required_details_in_working_order(app, client):
    with app.app_context():
        _add_farm_visit(
            start_time=time(14, 45),
            property_name="Willow Bend",
            locality="Milford",
            phone="0438 907 221",
            reason="Bull soundness",
            head_count=4,
        )
        _add_farm_visit(
            start_time=time(11, 15),
            property_name="Kalinga Downs",
            locality="Coulson",
            phone="0427 118 553",
            reason="Preg test",
            head_count=120,
        )
        db.session.commit()

    response = client.get(f"/farm-run?date={RUN_DAY.isoformat()}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.index("Kalinga Downs") < html.index("Willow Bend")
    for expected in (
        "Coulson",
        "0427 118 553",
        "Preg test",
        "120",
        "1.50 hours",
        "Access notes for Kalinga Downs.",
        "Milford",
        "Bull soundness",
    ):
        assert expected in html


def test_farm_run_page_handles_an_empty_day(app, client):
    response = client.get("/farm-run?date=2026-08-10")

    assert response.status_code == 200
    assert "No farm visits scheduled" in response.get_data(as_text=True)


def test_farm_run_page_handles_an_invalid_date(client):
    response = client.get("/farm-run?date=11-08-2026")

    assert response.status_code == 200
    assert "Date must be in YYYY-MM-DD format" in response.get_data(as_text=True)
