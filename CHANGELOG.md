# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the
project uses semantic-ish version numbers (v0.x during delivery, v1.0 at handover).

## [Unreleased]

### Added

- 2026-09-20 — Repository bootstrap: README, .gitignore, requirements.
- 2026-09-20 — Project scaffold: Flask application factory, SQLite models for
  clients, animals, properties and the two kinds of appointments, consulting
  timetable rules and booking validation helpers, pytest suite, GitHub Actions
  CI, pull request template, and a seed script with the case study's sample data.
- 2026-09-22 — MSD426GXUST3-54: cancellations retain the appointment record,
  mark it as cancelled, keep it distinguishable from live bookings, protect
  completed/no-show records, free the slot for a fresh booking and leave all
  other appointments unchanged.
- 2026-09-20 — MSD426GXUST3-51: ordered farm run view showing property,
  locality, client contact, job, head count, estimated time and access notes;
  cancelled visits are excluded.
- 2026-09-20 — MSD426GXUST3-52: client appointment history across all dates,
  showing date, time, appointment kind, status and booking detail, including
  cancelled appointments.
- 2026-09-21 — MSD426GXUST3-53: appointment rescheduling for consultations and
  farm visits, reusing the new-booking validation rules and updating only the
  selected appointment, and refusing to move cancelled or finished records.

- 2026-09-21 — In-clinic consultation booking (`MSD426GXUST3-46`): reception
  form for one animal, one 15-minute slot and one of the two consulting rooms,
  server-side validation against the consulting timetable, a booking
  confirmation page, and automated tests.
- 2026-09-21 — Deployment configuration: `.env` support with a checked-in
  `.env.example`, bootstrap and run scripts for Windows and Unix, a WSGI entry
  point, and a deployment guide (`docs/DEPLOYMENT.md`).
- 2026-09-22 — Timetable rules around a booking (`MSD426GXUST3-47`): nothing
  in the past, and the booking form shows which consulting rooms are still free
  for each 15-minute slot, disabling slots where both rooms are taken.


- 2026-09-22 — Client records (`MSD426GXUST3-39`): the front desk can add a
  client with the required full name and phone number plus optional email,
  postal address, notes and SMS consent, with the rules in
  `app/services/records.py`, the new client shown at once in the client list,
  and automated tests for the valid and invalid paths.
- 2026-09-23 — Viewing and correcting a client record (`MSD426GXUST3-40`): each
  client in the register now has a page of their own showing the details on
  file alongside their animals and farm properties, with a correction form
  that leads on from it. The same rules validate an addition and a
  correction, a rejected correction leaves the register untouched, and the
  record is changed in place so the client id and every booking already made
  against it survive. Automated tests cover the read path, the write path and
  the rejected paths.
- 2026-09-23 — Offline operation (`MSD426GXUST3-55`): an offline status page
  reports local SQLite storage and scans runtime templates/assets for external
  HTTP dependencies. Tests verify local configuration, no runtime external
  references and persistence of records across an application restart.
- 2026-09-24 — Farm visit booking (`MSD426GXUST3-48`): the green diary page
  books a visit against a property with a start time and an estimated duration
  in half-hour steps, keeps the client on the booking through the property, and
  ends on a confirmation page that repeats the access notes.
