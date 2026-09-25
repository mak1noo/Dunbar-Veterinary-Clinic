"""Tests for offline operation and local persistence (MSD426GXUST3-55)."""
from app import create_app
from app.models import Client, db
from app.services.offline import (
    database_is_local,
    database_persists,
    external_runtime_references,
    offline_report,
)


def test_sqlite_is_detected_as_local_and_persistent():
    uri = "sqlite:///C:/clinic/data/dunbar.sqlite3"
    assert database_is_local(uri) is True
    assert database_persists(uri) is True


def test_in_memory_sqlite_is_local_but_not_persistent():
    uri = "sqlite://"
    assert database_is_local(uri) is True
    assert database_persists(uri) is False


def test_runtime_templates_and_assets_do_not_use_external_urls(app):
    assert external_runtime_references(app) == []


def test_offline_report_is_ready_for_the_test_database(app):
    report = offline_report(app)

    assert report["ok"] is True
    assert report["database_engine"] == "SQLite"
    assert report["local_database"] is True
    assert report["persistent_database"] is True
    assert report["external_references"] == []


def test_offline_status_page_explains_local_operation(client):
    response = client.get("/offline-status")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Offline operation status" in page
    assert "Offline ready" in page
    assert "SQLite" in page
    assert "No CDN" not in page
    assert "http://" not in page
    assert "https://" not in page


def test_data_survives_an_application_restart(tmp_path):
    database_file = tmp_path / "restart.sqlite3"
    config = {
        "TESTING": True,
        "SECRET_KEY": "restart-test",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_file}",
    }

    first_app = create_app(config)
    with first_app.app_context():
        db.create_all()
        db.session.add(Client(name="Restart Test", phone="0400 000 000"))
        db.session.commit()
        db.session.remove()
        db.engine.dispose()

    second_app = create_app(config)
    with second_app.app_context():
        saved = Client.query.filter_by(name="Restart Test").one()
        assert saved.phone == "0400 000 000"
        db.session.remove()
        db.engine.dispose()
