"""Story MSD426GXUST3-40: looking at a client record and correcting it.

The register is a working document, so the story is not only "open the record"
but "put it right without starting again". The tests below cover the read
path, the write path, and the fact that a rejected correction leaves the
register exactly as it was.
"""
import re
import sqlite3
from datetime import date, time
from html import unescape
from pathlib import Path

from app.models import CONSULTATION, Animal, Appointment, Client, db

VALID = {
    "name": "Bridie Callaghan",
    "phone": "0417 884 260",
    "email": "bridie@kalinga.example",
    "postal_address": "PO Box 88, Boonah 4310",
    "notes": "Moved down from Toowoomba in March; records still at their old vet.",
    "sms_consent": "on",
}

ADDED_ID = re.compile(r"added=(\d+)")


def register(client, **overrides):
    """Put one client on the register and return the id they were given."""
    form = dict(VALID)
    form.update(overrides)
    response = client.post("/clients/new", data=form)
    assert response.status_code == 303, response.get_data(as_text=True)
    return int(ADDED_ID.search(response.headers["Location"]).group(1))


def change(client, client_id, **overrides):
    """Post the correction form for one client, the way reception would."""
    form = dict(VALID)
    form.update(overrides)
    return client.post(f"/clients/{client_id}/edit", data=form)


def test_the_client_list_links_each_name_to_its_own_page(client):
    client_id = register(client)
    page = client.get("/clients/").get_data(as_text=True)
    assert f'href="/clients/{client_id}"' in page


def test_a_client_page_shows_everything_the_register_holds(client):
    client_id = register(client)
    response = client.get(f"/clients/{client_id}")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 200
    assert "Bridie Callaghan" in page
    assert "0417 884 260" in page
    assert "bridie@kalinga.example" in page
    assert "PO Box 88, Boonah 4310" in page
    assert "records still at their old vet" in page
    assert "Yes" in page  # SMS reminders
    assert f"Client #{client_id}" in page


def test_a_client_page_offers_the_way_in_to_change_it(client):
    client_id = register(client)
    page = client.get(f"/clients/{client_id}").get_data(as_text=True)
    assert f"/clients/{client_id}/edit" in page
    assert "Change these details" in page


def test_a_client_page_says_when_nothing_else_is_on_file(client):
    client_id = register(client)
    page = client.get(f"/clients/{client_id}").get_data(as_text=True)
    assert "No animals on file for this client yet." in page
    assert "No farm properties on file for this client." in page


def test_the_correction_form_arrives_filled_in_with_what_is_on_file(client):
    client_id = register(client)
    page = unescape(client.get(f"/clients/{client_id}/edit").get_data(as_text=True))

    assert "Change these details" in page
    assert 'value="Bridie Callaghan"' in page
    assert 'value="0417 884 260"' in page
    assert 'value="bridie@kalinga.example"' in page
    assert 'value="PO Box 88, Boonah 4310"' in page
    assert "records still at their old vet" in page
    assert "checked" in page


def test_a_corrected_detail_is_saved_and_shown_back(app, client):
    client_id = register(client)
    response = change(
        client,
        client_id,
        name="Bridie Callaghan-Whitmore",
        phone="0455 201 776",
        postal_address="12 Church Street, Boonah 4310",
    )
    assert response.status_code == 303
    assert response.headers["Location"].endswith(f"/clients/{client_id}?updated=1")

    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))
    assert "The changes to Bridie Callaghan-Whitmore have been saved" in page
    assert "0455 201 776" in page
    assert "12 Church Street, Boonah 4310" in page

    with app.app_context():
        saved = Client.query.one()
        assert saved.name == "Bridie Callaghan-Whitmore"
        assert saved.phone == "0455 201 776"
        assert saved.postal_address == "12 Church Street, Boonah 4310"


def test_a_correction_does_not_touch_the_details_it_was_not_asked_to_change(app, client):
    client_id = register(client)
    change(client, client_id, phone="0455 201 776")

    with app.app_context():
        saved = Client.query.one()
        assert saved.name == "Bridie Callaghan"
        assert saved.email == "bridie@kalinga.example"
        assert saved.notes.startswith("Moved down from Toowoomba")
        assert saved.sms_consent is True


def test_an_optional_detail_can_be_cleared_from_the_record(app, client):
    client_id = register(client)
    response = change(client, client_id, email="", postal_address="", notes="", sms_consent=None)
    assert response.status_code == 303

    with app.app_context():
        saved = Client.query.one()
        assert saved.email is None
        assert saved.postal_address is None
        assert saved.notes is None
        assert saved.sms_consent is False


def test_whitespace_around_a_correction_is_trimmed(app, client):
    client_id = register(client)
    change(client, client_id, name="  Bridie Callaghan  ", phone=" 0455 201 776 ")

    with app.app_context():
        saved = Client.query.one()
        assert saved.name == "Bridie Callaghan"
        assert saved.phone == "0455 201 776"


def test_a_correction_that_blanks_the_name_is_explained(app, client):
    client_id = register(client)
    response = change(client, client_id, name="")
    assert response.status_code == 400
    assert "Enter the client's full name." in unescape(response.get_data(as_text=True))

    with app.app_context():
        assert Client.query.one().name == "Bridie Callaghan"


def test_a_correction_that_blanks_the_phone_number_is_explained(app, client):
    client_id = register(client)
    response = change(client, client_id, phone="")
    assert response.status_code == 400
    assert "Enter a phone number" in response.get_data(as_text=True)

    with app.app_context():
        assert Client.query.one().phone == "0417 884 260"


def test_a_correction_to_a_number_that_is_not_a_number_is_explained(app, client):
    client_id = register(client)
    response = change(client, client_id, phone="ask for Bridie")
    assert "phone number does not look right" in response.get_data(as_text=True)

    with app.app_context():
        assert Client.query.one().phone == "0417 884 260"


def test_a_correction_to_a_malformed_email_is_explained(app, client):
    client_id = register(client)
    response = change(client, client_id, email="bridie@kalinga")
    assert "email address does not look right" in response.get_data(as_text=True)

    with app.app_context():
        assert Client.query.one().email == "bridie@kalinga.example"


def test_a_rejected_correction_keeps_what_was_typed(app, client):
    client_id = register(client)
    page = unescape(change(client, client_id, name="", phone="0455 201 776").get_data(as_text=True))
    assert 'value="0455 201 776"' in page
    assert "Bridie Callaghan" in page  # the record itself, still on file


def test_a_correction_keeps_the_client_and_the_bookings_made_against_them(app, client):
    client_id = register(client)

    with app.app_context():
        record = Client.query.one()
        animal = Animal(client=record, name="Duke", species="Dog")
        db.session.add(animal)
        db.session.commit()
        appointment = Appointment(
            kind=CONSULTATION,
            client=record,
            animal=animal,
            date=date(2026, 9, 24),
            start_time=time(9, 30),
            room=1,
        )
        db.session.add(appointment)
        db.session.commit()
        appointment_id = appointment.id

    change(client, client_id, name="Bridie Callaghan-Whitmore")

    with app.app_context():
        assert Client.query.count() == 1
        assert Client.query.one().id == client_id
        kept = Appointment.query.one()
        assert kept.id == appointment_id
        assert kept.client_id == client_id


def test_an_unknown_client_has_no_page(client):
    assert client.get("/clients/4321").status_code == 404


def test_an_unknown_client_cannot_be_corrected(client):
    response = client.post("/clients/4321/edit", data=dict(VALID))
    assert response.status_code == 404


def test_the_correction_reaches_the_local_sqlite_file(app, client):
    client_id = register(client)
    change(client, client_id, phone="0455 201 776")

    database_file = Path(
        app.config["SQLALCHEMY_DATABASE_URI"].removeprefix("sqlite:///")
    )
    assert database_file.is_file()

    with sqlite3.connect(database_file) as connection:
        rows = connection.execute("SELECT name, phone FROM clients").fetchall()
    assert rows == [("Bridie Callaghan", "0455 201 776")]
