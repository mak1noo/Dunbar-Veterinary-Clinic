"""Story MSD426GXUST3-50: the day view of taken and free consulting cells.

The grid is laid out by ``app.services.scheduling.day_schedule``; this file
covers the layout itself (open and closed days, taken and free cells,
cancelled bookings, farm visits that never occupy a consulting room) and the
page that renders it.
"""
from datetime import date, time
from types import SimpleNamespace

import pytest

from app.models import (
    CONSULTATION,
    FARM_VISIT,
    STATUS_BOOKED,
    STATUS_CANCELLED,
    Animal,
    Appointment,
    Client,
    Property,
    db,
)
from app.services.scheduling import day_schedule, slots_for_day

MONDAY = date(2026, 9, 21)
SUNDAY = date(2026, 9, 27)


def _booking(start, room, status=STATUS_BOOKED):
    return SimpleNamespace(start_time=start, room=room, status=status)


def _row_at(grid, slot):
    return next(row for row in grid["rows"] if row["slot"] == slot)


# --- the layout -------------------------------------------------------------


def test_a_closed_day_has_no_rows():
    grid = day_schedule(SUNDAY, bookings=[])
    assert grid["open"] is False
    assert grid["rows"] == []
    assert grid["capacity"] == 0
    assert grid["booked"] == 0


def test_an_open_day_gives_every_slot_one_cell_per_room():
    grid = day_schedule(MONDAY, bookings=[])
    slots = slots_for_day(MONDAY)
    assert grid["open"] is True
    assert len(grid["rows"]) == len(slots)
    assert grid["capacity"] == len(slots) * 2
    assert grid["free"] == grid["capacity"]
    first = grid["rows"][0]
    assert first["label"] == "8:30 am"
    assert [cell["room"] for cell in first["cells"]] == [1, 2]
    assert all(cell["booking"] is None for cell in first["cells"])


def test_a_booking_takes_only_its_own_cell():
    grid = day_schedule(MONDAY, bookings=[_booking(time(9, 0), 1)])
    room_one, room_two = _row_at(grid, time(9, 0))["cells"]
    assert room_one["booking"] is not None
    assert room_two["booking"] is None
    assert grid["booked"] == 1
    assert grid["free"] == grid["capacity"] - 1


def test_cancelled_bookings_leave_their_cell_free():
    grid = day_schedule(MONDAY, bookings=[_booking(time(9, 0), 1, status=STATUS_CANCELLED)])
    assert all(cell["booking"] is None for cell in _row_at(grid, time(9, 0))["cells"])
    assert grid["booked"] == 0


def test_bookings_outside_the_grid_are_ignored():
    grid = day_schedule(
        MONDAY,
        bookings=[_booking(time(6, 0), 1), _booking(time(9, 0), 7)],
    )
    assert grid["booked"] == 0


# --- the page ---------------------------------------------------------------


@pytest.fixture
def biscuit(app):
    """Mrs Prosser's cat, straight from the case study appointment book."""
    with app.app_context():
        owner = Client(name="Mrs Prosser", phone="0417 552 118")
        animal = Animal(name="Biscuit", species="Cat", client=owner)
        db.session.add(animal)
        db.session.commit()
        return animal.id


def test_the_page_shows_every_slot_of_an_open_day(client):
    page = client.get(f"/schedule/?date={MONDAY.isoformat()}").get_data(as_text=True)
    assert "8:30 am" in page
    assert "5:15 pm" in page
    assert "Consulting room 1" in page
    assert "Consulting room 2" in page
    assert "0 of 72 cells taken" in page


def test_a_taken_cell_names_the_animal_and_the_client(app, client, biscuit):
    with app.app_context():
        animal = db.session.get(Animal, biscuit)
        db.session.add(
            Appointment(
                kind=CONSULTATION,
                status=STATUS_BOOKED,
                client=animal.client,
                animal=animal,
                date=MONDAY,
                start_time=time(9, 0),
                room=2,
            )
        )
        db.session.commit()

    page = client.get(f"/schedule/?date={MONDAY.isoformat()}").get_data(as_text=True)
    assert "Biscuit" in page
    assert "Mrs Prosser" in page
    assert "1 of 72 cells taken" in page


def test_farm_visits_do_not_occupy_consulting_cells(app, client, biscuit):
    with app.app_context():
        animal = db.session.get(Animal, biscuit)
        farm = Property(name="Gwavas Farm", locality="Dunbar", client=animal.client)
        db.session.add(farm)
        db.session.flush()
        db.session.add(
            Appointment(
                kind=FARM_VISIT,
                status=STATUS_BOOKED,
                client=animal.client,
                farm_property=farm,
                date=MONDAY,
                start_time=time(9, 0),
                estimated_hours=2,
            )
        )
        db.session.commit()

    page = client.get(f"/schedule/?date={MONDAY.isoformat()}").get_data(as_text=True)
    assert "0 of 72 cells taken" in page


def test_a_closed_day_says_so(client):
    page = client.get(f"/schedule/?date={SUNDAY.isoformat()}").get_data(as_text=True)
    assert "closed for consultations" in page


def test_a_bad_date_falls_back_to_today_with_a_message(client):
    page = client.get("/schedule/?date=not-a-date").get_data(as_text=True)
    assert "Date must be in YYYY-MM-DD format. Showing today instead." in page


def test_the_page_offers_the_neighbouring_days(client):
    page = client.get(f"/schedule/?date={MONDAY.isoformat()}").get_data(as_text=True)
    assert "date=2026-09-20" in page
    assert "date=2026-09-22" in page
