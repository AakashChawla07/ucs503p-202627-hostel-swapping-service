"""Load dummy data: four hostels and 1000 students living in them.

    python db/seed_hostels.py --reset                  1000 students
    python db/seed_hostels.py --reset --students 600   a different cohort size

DESTRUCTIVE: --reset clears every table first (rounds, proposals,
students, rooms, ...), the same way db/seed.py does. It is required so
the script never wipes a database by accident.

Layout (every room is AC with a shared washroom; room numbers are
<floor><NN>, so floor 3 room 7 is "307"):

    A   floors 1-4, rooms 01-57   2AC
    B   floors 1-2, rooms 01-30   2AC (01-15) and 1AC (16-30)
    C   floors 1-2, rooms 01-30   2AC (01-15) and 3AC (16-30)
    D   floors 1-4, rooms 01-57   2AC

That is 1152 beds. Students are spread over a random 1000 of them, so
every hostel has some empty beds for swaps to move into. A fixed random
seed makes a re-run produce the same data.

Everyone, admin included, logs in with the demo password.
"""

import argparse
import pathlib
import random
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))

import psycopg  # noqa: E402

from hostelswap.auth import hash_password  # noqa: E402
from seed import (  # noqa: E402
    ADMIN_EMAIL, ADMIN_NAME, ADMIN_ROLL, DEMO_PASSWORD, EPOCH, TABLES, resolve_dsn,
)

SEED = 20261102
WASHROOM = "sharing"  # "shared washroom"

# code, name, floors, rooms per floor, room type by room number
HOSTELS = (
    ("A", "Hostel A", 4, 57, lambda n: 2),
    ("B", "Hostel B", 2, 30, lambda n: 2 if n <= 15 else 1),
    ("C", "Hostel C", 2, 30, lambda n: 2 if n <= 15 else 3),
    ("D", "Hostel D", 4, 57, lambda n: 2),
)

FIRST = (
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Pranav", "Kabir", "Rohan",
    "Ananya", "Diya", "Aadhya", "Saanvi", "Myra", "Ira", "Kiara", "Anika",
    "Navya", "Sara", "Riya", "Meera", "Tanvi", "Pari", "Ishita", "Kavya",
    "Harsh", "Karan", "Nikhil", "Rahul", "Siddharth", "Varun", "Yash", "Dev",
    "Simran", "Neha", "Pooja", "Sneha", "Tanya", "Mehak", "Jasleen", "Gurleen",
)
LAST = (
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Mehta", "Malhotra", "Kapoor",
    "Arora", "Bansal", "Chawla", "Sethi", "Grover", "Bhatia", "Ahuja", "Khanna",
    "Jain", "Agarwal", "Saini", "Gill", "Sandhu", "Dhillon", "Bedi", "Anand",
    "Nair", "Iyer", "Reddy", "Rao", "Das", "Bose", "Mishra", "Tiwari",
)


def direction(room: int, per_floor: int) -> str:
    """Rooms go round the floor: first quarter faces N, then E, S, W."""
    return "NESW"[min(3, (room - 1) * 4 // per_floor)]


def roll_no(index: int) -> str:
    return f"1024{40001 + index:06d}"


def build_layout():
    """Rows for hostels, rooms and bed slots, with ids made here so the
    inserts need no round trips."""
    hostels, rooms, slots = [], [], []
    for code, name, floors, per_floor, capacity_of in HOSTELS:
        hostel_id = uuid.uuid4()
        hostels.append((hostel_id, code, name))
        for floor in range(1, floors + 1):
            for n in range(1, per_floor + 1):
                room_id, capacity = uuid.uuid4(), capacity_of(n)
                rooms.append((
                    room_id, hostel_id, f"{floor}{n:02d}", floor,
                    direction(n, per_floor), WASHROOM, True, capacity,
                ))
                for b in range(capacity):
                    slots.append((uuid.uuid4(), room_id, chr(ord("a") + b)))
    return hostels, rooms, slots


def build_students(rng: random.Random, count: int, password_hash: str):
    students, seen = [], set()
    for i in range(count):
        # Unique names keep the admin views readable.
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if name not in seen or len(seen) >= len(FIRST) * len(LAST):
                break
        seen.add(name)
        roll = roll_no(i)
        students.append((uuid.uuid4(), roll, name, f"{roll}@thapar.edu", password_hash))
    return students


def seed(dsn: str, count: int) -> None:
    rng = random.Random(SEED)
    hostels, rooms, slots = build_layout()
    if count > len(slots):
        raise SystemExit(f"{count} students but only {len(slots)} beds")

    # PBKDF2 is deliberately slow; one hash shared by every dummy account
    # keeps the run to seconds instead of minutes.
    password_hash = hash_password(DEMO_PASSWORD)
    students = build_students(rng, count, password_hash)
    beds = rng.sample(slots, count)
    allocations = [
        (student[0], bed[0], EPOCH, "seed") for student, bed in zip(students, beds)
    ]

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(f"truncate {', '.join(TABLES)}, roommate_requests restart identity cascade")
        cur.executemany("insert into hostels (id, code, name) values (%s, %s, %s)", hostels)
        cur.executemany(
            """insert into rooms (id, hostel_id, room_no, floor, direction,
                                  washroom_type, ac, capacity)
               values (%s, %s, %s, %s, %s, %s, %s, %s)""",
            rooms,
        )
        cur.executemany("insert into bed_slots (id, room_id, label) values (%s, %s, %s)", slots)
        cur.execute(
            """insert into students (roll_no, name, email, password_hash, role)
               values (%s, %s, %s, %s, 'admin')""",
            (ADMIN_ROLL, ADMIN_NAME, ADMIN_EMAIL, password_hash),
        )
        cur.executemany(
            """insert into students (id, roll_no, name, email, password_hash)
               values (%s, %s, %s, %s, %s)""",
            students,
        )
        cur.executemany(
            """insert into allocations (student_id, slot_id, effective_from, source)
               values (%s, %s, %s, %s)""",
            allocations,
        )
        # The room types students can ask for come from this catalog.
        cur.execute(
            """insert into hostel_room_type_inventory (hostel_id, room_type, quantity)
               select hostel_id, room_type, count(*) from rooms
               group by hostel_id, room_type"""
        )
        conn.commit()

        cur.execute(
            """select h.code, r.room_type, count(distinct r.id), count(b.id), count(c.slot_id)
               from hostels h
               join rooms r on r.hostel_id = h.id
               join bed_slots b on b.room_id = r.id
               left join current_allocations c on c.slot_id = b.id
               group by h.code, r.room_type order by h.code, r.room_type"""
        )
        print(f"  {'hostel':<7}{'type':<7}{'rooms':>6}{'beds':>6}{'filled':>8}")
        for code, room_type, n_rooms, n_beds, filled in cur.fetchall():
            print(f"  {code:<7}{room_type:<7}{n_rooms:>6}{n_beds:>6}{filled:>8}")

    print(f"\n{count} students in {len(beds)} of {len(slots)} beds")
    print(f"login as admin:   {ADMIN_ROLL} / {DEMO_PASSWORD}")
    print(f"login as student: {roll_no(0)} .. {roll_no(count - 1)} / {DEMO_PASSWORD}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Load four dummy hostels and their students.")
    parser.add_argument("--reset", action="store_true",
                        help="required: wipe all existing data first")
    parser.add_argument("--students", type=int, default=1000)
    args = parser.parse_args()

    if not args.reset:
        parser.error("this replaces ALL data in the database; pass --reset to confirm")
    dsn = resolve_dsn()
    if not dsn:
        print("DATABASE_URL is not set. Put it in .env or export it.", file=sys.stderr)
        return 1
    seed(dsn, args.students)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
