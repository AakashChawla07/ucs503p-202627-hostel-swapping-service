"""Load the demo cohort into Postgres.

    python db/seed.py

Reads DATABASE_URL from the environment (or a .env file next to this
script's parent). Safe to re-run: it clears the tables first.
"""

import os
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))

import psycopg  # noqa: E402

from hostelswap.demo_data import PREFERENCES, ROOMS, STUDENTS  # noqa: E402

HOSTEL_CODE = "A"
HOSTEL_NAME = "Hostel A"
EPOCH = datetime(2026, 1, 1)

# TRUNCATE bypasses row-level triggers, so it can clear the append-only
# allocations table. Ordinary DELETE and UPDATE are still refused, which
# is the point -- history cannot be rewritten through the application.
TABLES = (
    "swap_chain_members", "swap_proposals", "preferences", "preference_sets",
    "allocations", "bed_slots", "rooms", "students", "hostels",
)


def roll_no(index: int) -> str:
    return f"10240300{index + 10:02d}"


def seed(dsn: str) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(f"truncate {', '.join(TABLES)} restart identity cascade")

        cur.execute(
            "insert into hostels (code, name) values (%s, %s) returning id",
            (HOSTEL_CODE, HOSTEL_NAME),
        )
        hostel_id = cur.fetchone()[0]

        room_ids = {}
        for room_id, floor, facing, washroom, capacity in ROOMS:
            cur.execute(
                """insert into rooms
                   (hostel_id, room_no, floor, direction,
                    has_attached_washroom, capacity)
                   values (%s, %s, %s, %s, %s, %s) returning id""",
                (hostel_id, room_id.split("-", 1)[1], floor, facing, washroom, capacity),
            )
            room_ids[room_id] = cur.fetchone()[0]

        slot_ids = {}
        for room_id, _, _, _, capacity in ROOMS:
            for i in range(capacity):
                label = chr(ord("a") + i)
                cur.execute(
                    "insert into bed_slots (room_id, label) values (%s, %s) returning id",
                    (room_ids[room_id], label),
                )
                slot_ids[f"{room_id}-{label}"] = cur.fetchone()[0]

        student_ids = {}
        for i, (sid, name, _) in enumerate(STUDENTS):
            roll = roll_no(i)
            cur.execute(
                "insert into students (roll_no, name, email) values (%s, %s, %s) returning id",
                (roll, name, f"{roll}@thapar.edu"),
            )
            student_ids[sid] = cur.fetchone()[0]

        for sid, _, slot in STUDENTS:
            cur.execute(
                """insert into allocations (student_id, slot_id, effective_from, source)
                   values (%s, %s, %s, 'seed')""",
                (student_ids[sid], slot_ids[slot], EPOCH),
            )

        for sid, _, _ in STUDENTS:
            cur.execute(
                "insert into preference_sets (student_id, active) values (%s, true) returning id",
                (student_ids[sid],),
            )
            set_id = cur.fetchone()[0]
            for criterion, value, weight in PREFERENCES[sid]:
                cur.execute(
                    """insert into preferences
                       (preference_set_id, criterion, value, weight, hard)
                       values (%s, %s, %s, %s, false)""",
                    (set_id, criterion, str(value), weight),
                )

        conn.commit()

    print(f"seeded {len(STUDENTS)} students, {len(ROOMS)} rooms in hostel {HOSTEL_CODE}")


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        env = pathlib.Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not dsn:
        print("DATABASE_URL is not set. Put it in .env or export it.", file=sys.stderr)
        return 1
    seed(dsn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
