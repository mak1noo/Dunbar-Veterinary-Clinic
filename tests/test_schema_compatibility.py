"""Tests for the self-healing head_count schema upgrade."""
import sqlite3

from app import create_app


def test_existing_database_gains_the_head_count_column(tmp_path):
    database_file = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(database_file)
    connection.execute(
        """
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY,
            kind VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            client_id INTEGER NOT NULL,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            reason TEXT,
            notes TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            animal_id INTEGER,
            room SMALLINT,
            property_id INTEGER,
            estimated_hours NUMERIC(4, 2)
        )
        """
    )
    connection.commit()
    connection.close()

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "schema-test",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_file}",
        }
    )

    with app.app_context():
        columns = {
            row[1]
            for row in app.extensions["sqlalchemy"].engine.connect().exec_driver_sql(
                "PRAGMA table_info(appointments)"
            )
        }

    assert "head_count" in columns
