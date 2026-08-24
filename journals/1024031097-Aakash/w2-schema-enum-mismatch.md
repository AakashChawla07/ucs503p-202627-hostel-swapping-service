# Week 3 : The database rejected a value our code sends

## Problem

We wrote the Postgres schema before the preference model was finished.
A preference has a type, and we stored it as an enum:

```sql
create type criterion as enum (
    'hostel', 'floor', 'direction', 'washroom', 'room_type', 'roommate'
);
```

Later we added a new kind of preference: a student naming one specific
room they want, with floor and direction as the fallbacks. In Python:

```python
class Criterion(Enum):
    ROOM = "room"        # <- added later
    HOSTEL = "hostel"
    ...
```

The schema was never updated. Every one of our 30 demo students has a
`room` preference, so the seed script would have failed on the very
first insert:

```text
invalid input value for enum criterion: "room"
```

## How we caught it

Before running the seed we compared the two lists directly, rather than
running it and reading the error:

```text
schema enum:  hostel, floor, direction, washroom, room_type, roommate
code sends:   room, floor, direction
```

`room` is in one list and not the other.

## Fix

The enum already existed in the live database, so we could not just
edit `schema.sql` and re-run it. Postgres can add a value to an
existing enum:

```sql
alter type criterion add value if not exists 'room' before 'hostel';
```

This is additive, so nothing already stored is affected. We also fixed
`schema.sql` so a fresh setup gets it right the first time.

## What I learned

An enum in the database is a copy of a list that also exists in the
code, and nothing keeps the two in step. When we add a preference type
we have to change it in both places, or the application will send a
value the database has never heard of. A quick check comparing the two
lists costs seconds and catches it before the insert fails.
