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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import psycopg

log = logging.getLogger("hostelswap.db")

from .domain.models import Allocation, BedSlot, Direction, Room, Student, WashroomType
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
        case Criterion.FLOOR:
            return int(raw)
        case Criterion.DIRECTION:
            return Direction(raw)
        case Criterion.WASHROOM | Criterion.ROOM_TYPE:
            # Stored and compared as text: "attached"/"common"/"sharing"
            # for washroom, "2SAC"-style codes for room type.
            return raw
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
                   r.washroom_type, r.capacity, r.ac
            from rooms r join hostels h on h.id = r.hostel_id
            where h.code = %s
            """,
            (hostel,),
        )
        rooms, room_key = {}, {}
        for rid, code, room_no, floor, facing, washroom, capacity, ac in cur.fetchall():
            key = f"{code}-{room_no}"
            room_key[rid] = key
            rooms[key] = Room(
                key, code, floor, Direction(facing), WashroomType(washroom), capacity, ac
            )

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


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

def fetch_student_credentials(connection_string: str, identifier: str) -> dict | None:
    """Look a student up by roll number or email, for login."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, roll_no, name, role, password_hash
            from students
            where roll_no = %s or email = %s
            """,
            (identifier, identifier),
        )
        row = cur.fetchone()
    if row is None:
        return None
    sid, roll_no, name, role, password_hash = row
    return {
        "id": str(sid), "roll_no": roll_no, "name": name,
        "role": role, "password_hash": password_hash,
    }


def create_session(connection_string: str, token: str, student_id: str, expires_at: datetime) -> None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "insert into sessions (token, student_id, expires_at) values (%s, %s, %s)",
            (token, student_id, expires_at),
        )
        conn.commit()


def delete_session(connection_string: str, token: str) -> None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute("delete from sessions where token = %s", (token,))
        conn.commit()


def fetch_session_user(connection_string: str, token: str) -> dict | None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select s.id, s.roll_no, s.name, s.role
            from sessions se join students s on s.id = se.student_id
            where se.token = %s and se.expires_at > now()
            """,
            (token,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    sid, roll_no, name, role = row
    return {"id": str(sid), "roll_no": roll_no, "name": name, "role": role}


# --------------------------------------------------------------------------
# Student's own room / hostel
# --------------------------------------------------------------------------

def fetch_student_room(connection_string: str, student_id: str) -> dict | None:
    """The room a student currently occupies, plus their hostel's id."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select h.id, h.code, h.name, r.room_no, r.floor, r.direction,
                   r.washroom_type, r.room_type, b.label
            from current_allocations c
            join bed_slots b on b.id = c.slot_id
            join rooms r on r.id = b.room_id
            join hostels h on h.id = r.hostel_id
            where c.student_id = %s
            """,
            (student_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    hostel_id, code, name, room_no, floor, direction, washroom, room_type, label = row
    return {
        "hostelId": str(hostel_id), "hostel": code, "hostelName": name,
        "room": f"{code}-{room_no}", "floor": floor, "direction": direction,
        "washroomType": washroom, "roomType": room_type, "bed": label,
    }


# --------------------------------------------------------------------------
# Hostels
# --------------------------------------------------------------------------

def fetch_hostels(connection_string: str) -> list[dict]:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute("select id, code, name from hostels order by code")
        return [{"id": str(hid), "code": code, "name": name} for hid, code, name in cur.fetchall()]


# --------------------------------------------------------------------------
# Room-type catalog
# --------------------------------------------------------------------------

def fetch_room_type_catalog(connection_string: str, hostel_id: str) -> list[dict]:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select room_type, quantity from hostel_room_type_inventory
            where hostel_id = %s order by room_type
            """,
            (hostel_id,),
        )
        return [{"roomType": rt, "quantity": qty} for rt, qty in cur.fetchall()]


def upsert_room_type_quantity(
    connection_string: str, hostel_id: str, room_type: str, quantity: int
) -> None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into hostel_room_type_inventory (hostel_id, room_type, quantity)
            values (%s, %s, %s)
            on conflict (hostel_id, room_type) do update set quantity = excluded.quantity
            """,
            (hostel_id, room_type, quantity),
        )
        conn.commit()


# --------------------------------------------------------------------------
# Rounds
# --------------------------------------------------------------------------

def create_round(connection_string: str, hostel_id: str) -> str:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "insert into swap_rounds (hostel_id, status) values (%s, 'draft') returning id",
            (hostel_id,),
        )
        round_id = cur.fetchone()[0]
        conn.commit()
    return str(round_id)


def set_round_status(connection_string: str, round_id: str, status: str, **timestamps) -> None:
    columns = ", ".join(f"{col} = %s" for col in timestamps)
    sep = ", " if columns else ""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            f"update swap_rounds set status = %s{sep}{columns} where id = %s",
            (status, *timestamps.values(), round_id),
        )
        conn.commit()


def fetch_round(connection_string: str, round_id: str) -> dict | None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "select id, hostel_id, status from swap_rounds where id = %s", (round_id,)
        )
        row = cur.fetchone()
    if row is None:
        return None
    rid, hostel_id, status = row
    return {"id": str(rid), "hostelId": str(hostel_id), "status": status}


def fetch_active_round_for_hostel(connection_string: str, hostel_id: str) -> dict | None:
    """The most recent round for a hostel, cancelled ones aside.

    Deliberately includes 'completed' rounds -- students need this to keep
    resolving to the round whose results and offers they should be looking
    at, not just the ones still accepting registration.
    """
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, status from swap_rounds
            where hostel_id = %s and status <> 'cancelled'
            order by created_at desc limit 1
            """,
            (hostel_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    rid, status = row
    return {"id": str(rid), "hostelId": hostel_id, "status": status}


# --------------------------------------------------------------------------
# Enrollment
# --------------------------------------------------------------------------

def set_enrollment(connection_string: str, round_id: str, student_id: str, enrolled: bool) -> None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into round_enrollments (round_id, student_id, enrolled)
            values (%s, %s, %s)
            on conflict (round_id, student_id)
            do update set enrolled = excluded.enrolled, updated_at = now()
            """,
            (round_id, student_id, enrolled),
        )
        conn.commit()


def fetch_enrollment(connection_string: str, round_id: str, student_id: str) -> bool:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "select enrolled from round_enrollments where round_id = %s and student_id = %s",
            (round_id, student_id),
        )
        row = cur.fetchone()
    return bool(row and row[0])


# --------------------------------------------------------------------------
# Priorities (round-scoped preferences)
# --------------------------------------------------------------------------

def replace_preferences(
    connection_string: str, student_id: str, round_id: str, preferences: list[dict]
) -> None:
    """Deactivate this student's previous set for the round and insert a new one.

    `preferences` is a list of {criterion, value, weight, hard}; criteria the
    student left as "doesn't matter" are simply absent from the list.
    """
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            update preference_sets set active = false
            where student_id = %s and round_id = %s and active
            """,
            (student_id, round_id),
        )
        cur.execute(
            "insert into preference_sets (student_id, round_id, active) values (%s, %s, true) returning id",
            (student_id, round_id),
        )
        set_id = cur.fetchone()[0]
        for p in preferences:
            cur.execute(
                """
                insert into preferences (preference_set_id, criterion, value, weight, hard)
                values (%s, %s, %s, %s, %s)
                """,
                (set_id, p["criterion"], str(p["value"]), p.get("weight", 1), p.get("hard", False)),
            )
        conn.commit()


def fetch_preferences(connection_string: str, student_id: str, round_id: str) -> list[dict]:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select p.criterion, p.value, p.weight, p.hard
            from preferences p
            join preference_sets ps on ps.id = p.preference_set_id
            where ps.student_id = %s and ps.round_id = %s and ps.active
            """,
            (student_id, round_id),
        )
        return [
            {"criterion": c, "value": v, "weight": float(w), "hard": h}
            for c, v, w, h in cur.fetchall()
        ]


# --------------------------------------------------------------------------
# Building a SwapPool scoped to one round's enrolled students
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RoundPool:
    """A SwapPool plus the real database uuids behind its human-readable
    student/slot keys, needed when writing match results back to Postgres."""
    pool: SwapPool
    hostel_id: str
    student_uuid: Mapping[str, str]
    slot_uuid: Mapping[str, str]


def load_round_pool(connection_string: str, round_id: str) -> RoundPool:
    started = time.perf_counter()
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute("select hostel_id from swap_rounds where id = %s", (round_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"no such round: {round_id}")
        hostel_id = str(row[0])

        cur.execute(
            """
            select r.id, h.code, r.room_no, r.floor, r.direction,
                   r.washroom_type, r.capacity, r.ac
            from rooms r join hostels h on h.id = r.hostel_id
            where r.hostel_id = %s
            """,
            (hostel_id,),
        )
        rooms, room_key = {}, {}
        for rid, code, room_no, floor, facing, washroom, capacity, ac in cur.fetchall():
            key = f"{code}-{room_no}"
            room_key[str(rid)] = key
            rooms[key] = Room(
                key, code, floor, Direction(facing), WashroomType(washroom), capacity, ac
            )

        cur.execute(
            """
            select b.id, b.room_id, b.label
            from bed_slots b join rooms r on r.id = b.room_id
            where r.hostel_id = %s
            """,
            (hostel_id,),
        )
        slots, slot_key, slot_uuid = {}, {}, {}
        for sid, rid, label in cur.fetchall():
            key = f"{room_key[str(rid)]}-{label}"
            slot_key[str(sid)] = key
            slot_uuid[key] = str(sid)
            slots[key] = BedSlot(key, room_key[str(rid)])

        cur.execute(
            """
            select s.id, s.roll_no, s.name, c.slot_id, c.effective_from
            from round_enrollments e
            join students s on s.id = e.student_id
            join current_allocations c on c.student_id = s.id
            where e.round_id = %s and e.enrolled = true
            order by s.roll_no
            """,
            (round_id,),
        )
        students, allocations, held, student_uuid = [], [], [], {}
        for uid, roll_no, name, slot_id, effective_from in cur.fetchall():
            students.append(Student(roll_no, name))
            allocations.append(Allocation(roll_no, slot_key[str(slot_id)], effective_from))
            held.append(slot_key[str(slot_id)])
            student_uuid[roll_no] = str(uid)

        cur.execute(
            """
            select s.roll_no, p.criterion, p.value, p.weight, p.hard
            from preferences p
            join preference_sets ps on ps.id = p.preference_set_id
            join students s on s.id = ps.student_id
            where ps.active and ps.round_id = %s
            """,
            (round_id,),
        )
        wishes: dict[str, list[Preference]] = {s.id: [] for s in students}
        for roll_no, criterion, raw, weight, hard in cur.fetchall():
            if roll_no in wishes:
                c = Criterion(criterion)
                wishes[roll_no].append(Preference(c, _value(c, raw), float(weight), hard))

    log.info(
        "loaded round %s: %d enrolled students, %d rooms in %d ms",
        round_id, len(students), len(rooms), (time.perf_counter() - started) * 1000,
    )
    pool = SwapPool(
        students=tuple(students),
        preferences={sid: PreferenceSet(sid, tuple(p)) for sid, p in wishes.items()},
        rooms=rooms,
        slots=tuple(slots[k] for k in held),
        allocations=tuple(allocations),
    )
    return RoundPool(pool=pool, hostel_id=hostel_id, student_uuid=student_uuid, slot_uuid=slot_uuid)


# --------------------------------------------------------------------------
# Persisted chain options (the engine's output for a round)
# --------------------------------------------------------------------------

def clear_chain_options(connection_string: str, round_id: str) -> None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute("delete from round_chain_options where round_id = %s", (round_id,))
        conn.commit()


def insert_chain_options(connection_string: str, round_id: str, rows: list[dict]) -> None:
    """`rows`: {optionKind, chainNo, studentId, fromSlotId, toSlotId, matchValue} (uuids)."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into round_chain_options
                (round_id, option_kind, chain_no, student_id, from_slot_id, to_slot_id, match_value)
            values (%(round_id)s, %(kind)s, %(chain_no)s, %(student_id)s, %(from_slot_id)s,
                    %(to_slot_id)s, %(match_value)s)
            """,
            [{"round_id": round_id, **r} for r in rows],
        )
        conn.commit()


def fetch_chain_options(connection_string: str, round_id: str) -> list[dict]:
    """All persisted chain options for a round, grouped by (option_kind, chain_no)."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select o.option_kind, o.chain_no, s.id, s.roll_no, s.name,
                   fh.code, fr.room_no, tr.room_no, o.match_value,
                   o.from_slot_id, o.to_slot_id
            from round_chain_options o
            join students s on s.id = o.student_id
            join bed_slots fb on fb.id = o.from_slot_id
            join rooms fr on fr.id = fb.room_id
            join hostels fh on fh.id = fr.hostel_id
            join bed_slots tb on tb.id = o.to_slot_id
            join rooms tr on tr.id = tb.room_id
            where o.round_id = %s
            order by o.option_kind, o.chain_no, s.roll_no
            """,
            (round_id,),
        )
        rows = cur.fetchall()

    chains: dict[tuple[str, int], list[dict]] = {}
    for kind, chain_no, student_id, roll_no, name, code, from_no, to_no, match_value, from_slot, to_slot in rows:
        chains.setdefault((kind, chain_no), []).append({
            "studentId": str(student_id), "rollNo": roll_no, "name": name,
            "from": f"{code}-{from_no}", "to": f"{code}-{to_no}",
            "match": round(float(match_value) * 100),
            "fromSlotId": str(from_slot), "toSlotId": str(to_slot),
        })
    return [
        {"optionKind": kind, "chainNo": chain_no, "members": members}
        for (kind, chain_no), members in chains.items()
    ]


# --------------------------------------------------------------------------
# Swap proposals (offer / accept / reject)
# --------------------------------------------------------------------------

class AlreadyReserved(Exception):
    """A member of the chain is already live in another proposal."""


def insert_proposal(
    connection_string: str,
    round_id: str,
    kind: str,
    mean_match: float,
    longest_chain: int,
    expires_at: datetime,
    members: list[dict],
    offering_roll_no: str,
) -> str:
    """`members`: {studentId, rollNo, fromSlotId, toSlotId, matchValue} (uuids)."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                insert into swap_proposals (round_id, kind, status, mean_match, longest_chain, expires_at)
                values (%s, %s, 'proposed', %s, %s, %s) returning id
                """,
                (round_id, kind, mean_match, longest_chain, expires_at),
            )
            proposal_id = cur.fetchone()[0]
            for position, member in enumerate(members):
                approval = "approved" if member["rollNo"] == offering_roll_no else "pending"
                cur.execute(
                    """
                    insert into swap_chain_members
                        (proposal_id, position, student_id, from_slot_id, to_slot_id, match_value, approval, responded_at)
                    values (%s, %s, %s, %s, %s, %s, %s, case when %s = 'approved' then now() else null end)
                    """,
                    (proposal_id, position, member["studentId"], member["fromSlotId"],
                     member["toSlotId"], member["matchValue"], approval, approval),
                )
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            raise AlreadyReserved(
                "one or more students in this chain are already part of another live proposal"
            ) from None
        conn.commit()
    return str(proposal_id)


def fetch_proposal(connection_string: str, proposal_id: str) -> dict | None:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "select id, round_id, status, expires_at, settled_at from swap_proposals where id = %s",
            (proposal_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        pid, round_id, status, expires_at, settled_at = row

        cur.execute(
            """
            select m.position, s.id, s.roll_no, s.name, m.from_slot_id, m.to_slot_id,
                   m.match_value, m.approval, m.responded_at
            from swap_chain_members m join students s on s.id = m.student_id
            where m.proposal_id = %s order by m.position
            """,
            (proposal_id,),
        )
        members = [
            {
                "position": pos, "studentId": str(sid), "rollNo": roll_no, "name": name,
                "fromSlotId": str(fs), "toSlotId": str(ts), "matchValue": float(mv),
                "approval": approval, "respondedAt": responded_at,
            }
            for pos, sid, roll_no, name, fs, ts, mv, approval, responded_at in cur.fetchall()
        ]
    return {
        "id": str(pid), "roundId": str(round_id) if round_id else None,
        "status": status, "expiresAt": expires_at, "settledAt": settled_at, "members": members,
    }


def fetch_student_proposals(connection_string: str, student_id: str) -> list[dict]:
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select distinct m.proposal_id from swap_chain_members m
            where m.student_id = %s and m.approval <> 'rejected'
            """,
            (student_id,),
        )
        proposal_ids = [str(r[0]) for r in cur.fetchall()]
    return [p for p in (fetch_proposal(connection_string, pid) for pid in proposal_ids) if p]


def update_proposal(
    connection_string: str,
    proposal_id: str,
    status: str,
    member_approvals: dict[str, str],
    settled: bool,
) -> None:
    """`member_approvals`: {studentId: approval} for every member, reflecting
    the outcome of one response (a single rejection voids the whole chain,
    so every member's row is updated to keep the "one live proposal" index
    consistent)."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "update swap_proposals set status = %s, settled_at = case when %s then now() else settled_at end where id = %s",
            (status, settled, proposal_id),
        )
        for student_id, approval in member_approvals.items():
            cur.execute(
                """
                update swap_chain_members
                set approval = %s, responded_at = coalesce(responded_at, now())
                where proposal_id = %s and student_id = %s
                """,
                (approval, proposal_id, student_id),
            )
        conn.commit()


def insert_allocations(connection_string: str, allocations: list[tuple[str, str, datetime]]) -> None:
    """`allocations`: (student_id, slot_id, effective_from) uuids."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into allocations (student_id, slot_id, effective_from, source)
            values (%s, %s, %s, 'swap')
            """,
            allocations,
        )
        conn.commit()


def fetch_round_proposals(connection_string: str, round_id: str) -> list[dict]:
    """Every proposal for a round with its members' approval status, for admins."""
    with psycopg.connect(connection_string) as conn, conn.cursor() as cur:
        cur.execute(
            "select id from swap_proposals where round_id = %s order by created_at", (round_id,)
        )
        proposal_ids = [str(r[0]) for r in cur.fetchall()]
    return [p for p in (fetch_proposal(connection_string, pid) for pid in proposal_ids) if p]
