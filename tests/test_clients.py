"""Story MSD426GXUST3-39: creating a client record."""
import sqlite3
from html import unescape
from pathlib import Path

from app.models import Client

VALID = {
    "name": "Bridie Callaghan",
    "phone": "0417 884 260",
    "email": "bridie@kalinga.example",
    "postal_address": "PO Box 88, Boonah 4310",
    "notes": "Moved down from Toowoomba in March; records still at their old vet.",
    "sms_consent": "on",
}


def register(client, **overrides):
    """Post the registration form, overriding or dropping fields as asked."""
    form = dict(VALID)
    for field, value in overrides.items():
        if value is None:
            form.pop(field, None)
        else:
            form[field] = value
    return client.post("/clients/new", data=form)


def test_the_form_asks_for_a_name_and_a_phone_number(client):
    response = client.get("/clients/new")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Add a client" in page
    assert "Full name" in page and "Phone number" in page
    assert 'name="name"' in page and 'name="phone"' in page
    assert "Email (optional)" in page


def test_a_valid_client_is_saved_and_then_shown_in_the_client_list(app, client):
    response = register(client)
    assert response.status_code == 303

    listing = client.get(response.headers["Location"])
    page = listing.get_data(as_text=True)
    assert listing.status_code == 200
    assert "Bridie Callaghan" in page
    assert "0417 884 260" in page
    assert "is now on file" in page

    with app.app_context():
        saved = Client.query.one()
        assert saved.name == "Bridie Callaghan"
        assert saved.phone == "0417 884 260"
        assert saved.email == "bridie@kalinga.example"
        assert saved.postal_address == "PO Box 88, Boonah 4310"
        assert saved.notes.startswith("Moved down from Toowoomba")
        assert saved.sms_consent is True
        assert saved.active is True
        assert saved.created_at is not None


def test_the_optional_details_can_be_left_out(app, client):
    response = register(
        client,
        name="Kelso",
        phone="0413 660 288",
        email=None,
        postal_address=None,
        notes=None,
        sms_consent=None,
    )
    assert response.status_code == 303

    with app.app_context():
        saved = Client.query.one()
        assert saved.email is None
        assert saved.postal_address is None
        assert saved.notes is None
        assert saved.sms_consent is False


def test_the_new_client_joins_the_list_in_name_order(app, client):
    register(client, name="Zoe Zimmer", phone="0427 118 004")
    register(client, name="Alan Appleby", phone="0427 118 005")

    page = client.get("/clients/").get_data(as_text=True)
    assert "Alan Appleby" in page and "Zoe Zimmer" in page
    assert page.index("Alan Appleby") < page.index("Zoe Zimmer")


def test_a_missing_name_is_explained(app, client):
    response = register(client, name="")
    assert response.status_code == 400
    page = unescape(response.get_data(as_text=True))
    assert "Enter the client's full name." in page
    with app.app_context():
        assert Client.query.count() == 0


def test_a_name_of_spaces_is_not_a_name(app, client):
    register(client, name="   ")
    with app.app_context():
        assert Client.query.count() == 0


def test_a_missing_phone_number_is_explained(app, client):
    response = register(client, phone="")
    assert "Enter a phone number" in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_a_phone_number_that_is_not_a_phone_number_is_rejected(app, client):
    response = register(client, phone="ring the daughter")
    assert "phone number does not look right" in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_a_truncated_phone_number_is_rejected(app, client):
    response = register(client, phone="0417")
    assert "phone number does not look right" in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_a_malformed_email_is_rejected(app, client):
    response = register(client, email="bridie@kalinga")
    assert "email address does not look right" in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_an_overlong_name_is_rejected(app, client):
    response = register(client, name="A" * 121)
    assert "Keep the name to 120 characters or fewer." in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_an_overlong_postal_address_is_rejected(app, client):
    response = register(client, postal_address="x" * 256)
    assert "255 characters or fewer" in response.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_a_rejected_form_keeps_what_was_typed(client):
    page = register(client, email="not-an-email").get_data(as_text=True)
    assert 'value="Bridie Callaghan"' in page
    assert 'value="0417 884 260"' in page
    assert 'value="not-an-email"' in page


def test_the_validation_bubbles_use_the_shared_script(client):
    page = client.get("/clients/new").get_data(as_text=True)
    assert "data-error=\"Please enter the client's full name.\"" in page
    assert "js/form-validation.js" in page


def test_the_client_is_written_to_the_local_sqlite_file(app, client):
    register(client)

    database_file = Path(
        app.config["SQLALCHEMY_DATABASE_URI"].removeprefix("sqlite:///")
    )
    assert database_file.is_file()

    with sqlite3.connect(database_file) as connection:
        rows = connection.execute("SELECT name, phone FROM clients").fetchall()
    assert ("Bridie Callaghan", "0417 884 260") in rows
