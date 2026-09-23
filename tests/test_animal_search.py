"""Story MSD426GXUST3-42: finding an animal by name across the register."""
from app.models import Animal, Client, db
from app.services.records import animal_name_pattern


def keep(app, name, phone, animals=()):
    """Put a client on file, with the animals they own, and return the new id."""
    with app.app_context():
        record = Client(name=name, phone=phone)
        for animal_name, species, active in animals:
            record.animals.append(Animal(name=animal_name, species=species, active=active))
        db.session.add(record)
        db.session.commit()
        return record.id


def search(client, term):
    """Search the register the way the front desk does, through the search box."""
    return client.get("/animals/search", query_string={"name": term})


def test_the_form_asks_for_the_animals_name(client):
    response = client.get("/animals/search")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Find an animal" in page
    assert 'name="name"' in page
    assert "Type a name" in page


def test_a_name_is_found_across_every_client(app, client):
    keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])
    keep(app, "Bridie Callaghan", "0417 884 260", [("Jedda", "Dog", True)])
    keep(app, "Kelso", "0413 660 288", [("Nutmeg", "Cat", True)])

    page = search(client, "Jed").get_data(as_text=True)

    # Both matches, from two different clients, and nothing that did not match.
    assert "Jed" in page and "Jedda" in page
    assert "Nutmeg" not in page
    assert "2 matches" in page


def test_every_match_carries_the_owner_and_a_contact_number(app, client):
    sanderson = keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])
    keep(app, "Bridie Callaghan", "0417 884 260", [("Jedda", "Dog", True)])

    page = search(client, "Jed").get_data(as_text=True)

    assert "D Sanderson" in page and "0438 907 221" in page
    assert "Bridie Callaghan" in page and "0417 884 260" in page
    assert 'href="/clients/%d"' % sanderson in page
    assert "Dog" in page


def test_the_search_does_not_care_about_capitals(app, client):
    keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])
    assert "Jed" in search(client, "jEd").get_data(as_text=True)


def test_part_of_a_name_is_enough_to_find_it(app, client):
    keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])
    keep(app, "Kelso", "0413 660 288", [("Nutmeg", "Cat", True)])
    page = search(client, "ed").get_data(as_text=True)
    assert "Jed" in page
    assert "Nutmeg" not in page


def test_a_name_with_no_matches_is_an_empty_result_not_an_error(app, client):
    keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])

    response = search(client, "Tiberius")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No animal on the register matches" in page
    # No results table at all: the animal is not listed as a match.
    assert "<table" not in page


def test_an_empty_search_asks_for_a_name_instead_of_listing_the_register(app, client):
    keep(app, "D Sanderson", "0438 907 221", [("Jed", "Dog", True)])

    for empty in ("", "   "):
        response = search(client, empty)
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Type a name" in page
        # An empty box lists nothing: the register is not dumped on the screen.
        assert "<table" not in page


def test_a_wildcard_typed_into_the_box_matches_the_character_and_not_everything(app, client):
    keep(app, "Kelso", "0413 660 288", [("Biscuit", "Cat", True), ("Ollie", "Dog", True)])

    # If % and _ were passed through, these three searches would return the
    # whole register instead of nothing.
    for wildcard in ("%", "_", "%%", "%i%"):
        page = search(client, wildcard).get_data(as_text=True)
        assert "No animal on the register matches" in page
        assert "Biscuit" not in page

    # The ordinary characters around them still work.
    assert "Biscuit" in search(client, "iscui").get_data(as_text=True)


def test_an_animal_taken_off_the_books_is_still_found_and_marked(app, client):
    keep(app, "Kelso", "0413 660 288", [("Jed", "Dog", False)])
    page = search(client, "Jed").get_data(as_text=True)
    assert "Jed" in page
    assert "removed" in page


def test_the_search_is_reachable_from_every_page(client):
    page = client.get("/").get_data(as_text=True)
    assert 'href="/animals/search"' in page


def test_an_empty_search_box_has_no_pattern_to_search_with():
    assert animal_name_pattern("") is None
    assert animal_name_pattern("   ") is None
    assert animal_name_pattern(None) is None


def test_the_pattern_matches_anywhere_in_the_name():
    assert animal_name_pattern("  Jed ") == "%Jed%"
    assert animal_name_pattern("ed") == "%ed%"


def test_the_pattern_escapes_the_characters_like_would_read_as_wildcards():
    assert animal_name_pattern(r"100%") == r"%100\%%"
    assert animal_name_pattern(r"a_b") == r"%a\_b%"
    assert animal_name_pattern("50/50") == "50/50".join(["%", "%"])
