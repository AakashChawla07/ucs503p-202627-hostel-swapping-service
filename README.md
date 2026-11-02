# Hostel Room Swap Service

UCS503 Software Engineering project, TIET Patiala (2026-27 ODD).

Finds multi-party room swap chains so students stuck with the wrong
hostel room can trade out of it, and returns options that differ in
kind rather than a single ranked list.

## Layout

```
code/hostelswap/domain   matching engine, no framework or db imports
code/hostelswap/synth    synthetic pools for demos and benchmarks
code/hostelswap/api.py   fastapi app
db/migrations/           schema, as numbered migrations (python db/migrate.py)
tests/                   pytest suite
docs/                    mkdocs site, published from master
journals/                weekly journals, one folder per member
```

## Setup

``` shell
python -m venv .venv
.venv/Scripts/activate      # source .venv/bin/activate on linux
pip install -e ".[dev]"
pytest -q
```

## Running the prototype

``` shell
uvicorn hostelswap.api:app --reload
```

Without `DATABASE_URL` the app serves a hardcoded demo cohort. In
production set `APP_ENV=production` (environment or `.env`): the app then
refuses to start without a database instead of serving demo data.

## Database

Put `DATABASE_URL` in `.env` (see `.env.example`), then:

``` shell
python db/migrate.py            # apply pending migrations
python db/migrate.py --status   # see what is applied
```

A schema change is a new file `db/migrations/NNNN_description.sql`;
never edit a migration that has already been applied anywhere.

## Docs

``` shell
make docs
```
