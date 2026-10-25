"""Add a fresh cohort to whichever swap round is currently open.

    python db/seed_round.py [round_id]

Additive and idempotent-by-roll-number: it never truncates. It creates
rooms and beds on new floors, moves a batch of new students into them,
enrols those students in the open round and gives each one a set of
round-scoped priorities, so the round has a cohort large enough to
produce real chains when an admin locks and runs it.

Re-running skips students whose roll numbers already exist, so it can
top up a round without duplicating anyone.
"""

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))

import psycopg  # noqa: E402

from hostelswap.auth import hash_password  # noqa: E402
from seed import DEMO_PASSWORD, EPOCH  # noqa: E402
from seed import resolve_dsn  # noqa: E402

COHORT = 28
ROLL_START = 40  # existing seed occupies 10..39
SEED = 20260907  # fixed, so a re-run of a fresh database reproduces this cohort

NAMES = (
    "Ritvik Anand", "Yash Bhatia", "Dhruv Sethi", "Manan Grover",
    "Aryan Chadha", "Krish Saluja", "Tanmay Bakshi", "Naman Puri",
    "Shaurya Ahuja", "Veer Nagpal", "Rudra Sachdeva", "Advait Chhabra",
    "Parth Wadhwa", "Ansh Bhardwaj", "Aditya Rastogi", "Kunal Trehan",
    "Ayush Sarin", "Raghav Batra", "Siddharth Oberoi", "Nakul Bedi",
    "Jai Talwar", "Ekansh Sabharwal", "Om Chaudhary", "Rishab Kalra",
    "Aarush Gulati", "Madhav Suri", "Neel Bhasin", "Vihaan Ratra",
)

# New floors, so these rooms cannot collide with the fixed demo table.
# room_no, floor, direction, washroom, ac, capacity
NEW_ROOMS = (
    ("701", 7, "N", "attached", False, 1),
    ("702", 7, "N", "common",   False, 1),
    ("705", 7, "S", "attached", True,  1),
    ("708", 7, "S", "common",   False, 1),
    ("712", 7, "E", "attached", True,  2),
    ("715", 7, "E", "common",   False, 2),
    ("718", 7, "W", "attached", False, 2),
    ("721", 7, "W", "common",   False, 3),
    ("724", 7, "N", "attached", True,  3),
    ("801", 8, "N", "attached", True,  1),
    ("804", 8, "N", "common",   False, 1),
    ("807", 8, "S", "attached", False, 1),
    ("810", 8, "S", "attached", True,  2),
    ("813", 8, "E", "common",   False, 2),
    ("816", 8, "E", "attached", True,  2),
    ("819", 8, "W", "attached", False, 3),
    ("822", 8, "W", "common",   False, 3),
)


def roll_no(index: int) -> str:
    return f"10240300{index:02d}"


def open_round(cur, wanted: str | None) -> tuple[str, str]:
    """The round to fill: the one asked for, else the single open one."""
    if wanted:
        cur.execute("select id, hostel_id, status from swap_rounds where id = %s", (wanted,))
    else:
        cur.execute(
            """select id, hostel_id, status from swap_rounds
               where status = 'open' order by created_at desc limit 1"""
        )
    row = cur.fetchone()
    if row is None:
        raise SystemExit("no open round found -- open one from the admin page first")
    round_id, hostel_id, status = row
    if status != "open":
        raise SystemExit(f"round {round_id} is '{status}', not open -- refusing to enrol into it")
    return str(round_id), str(hostel_id)


def make_rooms(cur, hostel_id: str) -> list[tuple[str, str, int, str, str]]:
    """Create the new rooms and their beds; return the free bed slots."""
    free = []
    for room_no, floor, direction, washroom, ac, capacity in NEW_ROOMS:
        cur.execute(
            """insert into rooms
               (hostel_id, room_no, floor, direction, washroom_type, ac, capacity)
               values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (hostel_id, room_no) do nothing
               returning id""",
            (hostel_id, room_no, floor, direction, washroom, ac, capacity),
        )
        row = cur.fetchone()
        if row is None:  # room already there from an earlier run
            cur.execute(
                "select id from rooms where hostel_id = %s and room_no = %s",
                (hostel_id, room_no),
            )
            row = cur.fetchone()
        room_id = row[0]
        for i in range(capacity):
            label = chr(ord("a") + i)
            cur.execute(
                """insert into bed_slots (room_id, label) values (%s, %s)
                   on conflict (room_id, label) do nothing returning id""",
                (room_id, label),
            )
            slot = cur.fetchone()
            if slot is None:
                cur.execute(
                    "select id from bed_slots where room_id = %s and label = %s",
                    (room_id, label),
                )
                slot = cur.fetchone()
            # Skip beds someone already lives in, so a re-run cannot
            # double-allocate a slot.
            cur.execute(
                "select 1 from current_allocations where slot_id = %s", (slot[0],)
            )
            if cur.fetchone() is None:
                free.append((str(slot[0]), room_no, floor, direction, washroom))
    return free


def priorities(rng, room_no: str, floor: int, direction: str, washroom: str, rooms) -> list:
    """A wish list that is neither what the student already has nor
    impossible: a named room elsewhere, plus softer floor/direction and
    one comfort criterion to break ties."""
    target = rng.choice([r for r in rooms if r[0] != room_no])
    wishes = [
        ("room", f"A-{target[0]}", 3.0),
        ("floor", str(target[1]), 2.0),
        ("direction", target[2], 1.0),
    ]
    if rng.random() < 0.5:
        wishes.append(("washroom", "attached" if washroom == "common" else "common", 1.0))
    else:
        capacity = target[5]
        wishes.append(("room_type", f"{capacity}S{'A' if target[4] else 'NA'}C", 1.0))
    return wishes


def populate(dsn: str, wanted: str | None) -> None:
    rng = random.Random(SEED)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        round_id, hostel_id = open_round(cur, wanted)
        free = make_rooms(cur, hostel_id)

        added, enrolled = 0, 0
        for i in range(COHORT):
            roll = roll_no(ROLL_START + i)
            cur.execute("select id from students where roll_no = %s", (roll,))
            row = cur.fetchone()
            if row is None:
                if not free:
                    print(f"out of free beds after {added} students", file=sys.stderr)
                    break
                cur.execute(
                    """insert into students (roll_no, name, email, password_hash)
                       values (%s, %s, %s, %s) returning id""",
                    (roll, NAMES[i], f"{roll}@thapar.edu", hash_password(DEMO_PASSWORD)),
                )
                student_id = cur.fetchone()[0]
                slot_id, room_no, floor, direction, washroom = free.pop(0)
                cur.execute(
                    """insert into allocations (student_id, slot_id, effective_from, source)
                       values (%s, %s, %s, 'seed_round')""",
                    (student_id, slot_id, EPOCH),
                )
                added += 1
            else:
                student_id = row[0]
                cur.execute(
                    """select r.room_no, r.floor, r.direction, r.washroom_type
                       from current_allocations c
                       join bed_slots b on b.id = c.slot_id
                       join rooms r on r.id = b.room_id
                       where c.student_id = %s""",
                    (student_id,),
                )
                held = cur.fetchone()
                if held is None:
                    continue  # nowhere to swap from; leave them out of the round
                room_no, floor, direction, washroom = held

            cur.execute(
                """insert into round_enrollments (round_id, student_id, enrolled)
                   values (%s, %s, true)
                   on conflict (round_id, student_id)
                   do update set enrolled = true, updated_at = now()""",
                (round_id, student_id),
            )
            enrolled += 1

            # One active priority set per student per round.
            cur.execute(
                """update preference_sets set active = false
                   where student_id = %s and round_id = %s""",
                (student_id, round_id),
            )
            cur.execute(
                """insert into preference_sets (student_id, round_id, active)
                   values (%s, %s, true) returning id""",
                (student_id, round_id),
            )
            set_id = cur.fetchone()[0]
            for criterion, value, weight in priorities(
                rng, room_no, floor, direction, washroom, NEW_ROOMS
            ):
                cur.execute(
                    """insert into preferences
                       (preference_set_id, criterion, value, weight, hard)
                       values (%s, %s, %s, %s, false)""",
                    (set_id, criterion, value, weight),
                )

        # The room-type choices the student page offers come from this
        # catalog, so keep it in step with the rooms that now exist.
        cur.execute(
            """insert into hostel_room_type_inventory (hostel_id, room_type, quantity)
               select hostel_id, room_type, count(*) from rooms
               where hostel_id = %s group by hostel_id, room_type
               on conflict (hostel_id, room_type)
               do update set quantity = excluded.quantity""",
            (hostel_id,),
        )
        conn.commit()

    print(f"round {round_id}: {added} new students created, {enrolled} enrolled with priorities")
    print(f"login as any of them: {roll_no(ROLL_START)} / {DEMO_PASSWORD}")


def main() -> int:
    dsn = resolve_dsn()
    if not dsn:
        print("DATABASE_URL is not set. Put it in .env or export it.", file=sys.stderr)
        return 1
    populate(dsn, sys.argv[1] if len(sys.argv) > 1 else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
