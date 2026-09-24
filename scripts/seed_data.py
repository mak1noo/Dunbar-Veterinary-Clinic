"""Create the database and load the sample data used in the case study.

Run:  python scripts/seed_data.py [--reset]

The rows come straight from the case study documents (the appointment book
page, the farm run sheet and the client registration form), so the application
can be demonstrated with the clinic's own examples: Mrs Prosser and Biscuit,
Kalinga Downs, Stony Creek, and so on.
"""
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.models import (  # noqa: E402
    CONSULTATION,
    FARM_VISIT,
    STATUS_BOOKED,
    Animal,
    Appointment,
    Client,
    Property,
    db,
)


def seed(reset=False):
    app = create_app()
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()

        if Client.query.first() is not None:
            print("Database already has data; use --reset to rebuild it.")
            return

        prosser = Client(name="Mrs Prosser", phone="0417 552 118", sms_consent=True)
        krsteski = Client(name="Krsteski", phone="0428 114 907")
        truong = Client(name="Truong", phone="0455 301 662", sms_consent=True)
        kelso = Client(name="Kelso", phone="0413 660 288")
        callaghan = Client(
            name="Bridie & Tom Callaghan",
            phone="0417 884 260",
            email=None,
            postal_address="PO Box 88, Boonah 4310",
            sms_consent=True,
            notes="Moved down from Toowoomba in March; records still at their old vet.",
        )
        petrie = Client(name="R & M Petrie", phone="0427 118 553")
        sanderson = Client(name="D Sanderson", phone="0438 907 221")
        ironbark = Client(name="Ironbark Pastoral Co (mgr K Delaney)", phone="0405 663 118")
        db.session.add_all([prosser, krsteski, truong, kelso, callaghan, petrie, sanderson, ironbark])
        db.session.flush()

        biscuit = Animal(client=prosser, name="Biscuit", species="Cat", breed="DSH", sex="F", desexed=True)
        ollie = Animal(client=krsteski, name="Ollie", species="Dog", sex="M", desexed=True, notes="Lame hind leg.")
        nutmeg = Animal(client=truong, name="Nutmeg", species="Cat")
        clove = Animal(client=truong, name="Clove", species="Cat")
        ruby = Animal(client=kelso, name="Ruby", species="Cat", sex="F", desexed=True)
        moss = Animal(client=callaghan, name="Moss", species="Dog", breed="Kelpie x", sex="M", desexed=True, microchip="956000012774318")
        tilly = Animal(client=callaghan, name="Tilly", species="Dog", breed="Border Collie", sex="F", desexed=True, microchip="956000014029551", insured=True)
        sooty = Animal(client=callaghan, name="Sooty", species="Cat", breed="DSH", sex="F", desexed=True)
        db.session.add_all([biscuit, ollie, nutmeg, clove, ruby, moss, tilly, sooty])

        stony_creek = Property(
            client=callaghan,
            name="Stony Creek",
            locality="Bunjurgen",
            access_notes="3 gates; the last one has a chain and no code. Ring first or you'll be waiting.",
            preferred_run_day=3,  # Thursday — Tom works in town on Tuesdays
        )
        kalinga = Property(
            client=petrie,
            name="Kalinga Downs",
            locality="Coulson",
            access_notes="Gate code 4417. Yards ready by 11:00, Ray is drafting.",
        )
        willow_bend = Property(
            client=sanderson,
            name="Willow Bend",
            locality="Milford",
            access_notes="RING BEFORE YOU TURN IN. Dogs off the chain in the house paddock.",
        )
        ironbark_park = Property(
            client=ironbark,
            name="Ironbark Park",
            locality="Milford",
            access_notes="Same road as Willow Bend, 4 km further on. Always do them together.",
        )
        db.session.add_all([stony_creek, kalinga, willow_bend, ironbark_park])
        db.session.flush()

        consult_day = date(2026, 8, 12)  # Wednesday, from the appointment book page
        db.session.add_all(
            [
                Appointment(kind=CONSULTATION, status=STATUS_BOOKED, client=prosser, animal=biscuit,
                            date=consult_day, start_time=time(8, 30), room=1, reason="F3 vaccination"),
                Appointment(kind=CONSULTATION, status=STATUS_BOOKED, client=krsteski, animal=ollie,
                            date=consult_day, start_time=time(8, 30), room=2, reason="Lame hind leg"),
                Appointment(kind=CONSULTATION, status=STATUS_BOOKED, client=truong, animal=nutmeg,
                            date=consult_day, start_time=time(9, 0), room=2, reason="Vaccination (with Clove)"),
                Appointment(kind=CONSULTATION, status=STATUS_BOOKED, client=kelso, animal=ruby,
                            date=consult_day, start_time=time(10, 45), room=1, reason="Vaccination"),
            ]
        )

        run_day = date(2026, 8, 11)  # Tuesday farm run, from the green diary
        db.session.add_all(
            [
                Appointment(kind=FARM_VISIT, status=STATUS_BOOKED, client=petrie, farm_property=kalinga,
                            date=run_day, start_time=time(11, 15), estimated_hours=Decimal("3.0"), head_count=120,
                            reason="Preg test, 120 head"),
                Appointment(kind=FARM_VISIT, status=STATUS_BOOKED, client=sanderson, farm_property=willow_bend,
                            date=run_day, start_time=time(14, 45), estimated_hours=Decimal("1.0"), head_count=4,
                            reason="Bull soundness, 4 head"),
                Appointment(kind=FARM_VISIT, status=STATUS_BOOKED, client=ironbark, farm_property=ironbark_park,
                            date=run_day, start_time=time(16, 0), estimated_hours=Decimal("1.5"), head_count=1,
                            reason="Lame cow + calf marking check"),
            ]
        )

        db.session.commit()
        print(
            "Seeded: {clients} clients, {animals} animals, {properties} properties, {appointments} appointments.".format(
                clients=Client.query.count(),
                animals=Animal.query.count(),
                properties=Property.query.count(),
                appointments=Appointment.query.count(),
            )
        )


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
