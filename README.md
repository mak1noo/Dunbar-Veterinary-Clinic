# Dunbar Veterinary Clinic — Appointment System

A small web application for **ISYS3001 Managing Software Development** (Southern Cross University),
based on Case Study 5: *Dunbar Veterinary Clinic*.

The clinic currently books everything on a single paper appointment book (in-clinic
consultations) and a green diary (farm visits). This project delivers one appointment
system that holds both kinds of work, so the front desk, the vets and the owner can all
see the same day.

## Team

| GitHub account | Notes |
|---|---|
| [@mak1noo](https://github.com/mak1noo) | project owner |
| [@1802168960-star](https://github.com/1802168960-star) | team member |
| [@Codesprout-91](https://github.com/Codesprout-91) | team member |

## Tech stack

- Python 3 + Flask
- SQLite (local database file, no server required)
- pytest for automated tests
- No CDN or external services: the application must work when the clinic's internet is down

## Planned scope (Sprint 1)

- Clients, animals and farm properties: create, find, update, deactivate
- Two kinds of appointments:
  - in-clinic consultation: 15-minute slot, one animal, one of two consulting rooms
  - farm visit: booked against a property, start time + estimated hours
- Day views: consulting timetable (taken and free slots), farm run list, client appointments
- Reschedule and cancel (cancelled appointments stay visible in the record)

Out of scope for this project (kept in the product backlog): clinical records,
prescriptions and the drug register, invoicing, vaccination reminders, SMS/email,
client self-booking, surgery/theatre list, route planning, after-hours roster, stock,
and VetLedger data migration.

## Repository conventions

- `main` is the protected branch; all work arrives through pull requests.
- Branch names: `story/<JIRA-KEY>-short-name` (one branch per user story).
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- Every pull request is reviewed by another team member before merging.
- Every user story carries automated tests; the Definition of Done is fixed by the unit.

## Running the application

Prerequisites: Python 3.11+ and Git. No internet connection is needed at run time.

```bash
git clone https://github.com/mak1noo/Dunbar-Veterinary-Clinic.git
cd Dunbar-Veterinary-Clinic
python -m venv .venv

# Windows
.venv\Scripts\python -m pip install -r requirements.txt
# macOS / Linux
# .venv/bin/python -m pip install -r requirements.txt

python scripts/seed_data.py        # create the database with sample data
python run.py                      # start the app on http://127.0.0.1:5000
```

On Windows the same steps are wrapped in two scripts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1   # venv + dependencies + .env + sample data
powershell -ExecutionPolicy Bypass -File scripts\run.ps1         # start the app
```

Run the test suite:

```bash
python -m pytest -q
```

## Configuration

Settings are read from environment variables, or from a `.env` file copied from
`.env.example`; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the settings,
the small-server setup and backup notes.

## Implemented views

- `GET/POST /appointments/<id>/cancel` cancels a live booking without deleting
  its record. Cancelled appointments remain visible and are distinguishable
  from live bookings; completed and no-show records are protected from
  cancellation, and no other appointment is changed.
- `GET /farm-run?date=YYYY-MM-DD` shows the day's active farm visits in working
  order, including property, locality, client contact, job, head count,
  estimated duration and access notes. An empty day returns an empty list.
- `GET /clients/<id>/appointments`, linked from the client record, shows every
  appointment for that client across all dates, including the appointment kind,
  status and booking detail.
- `GET/POST /appointments/<id>/reschedule` provides a rescheduling form for
  both consultation and farm-visit appointments. It reuses new-booking
  validation, moves only the selected appointment and reports validation errors.

## Offline operation

- Open `/offline-status` to check that the application is using local SQLite
  storage and has no external runtime asset references.
- Automated tests verify that the default database is local, that records
  survive an application restart, and that templates/static files do not depend
  on a CDN or other external HTTP resource.

## Project structure

```
app/__init__.py          application factory
app/models.py            clients, animals, properties, appointments
app/services/            consulting timetable rules and booking validation
app/routes/              HTTP routes, grouped by module
app/templates/           server-rendered pages
app/static/              local CSS and assets (no CDN)
scripts/seed_data.py     sample data from the case study documents
tests/                   pytest suite
```

## Team workflow

Every user story is delivered on a branch named `story/MSD426GXUST3-<number>-<short-name>`,
reviewed through a pull request, and closed out in Jira.

## Links

- Jira project: https://scu-it.atlassian.net/jira/software/c/projects/MSD426GXUST3/boards/1995/backlog
- Confluence space: https://scu-it.atlassian.net/wiki/spaces/MSD426GXUST3
