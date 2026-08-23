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
db/schema.sql            supabase schema
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

## Docs

``` shell
make docs
```
