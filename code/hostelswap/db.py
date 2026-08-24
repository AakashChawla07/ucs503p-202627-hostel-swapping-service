"""Load a swap pool from Postgres.

The domain layer knows nothing about databases, so this module is the
only place that speaks SQL. It reads rows and hands back the same
SwapPool the engine already works with, which is why swapping the
hardcoded table for a real database changes nothing downstream.
"""

import logging
import os
import pathlib
import re
import time

import psycopg

log = logging.getLogger("hostelswap.db")

from .domain.models import Allocation, BedSlot, Direction, Room, Student
from .domain.pool import SwapPool
from .domain.preferences import Criterion, Preference, PreferenceSet


ENV_FILE = pathlib.Path(__file__).resolve().parents[2] / ".env"


def dsn() -> str | None:
    """Connection string, or None when no database is configured.

    Checks the environment first, then a .env file at the repo root, so
    running `uvicorn` needs no extra setup.
    """
    from_env = os.environ.get("DATABASE_URL")
    if from_env:
        return from_env
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    return None


def _value(criterion: Criterion, raw: str):
    """Preference values are stored as text; put them back in their type."""
    match criterion:
        case Criterion.FLOOR | Criterion.ROOM_TYPE:
            return int(raw)
        case Criterion.DIRECTION:
            return Direction(raw)
        case Criterion.WASHROOM:
            return raw.lower() in ("true", "t", "1")
        case _:
            return raw


def _host(connection_string: str) -> str:
    match = re.search(r"@([^:/]+)", connection_string)
    return match.group(1) if match else "?"


def load_pool(connection_string: str, hostel: str = "A") -> SwapPool:
    """Build a pool from the students currently living in `hostel`."""
    started = time.perf_counter()
    log.info("connecting to postgres at %s", _host(connection_string))
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select r.id, h.code, r.room_no, r.floor, r.direction,
                   r.has_attached_washroom, r.capacity
            from rooms r join hostels h on h.id = r.hostel_id
            where h.code = %s
            """,
            (hostel,),
        )
        rooms, room_key = {}, {}
        for rid, code, room_no, floor, facing, washroom, capacity in cur.fetchall():
            key = f"{code}-{room_no}"
            room_key[rid] = key
            rooms[key] = Room(key, code, floor, Direction(facing), washroom, capacity)

        cur.execute(
            """
            select b.id, b.room_id, b.label
            from bed_slots b join rooms r on r.id = b.room_id
                             join hostels h on h.id = r.hostel_id
            where h.code = %s
            """,
            (hostel,),
        )
        slots, slot_key = {}, {}
        for sid, rid, label in cur.fetchall():
            key = f"{room_key[rid]}-{label}"
            slot_key[sid] = key
            slots[key] = BedSlot(key, room_key[rid])

        # Current occupancy comes from the append-only history via the view.
        cur.execute(
            """
            select s.roll_no, s.name, c.slot_id, c.effective_from
            from current_allocations c
            join students s on s.id = c.student_id
            join bed_slots b on b.id = c.slot_id
            join rooms r on r.id = b.room_id
            join hostels h on h.id = r.hostel_id
            where h.code = %s
            order by s.roll_no
            """,
            (hostel,),
        )
        students, allocations, held = [], [], []
        for roll_no, name, slot_id, effective_from in cur.fetchall():
            students.append(Student(roll_no, name))
            allocations.append(Allocation(roll_no, slot_key[slot_id], effective_from))
            held.append(slot_key[slot_id])

        cur.execute(
            """
            select s.roll_no, p.criterion, p.value, p.weight, p.hard
            from preferences p
            join preference_sets ps on ps.id = p.preference_set_id
            join students s on s.id = ps.student_id
            where ps.active
            """
        )
        wishes: dict[str, list[Preference]] = {s.id: [] for s in students}
        for roll_no, criterion, raw, weight, hard in cur.fetchall():
            if roll_no in wishes:
                c = Criterion(criterion)
                wishes[roll_no].append(Preference(c, _value(c, raw), float(weight), hard))

    log.info(
        "loaded %d students, %d rooms, %d preferences from postgres in %d ms",
        len(students), len(rooms), sum(len(v) for v in wishes.values()),
        (time.perf_counter() - started) * 1000,
    )
    return SwapPool(
        students=tuple(students),
        preferences={sid: PreferenceSet(sid, tuple(p)) for sid, p in wishes.items()},
        rooms=rooms,
        # A pool is closed: only the slots these students occupy.
        slots=tuple(slots[k] for k in held),
        allocations=tuple(allocations),
    )


def describe(connection_string: str) -> list[dict]:
    """Read the live table structure straight out of Postgres.

    Used to show the real schema rather than a diagram of one.
    """
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select table_name, column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = 'public'
            order by table_name, ordinal_position
            """
        )
        tables: dict[str, list[dict]] = {}
        for table, column, data_type, nullable in cur.fetchall():
            tables.setdefault(table, []).append(
                {"name": column, "type": data_type, "nullable": nullable == "YES"}
            )

        rows = {}
        for table in tables:
            cur.execute(f'select count(*) from "{table}"')  # noqa: S608 - names from catalog
            rows[table] = cur.fetchone()[0]

    return [
        {"table": name, "rows": rows[name], "columns": cols}
        for name, cols in sorted(tables.items())
    ]
