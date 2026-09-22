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
