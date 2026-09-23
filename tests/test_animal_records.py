"""Story MSD426GXUST3-41: recording an animal against a client.

An animal is not a record of its own. It belongs to the household or business
that will be billed for it, so it is always added from the client page it
belongs to, and there is no form anywhere that could save one on its own.

The tests below cover the path reception takes, the two fields the story
insists on, the way a rejected form is handed back with what was typed still
in it, and the ownerless path: a client who is not on the register has nothing
to add an animal to.
"""
import re
from html import unescape

from app.models import Animal, Client

VALID = {
    "name": "Moss",
    "species": "Dog",
    "breed": "Kelpie x",
    "sex": "male",
    "date_of_birth": "2019-04-17",
    "microchip": "956000012774318",
    "desexed": "on",
    "notes": "Nervous on the table; muzzle in the car park.",
}

ADDED_ID = re.compile(r"added=(\d+)")


def register(client, name="Bridie Callaghan", phone="0417 884 260"):
    """Put one client on the register and return the id they were given."""
    response = client.post("/clients/new", data={"name": name, "phone": phone})
    assert response.status_code == 303, response.get_data(as_text=True)
    return int(ADDED_ID.search(response.headers["Location"]).group(1))


def add_animal(client, client_id, **overrides):
    """Post the animal form the way reception would."""
    form = dict(VALID)
    form.update(overrides)
    return client.post(f"/clients/{client_id}/animals/new", data=form)


def test_the_form_asks_for_a_name_and_a_species(client):
    client_id = register(client)
    response = client.get(f"/clients/{client_id}/animals/new")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 200
    assert "Add an animal" in page
    assert 'name="name"' in page and 'name="species"' in page
    assert page.count("required") >= 2
    assert "Bridie Callaghan" in page  # the client it will be attached to


def test_a_client_page_leads_to_the_animal_form(client):
    client_id = register(client)
    page = client.get(f"/clients/{client_id}").get_data(as_text=True)
    assert f"/clients/{client_id}/animals/new" in page
    assert "Add an animal" in page


def test_an_animal_can_be_added_with_a_name_and_a_species(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, name="Biscuit", species="Cat", breed="", sex="",
                          date_of_birth="", microchip="", notes="")

    assert response.status_code == 303
    assert response.headers["Location"].startswith(f"/clients/{client_id}?added_animal=")

    with app.app_context():
        animal = Animal.query.one()
        assert animal.name == "Biscuit"
        assert animal.species == "Cat"
        assert animal.client_id == client_id


def test_the_new_animal_is_shown_on_the_client_page(client):
    client_id = register(client)
    response = add_animal(client, client_id, name="Biscuit", species="Cat")
    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))

    assert "Biscuit" in page
    assert "Cat" in page
    assert "has been added to this client's record" in page
    assert "No animals on file for this client yet." not in page


def test_the_optional_details_are_kept(app, client):
    client_id = register(client)
    add_animal(client, client_id)

    with app.app_context():
        animal = Animal.query.one()
        assert animal.breed == "Kelpie x"
        assert animal.sex == "male"
        assert animal.date_of_birth.isoformat() == "2019-04-17"
        assert animal.microchip == "956000012774318"
        assert animal.desexed is True
        assert animal.notes.startswith("Nervous on the table")


def test_the_optional_details_can_be_left_out(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, breed="  ", sex="", date_of_birth="",
                          microchip="", notes="", desexed="")

    assert response.status_code == 303
    with app.app_context():
        animal = Animal.query.one()
        assert animal.breed is None
        assert animal.sex is None
        assert animal.date_of_birth is None
        assert animal.microchip is None
        assert animal.notes is None
        assert animal.desexed is False


def test_every_animal_of_a_client_is_listed(client):
    client_id = register(client)
    add_animal(client, client_id, name="Moss", species="Dog")
    add_animal(client, client_id, name="Tilly", species="Dog")
    add_animal(client, client_id, name="Sooty", species="Cat")

    page = unescape(client.get(f"/clients/{client_id}").get_data(as_text=True))
    assert "Moss" in page and "Tilly" in page and "Sooty" in page


def test_three_animals_are_three_records_not_one(app, client):
    client_id = register(client)
    add_animal(client, client_id, name="Moss", species="Dog")
    add_animal(client, client_id, name="Tilly", species="Dog")
    add_animal(client, client_id, name="Sooty", species="Cat")

    with app.app_context():
        assert Animal.query.count() == 3
        assert {animal.client_id for animal in Animal.query.all()} == {client_id}


def test_an_animal_is_only_listed_under_its_own_client(client):
    first = register(client, name="Bridie Callaghan", phone="0417 884 260")
    second = register(client, name="Krsteski", phone="0428 114 907")
    add_animal(client, first, name="Moss", species="Dog")

    page = unescape(client.get(f"/clients/{second}").get_data(as_text=True))
    assert "Moss" not in page
    assert "No animals on file for this client yet." in page


def test_an_animal_without_a_name_is_not_saved(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, name="   ")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 400
    assert "Enter the animal's name." in page
    with app.app_context():
        assert Animal.query.count() == 0


def test_an_animal_without_a_species_is_not_saved(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, species="")
    page = unescape(response.get_data(as_text=True))

    assert response.status_code == 400
    assert "Enter the species, for example dog, cat or horse." in page
    with app.app_context():
        assert Animal.query.count() == 0


def test_a_rejected_form_is_handed_back_with_what_was_typed(client):
    client_id = register(client)
    page = unescape(add_animal(client, client_id, species="").get_data(as_text=True))

    assert 'value="Moss"' in page
    assert "Kelpie x" in page
    assert "956000012774318" in page
    assert "This animal record cannot be saved yet:" in page


def test_an_animal_cannot_be_saved_without_a_client(app, client):
    response = add_animal(client, 4321, name="Moss", species="Dog")

    assert response.status_code == 404
    with app.app_context():
        assert Animal.query.count() == 0
        assert Client.query.count() == 0


def test_the_form_cannot_be_opened_for_a_client_who_is_not_on_the_register(client):
    assert client.get("/clients/4321/animals/new").status_code == 404


def test_a_date_of_birth_that_is_not_a_date_is_rejected(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, date_of_birth="17/04/2019")

    assert response.status_code == 400
    assert "Enter the date of birth as YYYY-MM-DD" in unescape(response.get_data(as_text=True))
    with app.app_context():
        assert Animal.query.count() == 0


def test_a_date_of_birth_in_the_future_is_rejected(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, date_of_birth="2999-01-01")

    assert response.status_code == 400
    assert "cannot be in the future" in unescape(response.get_data(as_text=True))
    with app.app_context():
        assert Animal.query.count() == 0


def test_a_sex_that_is_not_one_of_the_choices_is_rejected(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, sex="queen")

    assert response.status_code == 400
    assert "Choose female, male or unknown for the sex." in unescape(response.get_data(as_text=True))
    with app.app_context():
        assert Animal.query.count() == 0


def test_a_name_that_is_too_long_is_rejected(app, client):
    client_id = register(client)
    response = add_animal(client, client_id, name="M" * 121)

    assert response.status_code == 400
    assert "Keep the animal's name to 120 characters or fewer." in unescape(response.get_data(as_text=True))
    with app.app_context():
        assert Animal.query.count() == 0


def test_adding_an_animal_leaves_the_client_record_alone(app, client):
    client_id = register(client)
    add_animal(client, client_id)

    with app.app_context():
        record = Client.query.one()
        assert record.id == client_id
        assert record.name == "Bridie Callaghan"
        assert record.phone == "0417 884 260"
        assert len(record.animals) == 1
