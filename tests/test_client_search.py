"""Story MSD426GXUST3-40 (follow-up): finding a client, and stopping one.

The register is read two ways the first pass at the story did not cover: by the
name the caller gives, and by the number they ring from. It also has to be able
to stop work for a client without losing the record, because the bookings
already made against it are the clinic's history and the client may come back.

These tests cover the search itself (name, phone, nothing found, and a wildcard
that is part of a name rather than a pattern) and the stop / restore flag,
including the promise that a stopped client is still found and clearly marked.
"""
import re
from html import unescape

from app.models import Client, db

VALID = {
    "name": "Bridie Callaghan",
    "phone": "0417 884 260",
    "email": "bridie@kalinga.example",
    "postal_address": "PO Box 88, Boonah 4310",
    "notes": "",
    "sms_consent": "",
}

ADDED_ID = re.compile(r"added=(\d+)")


def register(client, **overrides):
    """Put one client on the register and return the id they were given."""
    form = dict(VALID)
    form.update(overrides)
    response = client.post("/clients/new", data=form)
    assert response.status_code == 303, response.get_data(as_text=True)
    return int(ADDED_ID.search(response.headers["Location"]).group(1))


def search(client, term):
    """The client list as one search renders it."""
    response = client.get("/clients/", query_string={"q": term})
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_a_search_by_name_finds_the_client(client):
    register(client)
    page = search(client, "Callaghan")
    assert "Bridie Callaghan" in page
    assert "1 record" in page


def test_a_search_by_name_ignores_capitalisation(client):
    register(client)
    assert "Bridie Callaghan" in search(client, "cALLaghan")


def test_a_search_by_phone_number_finds_the_client(client):
    register(client)
    assert "Bridie Callaghan" in search(client, "884 260")
    assert "Bridie Callaghan" in search(client, "0417")


def test_a_search_leaves_out_the_clients_it_does_not_match(client):
    register(client)
    register(client, name="Tom Whitlock", phone="0455 118 902")
    page = search(client, "Whitlock")
    assert "Tom Whitlock" in page
    assert "Bridie Callaghan" not in page


def test_a_search_that_matches_nothing_says_so_instead_of_failing(client):
    register(client)
    page = search(client, "Nobody")
    assert "Nothing on the register matches" in page
    assert "Bridie Callaghan" not in page


def test_the_whole_register_is_shown_when_nothing_is_being_searched_for(client):
    register(client)
    register(client, name="Tom Whitlock", phone="0455 118 902")
    page = unescape(client.get("/clients/").get_data(as_text=True))
    assert "Bridie Callaghan" in page
    assert "Tom Whitlock" in page


def test_a_wildcard_in_a_name_is_a_name_and_not_a_pattern(client):
    register(client, name="50% Off Farm Supplies", phone="0417 000 111")
    register(client, name="Tom Whitlock", phone="0455 118 902")

    page = search(client, "50%")
    assert "50% Off Farm Supplies" in page
    assert "Tom Whitlock" not in page

    # A lone wildcard must not turn into "match every client on the register".
    page = search(client, "%")
    assert "50% Off Farm Supplies" in page
    assert "Tom Whitlock" not in page


def test_an_empty_search_returns_the_register_rather_than_nothing(client):
    register(client)
    page = search(client, "   ")
    assert "Bridie Callaghan" in page


def test_stopping_a_client_keeps_the_record_and_marks_it(app, client):
    client_id = register(client)
    response = client.post(f"/clients/{client_id}/active", data={"active": "0"})

    assert response.status_code == 303
    assert response.headers["Location"].endswith(f"/clients/{client_id}?changed=1")

    with app.app_context():
        record = Client.query.one()
        assert record.id == client_id
        assert record.active is False

    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))
    assert "Work for Bridie Callaghan has been stopped" in page
    assert "Put this client back on the active list" in page


def test_a_stopped_client_is_still_found_by_a_search_and_clearly_marked(app, client):
    client_id = register(client)
    client.post(f"/clients/{client_id}/active", data={"active": "0"})

    page = search(client, "Callaghan")
    assert "Bridie Callaghan" in page
    assert "tag-stopped" in page
    assert "Stopped" in page


def test_a_client_can_be_put_back_on_the_active_list(app, client):
    client_id = register(client)
    client.post(f"/clients/{client_id}/active", data={"active": "0"})
    response = client.post(f"/clients/{client_id}/active", data={"active": "1"})

    assert response.status_code == 303
    with app.app_context():
        assert Client.query.one().active is True

    page = unescape(client.get(response.headers["Location"]).get_data(as_text=True))
    assert "Bridie Callaghan is back on the active list" in page
    assert "Stop work for this client" in page


def test_an_active_client_is_marked_active_on_the_list(client):
    register(client)
    assert "tag-active" in search(client, "Callaghan")


def test_stopping_an_unknown_client_has_no_page(client):
    response = client.post("/clients/4321/active", data={"active": "0"})
    assert response.status_code == 404
