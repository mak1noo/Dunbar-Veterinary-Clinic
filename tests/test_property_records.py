"""Story MSD426GXUST3-44: recording a client's farm property."""
from app.models import Animal, Client, Property, db

VALID = {
    "name": "Stony Creek",
    "locality": "Bunjurgen",
    "preferred_run_day": "2",
}


def add_client(name="Bridie Callaghan", phone="0417 884 260"):
    """Put a client on the register the way the registration form would."""
    record = Client(name=name, phone=phone)
    db.session.add(record)
    db.session.commit()
    return record.id


def add_property(app, **overrides):
    """Post the property form for a client, overriding or dropping fields."""
    form = dict(VALID)
    for field, value in overrides.items():
        if value is None:
            form.pop(field, None)
        else:
            form[field] = value
    return form


def test_the_form_asks_for_a_property_name_and_a_locality(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.get(f"/clients/{client_id}/properties/new")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Add a farm property" in page
    assert "Property name" in page and "Locality" in page
    assert 'name="name"' in page and 'name="locality"' in page
    assert "Usual run day (optional)" in page


def test_a_valid_property_is_saved_and_shown_on_the_client_page(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.post(f"/clients/{client_id}/properties/new", data=add_property(app))
    assert response.status_code == 303

    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Stony Creek" in page and "Bunjurgen" in page
    assert "is now on file for this client" in page

    with app.app_context():
        saved = Property.query.one()
        assert saved.name == "Stony Creek"
        assert saved.locality == "Bunjurgen"
        assert saved.client_id == client_id
        assert saved.preferred_run_day == 2
        assert saved.active is True


def test_a_property_without_a_name_is_refused_with_a_clear_message(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.post(f"/clients/{client_id}/properties/new", data=add_property(app, name=None))
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Enter the property name" in page
    assert "Bunjurgen" in page, "the locality already typed stays in the form"
    with app.app_context():
        assert Property.query.count() == 0, "nothing is written when the form is refused"


def test_a_property_without_a_locality_is_refused_with_a_clear_message(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.post(f"/clients/{client_id}/properties/new", data=add_property(app, locality=None))
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Enter the locality" in page
    with app.app_context():
        assert Property.query.count() == 0


def test_the_property_lands_on_the_client_in_the_address_not_on_a_form_field(app, client):
    """The client comes from the URL, so a posted client_id cannot redirect it."""
    with app.app_context():
        owner_id = add_client()
        bystander_id = add_client("Nguyen Family Trust", "07 5463 1180")
    form = add_property(app)
    form["client_id"] = str(bystander_id)
    response = client.post(f"/clients/{owner_id}/properties/new", data=form)
    assert response.status_code == 303
    with app.app_context():
        saved = Property.query.one()
        assert saved.client_id == owner_id, "the address decides whose property it is"


def test_every_property_belonging_to_one_client_is_listed(app, client):
    with app.app_context():
        found = add_client()
        other = add_client("Nguyen Family Trust", "07 5463 1180")
        db.session.add(Property(client_id=found, name="Stony Creek", locality="Bunjurgen"))
        db.session.add(Property(client_id=found, name="Kalinga Park", locality="Boonah"))
        db.session.add(Property(client_id=other, name="Riverbend", locality="Kalbar"))
        db.session.commit()
    page = client.get(f"/clients/{found}").get_data(as_text=True)
    assert "Stony Creek" in page and "Kalinga Park" in page
    assert "Riverbend" not in page, "another client's property is not on this page"


def test_a_client_can_have_animals_properties_both_or_neither(app, client):
    """The third acceptance criterion: the two kinds of record are independent."""
    with app.app_context():
        neither = add_client("Neither", "07 5463 0001")
        animals_only = add_client("Animals Only", "07 5463 0002")
        db.session.add(Animal(client_id=animals_only, name="Moss", species="Dog"))
        properties_only = add_client("Properties Only", "07 5463 0003")
        db.session.add(Property(client_id=properties_only, name="Stony Creek", locality="Bunjurgen"))
        both = add_client("Both", "07 5463 0004")
        db.session.add(Animal(client_id=both, name="Tilly", species="Cat"))
        db.session.add(Property(client_id=both, name="Kalinga Park", locality="Boonah"))
        db.session.commit()

    cases = [
        (neither, "No animals on file for this client yet.", "No farm properties on file for this client."),
        (animals_only, "Moss", "No farm properties on file for this client."),
        (properties_only, "No animals on file for this client yet.", "Stony Creek"),
        (both, "Tilly", "Kalinga Park"),
    ]
    for client_id, animal_expected, property_expected in cases:
        response = client.get(f"/clients/{client_id}")
        page = response.get_data(as_text=True)
        assert response.status_code == 200
        assert animal_expected in page
        assert property_expected in page


def test_a_property_cannot_be_recorded_without_a_client(app, client):
    """There is no form for a property that belongs to nobody."""
    missing = client.get("/clients/999/properties/new")
    assert missing.status_code == 404
    posted = client.post("/clients/999/properties/new", data=dict(VALID))
    assert posted.status_code == 404
    with app.app_context():
        assert Property.query.count() == 0


def test_the_usual_run_day_is_optional(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.post(
        f"/clients/{client_id}/properties/new",
        data=add_property(app, preferred_run_day=None),
    )
    assert response.status_code == 303
    with app.app_context():
        assert Property.query.one().preferred_run_day is None


def test_a_run_day_out_of_range_is_refused(app, client):
    with app.app_context():
        client_id = add_client()
    response = client.post(
        f"/clients/{client_id}/properties/new",
        data=add_property(app, preferred_run_day="9"),
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Choose a preferred run day" in page
    with app.app_context():
        assert Property.query.count() == 0


def test_a_name_or_locality_that_is_too_long_is_refused(app, client):
    with app.app_context():
        client_id = add_client()
    too_long = "x" * 121
    for field, message in (("name", "Keep the property name"), ("locality", "Keep the locality")):
        response = client.post(
            f"/clients/{client_id}/properties/new",
            data=add_property(app, **{field: too_long}),
        )
        assert response.status_code == 400
        assert message in response.get_data(as_text=True)
    with app.app_context():
        assert Property.query.count() == 0


def test_the_saved_property_is_trimmed(app, client):
    with app.app_context():
        client_id = add_client()
    client.post(
        f"/clients/{client_id}/properties/new",
        data=add_property(app, name="  Stony Creek  ", locality="  Bunjurgen  "),
    )
    with app.app_context():
        saved = Property.query.one()
        assert saved.name == "Stony Creek"
        assert saved.locality == "Bunjurgen"


def test_a_new_property_can_be_added_for_a_client_that_already_has_one(app, client):
    with app.app_context():
        client_id = add_client()
    first = client.post(f"/clients/{client_id}/properties/new", data=add_property(app))
    second = client.post(
        f"/clients/{client_id}/properties/new",
        data=add_property(app, name="Kalinga Park", locality="Boonah"),
    )
    assert first.status_code == 303 and second.status_code == 303
    with app.app_context():
        names = sorted(record.name for record in Property.query.all())
        assert names == ["Kalinga Park", "Stony Creek"]
