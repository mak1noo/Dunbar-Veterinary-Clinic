
"""Story MSD426GXUST3-43: correcting an animal's details, and removing one.

An animal record is a working document, like the client record it sits under:
a breed is written down wrong at the first visit, a date of birth is put right
once the vaccination card turns up, an animal is sold or dies and should stop
being offered for new work. So an animal can be corrected, and it can be taken
off the books.

Taking an animal off the books is a flag and never a delete, for the same
reason stopping a client is: the record is history as well as a way of booking
work. The client it belonged to is not touched, and neither is anything already
booked against the animal.

The animals in these tests are put on the register the way the database holds
one, because the form that records an animal from its client's page is story
MSD426GXUST3-41. What this file is about is what happens to the animal after
that.
"""
import re
from datetime import date, time
from html import unescape

from app.models import CONSULTATION, STATUS_BOOKED, Animal, Appointment, Client, db
from app.services.records import animal_columns

ADDED_ID = re.compile(r"added=(\d+)")

CORRECTION = {
    "name": "Moss",
    "species": "Dog",
    "breed": "Kelpie x",
    "sex": "female",
    "date_of_birth": "2020-11-02",
    "microchip": "956000014029551",
    "desexed": "on",
    "notes": "Now lives at the Goodna address.",
}


def register(client, name="Bridie Callaghan", phone="0417 884 260"):
    """Put one client on the register and return the id they were given."""
    response = client.post("/clients/new", data={"name": name, "phone": phone})
    assert response.status_code == 303, response.get_data(as_text=True)
    return int(ADDED_ID.search(response.headers["Location"]).group(1))


def record_animal(app, client_id, **overrides):
    """Put one animal on the register and return the id it was given."""
    fields = {"name": "Moss", "species": "Dog", "breed": "Kelpie x", "sex": "male",
              "date_of_birth": "2019-04-17", "microchip": "956000012774318"}
    fields.update(overrides)
    with app.app_context():
        animal = Animal(client_id=client_id, **animal_columns(**fields))
        db.session.add(animal)
        db.session.commit()
        return animal.id


def book_consultation(app, client_id, animal_id, *, status=STATUS_BOOKED):
    """Put one appointment in the book against an animal, as reception would."""
    with app.app_context():
        appointment = Appointment(
            kind=CONSULTATION,
            status=status,
            client_id=client_id,
            animal_id=animal_id,
            date=date(2026, 9, 30),
            start_time=time(9, 0),
            room=1,
        )
        db.session.add(appointment)
        db.session.commit()
        return appointment.id


def correct(client, client_id, animal_id, **overrides):
    """Post the correction form the way reception would."""
    form = dict(CORRECTION)
    form.update(overrides)
    return client.post(f"/clients/{client_id}/animals/{animal_id}/edit", data=form)


def test_a_client_page_leads_to_the_correction_form(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    page = client.get(f"/clients/{client_id}").get_data(as_text=True)

    assert f"/clients/{client_id}/animals/{animal_id}/edit" in page
    assert "Change details" in page


def test_the_correction_form_is_filled_in_with_what_is_on_file(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = client.get(f"/clients/{client_id}/animals/{animal_id}/edit")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 200
    assert "Change Moss" in page
    assert "Bridie Callaghan" in page  # the owner it is recorded against
    assert 'value="Moss"' in page
    assert 'value="Kelpie x"' in page
    assert 'value="2019-04-17"' in page
    assert 'value="956000012774318"' in page


def test_an_animal_can_be_corrected(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = correct(client, client_id, animal_id, name="Mossy", species="Dog (Kelpie)")

    assert response.status_code == 303
    assert response.headers["Location"].startswith(f"/clients/{client_id}?updated_animal=")

    with app.app_context():
        animal = db.session.get(Animal, animal_id)
        assert animal.name == "Mossy"
        assert animal.species == "Dog (Kelpie)"
        assert animal.sex == "female"
        assert animal.date_of_birth.isoformat() == "2020-11-02"
        assert animal.microchip == "956000014029551"
        assert animal.notes.startswith("Now lives at the Goodna address")
        assert animal.client_id == client_id  # the owner is not changed by a correction


def test_a_correction_leaves_the_id_and_the_bookings_alone(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)
    appointment_id = book_consultation(app, client_id, animal_id)

    correct(client, client_id, animal_id, name="Mossy")

    with app.app_context():
        appointment = db.session.get(Appointment, appointment_id)
        assert appointment.animal_id == animal_id
        assert appointment.status == STATUS_BOOKED
        assert db.session.get(Animal, animal_id) is not None


def test_the_corrected_details_are_shown_on_the_client_page(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = correct(client, client_id, animal_id, name="Mossy", breed="Cattle x")
    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))

    assert "The changes to Mossy have been saved to the register." in page
    assert "Cattle x" in page


def test_a_correction_that_breaks_the_rules_is_handed_back(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = correct(client, client_id, animal_id, name="   ", species="", date_of_birth="next Tuesday")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 400
    assert "Enter the animal's name." in page
    assert "Enter the species, for example dog, cat or horse." in page
    assert "Enter the date of birth as YYYY-MM-DD, for example 2019-04-17." in page
    assert "Now lives at the Goodna address." in page  # what was typed is handed back

    with app.app_context():
        animal = db.session.get(Animal, animal_id)
        assert animal.name == "Moss"
        assert animal.species == "Dog"
        assert animal.date_of_birth.isoformat() == "2019-04-17"


def test_an_animal_cannot_be_reached_through_another_clients_page(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)
    other_client_id = register(client, name="Ted Okafor", phone="07 4666 1122")

    assert client.get(f"/clients/{other_client_id}/animals/{animal_id}/edit").status_code == 404
    assert correct(client, other_client_id, animal_id).status_code == 404

    with app.app_context():
        assert db.session.get(Animal, animal_id).name == "Moss"


def test_taking_an_animal_off_the_books_keeps_the_row(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})

    assert response.status_code == 303
    assert response.headers["Location"].startswith(f"/clients/{client_id}?animal_changed=")

    with app.app_context():
        animal = db.session.get(Animal, animal_id)
        assert animal is not None  # removed, not deleted
        assert animal.active is False
        assert animal.client_id == client_id
        assert animal.name == "Moss"


def test_taking_an_animal_off_the_books_does_not_touch_the_owner(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})

    with app.app_context():
        owner = db.session.get(Client, client_id)
        assert owner is not None
        assert owner.active is True
        assert owner.name == "Bridie Callaghan"
        assert owner.phone == "0417 884 260"
        assert len(owner.animals) == 1  # still one of their animals, just off the books
        assert Client.query.count() == 1


def test_taking_an_animal_off_the_books_leaves_its_bookings_alone(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)
    appointment_id = book_consultation(app, client_id, animal_id)

    client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})

    with app.app_context():
        appointment = db.session.get(Appointment, appointment_id)
        assert appointment is not None
        assert appointment.animal_id == animal_id
        assert appointment.status == STATUS_BOOKED


def test_a_removed_animal_is_not_offered_when_a_consultation_is_booked(app, client):
    client_id = register(client)
    removed_id = record_animal(app, client_id, name="Moss")
    on_the_books_id = record_animal(app, client_id, name="Biscuit", species="Cat")

    assert client.post(f"/clients/{client_id}/animals/{removed_id}/active", data={"active": "0"}).status_code == 303
    page = unescape(client.get("/consultations/new?date=2026-09-30").get_data(as_text=True))

    assert "Biscuit" in page  # the animal that is still on the books is offered
    assert "Moss" not in page  # the removed one is not
    with app.app_context():
        assert db.session.get(Animal, on_the_books_id).active is True


def test_a_removed_animal_is_marked_on_the_client_page(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    response = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})
    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))

    assert "Moss has been taken off the books" in page
    assert "Bridie Callaghan's record is not affected." in page
    assert "Removed" in page
    assert "Put back" in page
    assert "Change details" in page  # the record can still be corrected


def test_taking_an_animal_off_the_books_says_what_happens_to_its_bookings(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)
    book_consultation(app, client_id, animal_id)

    response = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})
    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))

    assert "1 appointment" in page
    assert "already in the book for Moss" in page
    assert "is unchanged." in page


def test_an_animal_can_be_put_back_on_the_books(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)
    client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})

    response = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "1"})
    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))

    assert "Moss is back on the books and can be booked again." in page
    assert "Moss" in unescape(client.get("/consultations/new?date=2026-09-30").get_data(as_text=True))

    with app.app_context():
        assert db.session.get(Animal, animal_id).active is True


def test_removing_an_animal_twice_changes_nothing_the_second_time(app, client):
    client_id = register(client)
    animal_id = record_animal(app, client_id)

    first = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})
    second = client.post(f"/clients/{client_id}/animals/{animal_id}/active", data={"active": "0"})

    assert first.status_code == 303 and second.status_code == 303
    with app.app_context():
        assert db.session.get(Animal, animal_id).active is False
        assert Animal.query.count() == 1
