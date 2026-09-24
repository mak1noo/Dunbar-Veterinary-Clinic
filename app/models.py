"""Database models for the Dunbar Veterinary Clinic appointment system.

The clinic books two different kinds of work and they are not the same shape
(case study section 4). The models keep that distinction honest instead of
forcing both into one shape with fields left blank:

* a **consultation** is booked for one animal, into one 15-minute slot, in one
  of the two consulting rooms;
* a **farm visit** is booked against a property, with a start time and an
  estimated duration in hours.

The check constraints below are a backstop for the service layer: a database
row can never hold a booking that mixes the two shapes, and a room and slot
cannot hold two live consultations.
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

CONSULTATION = "consultation"
FARM_VISIT = "farm_visit"

STATUS_BOOKED = "booked"
STATUS_CANCELLED = "cancelled"
STATUS_COMPLETED = "completed"
STATUS_NO_SHOW = "no_show"

APPOINTMENT_KINDS = (CONSULTATION, FARM_VISIT)
APPOINTMENT_STATUSES = (STATUS_BOOKED, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_NO_SHOW)


def _utcnow():
    return datetime.now(timezone.utc)


def ensure_schema_compatibility():
    """Apply the small schema upgrades that ``create_all`` cannot perform."""
    inspector = sa.inspect(db.engine)
    if "appointments" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("appointments")}
    if "head_count" not in columns:
        with db.engine.begin() as connection:
            connection.execute(sa.text("ALTER TABLE appointments ADD COLUMN head_count INTEGER"))


class Client(db.Model):
    """A household or a farming business."""

    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(255))
    postal_address = db.Column(db.String(255))
    sms_consent = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    animals = db.relationship("Animal", back_populates="client", cascade="all, delete-orphan")
    properties = db.relationship("Property", back_populates="client", cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="client")

    def __repr__(self):  # pragma: no cover - debug helper
        return f"<Client {self.id} {self.name!r}>"


class Animal(db.Model):
    """An animal belonging to one client."""

    __tablename__ = "animals"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False, index=True)
    species = db.Column(db.String(60), nullable=False)
    breed = db.Column(db.String(120))
    sex = db.Column(db.String(20))
    desexed = db.Column(db.Boolean, nullable=False, default=False)
    date_of_birth = db.Column(db.Date)
    microchip = db.Column(db.String(40))
    insured = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text)

    client = db.relationship("Client", back_populates="animals")
    appointments = db.relationship("Appointment", back_populates="animal")

    def __repr__(self):  # pragma: no cover - debug helper
        return f"<Animal {self.id} {self.name!r} ({self.species})>"


class Property(db.Model):
    """A farm property belonging to one client."""

    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False, index=True)
    locality = db.Column(db.String(120), nullable=False)
    access_notes = db.Column(db.Text)
    preferred_run_day = db.Column(db.SmallInteger)  # 0 = Monday ... 6 = Sunday
    active = db.Column(db.Boolean, nullable=False, default=True)

    client = db.relationship("Client", back_populates="properties")
    appointments = db.relationship("Appointment", back_populates="farm_property")

    def __repr__(self):  # pragma: no cover - debug helper
        return f"<Property {self.id} {self.name!r} ({self.locality})>"


class Appointment(db.Model):
    """A booking: either an in-clinic consultation or a farm visit."""

    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_BOOKED)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Consultation shape.
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"))
    room = db.Column(db.SmallInteger)

    # Farm visit shape.
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"))
    estimated_hours = db.Column(db.Numeric(4, 2))
    head_count = db.Column(db.Integer)

    client = db.relationship("Client", back_populates="appointments")
    animal = db.relationship("Animal", back_populates="appointments")
    farm_property = db.relationship("Property", back_populates="appointments")

    __table_args__ = (
        sa.CheckConstraint("kind IN ('consultation', 'farm_visit')", name="ck_appointment_kind"),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed', 'no_show')",
            name="ck_appointment_status",
        ),
        sa.CheckConstraint(
            "(kind = 'consultation' AND animal_id IS NOT NULL AND room IN (1, 2)"
            " AND property_id IS NULL AND estimated_hours IS NULL)"
            " OR (kind = 'farm_visit' AND property_id IS NOT NULL AND animal_id IS NULL"
            " AND room IS NULL AND estimated_hours IS NOT NULL AND estimated_hours > 0)",
            name="ck_appointment_shape",
        ),
        sa.Index(
            "uq_consultation_room_slot",
            "date",
            "start_time",
            "room",
            unique=True,
            sqlite_where=sa.text("kind = 'consultation' AND status = 'booked'"),
        ),
    )

    def __repr__(self):  # pragma: no cover - debug helper
        return f"<Appointment {self.id} {self.kind} {self.date} {self.start_time} ({self.status})>"

    @property
    def kind_label(self):
        """Return the user-facing label for this appointment kind."""
        if self.kind == CONSULTATION:
            return "Consultation"
        if self.kind == FARM_VISIT:
            return "Farm visit"
        return self.kind.replace("_", " ").title()

    @property
    def status_label(self):
        """Return the user-facing label for this appointment status."""
        return self.status.replace("_", " ").title()
