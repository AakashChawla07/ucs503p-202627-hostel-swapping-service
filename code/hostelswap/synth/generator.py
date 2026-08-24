"""Synthetic swap pools for demos, tests and benchmarks."""

import random
from datetime import datetime

from ..domain.models import Allocation, BedSlot, Direction, Room, Student
from ..domain.pool import SwapPool
from ..domain.preferences import Criterion, Preference, PreferenceSet

# Hostels are named by letter. TODO: fill in the remaining four.
HOSTELS = ("A", "B", "C", "D", "G", "H", "K", "P")
FLOORS = (1, 2, 3, 4, 5, 6, 7, 8)
ROOMS_PER_FLOOR = 58
CAPACITIES = (1, 2, 3)
EPOCH = datetime(2026, 1, 1)

ROOM_CRITERIA = (
    Criterion.HOSTEL,
    Criterion.FLOOR,
    Criterion.DIRECTION,
    Criterion.WASHROOM,
    Criterion.ROOM_TYPE,
)


def _build_rooms(
    rng: random.Random, needed_slots: int, hostels: tuple[str, ...]
) -> tuple[list[Room], list[BedSlot]]:
    """Sample distinct rooms, numbered the way the hostels actually are.

    Room numbers are <floor><nn>, so the eighth floor of hostel A runs
    A-801 to A-858.
    """
    rooms: list[Room] = []
    slots: list[BedSlot] = []
    seen: set[str] = set()

    while len(slots) < needed_slots:
        hostel = rng.choice(hostels)
        floor = rng.choice(FLOORS)
        room_id = f"{hostel}-{floor}{rng.randint(1, ROOMS_PER_FLOOR):02d}"
        if room_id in seen:
            continue
        seen.add(room_id)

        room = Room(
            id=room_id,
            hostel=hostel,
            floor=floor,
            direction=rng.choice(tuple(Direction)),
            has_attached_washroom=rng.random() < 0.5,
            capacity=rng.choice(CAPACITIES),
        )
        rooms.append(room)
        slots.extend(
            BedSlot(f"{room.id}-{chr(ord('a') + i)}", room.id)
            for i in range(room.capacity)
        )

    # Trim to a closed pool: empty beds take no part in a swap.
    return rooms, slots[:needed_slots]


def _build_preferences(
    rng: random.Random,
    student_id: str,
    peer_ids: list[str],
    roommate_probability: float,
    hard_probability: float,
    hostels: tuple[str, ...],
) -> PreferenceSet:
    criteria = rng.sample(ROOM_CRITERIA, rng.randint(2, 4))
    preferences = []
    for criterion in criteria:
        match criterion:
            case Criterion.HOSTEL:
                value = rng.choice(hostels)
            case Criterion.FLOOR:
                value = rng.choice(FLOORS)
            case Criterion.DIRECTION:
                value = rng.choice(tuple(Direction))
            case Criterion.WASHROOM:
                value = rng.random() < 0.7
            case _:
                value = rng.choice(CAPACITIES)
        preferences.append(
            Preference(
                criterion=criterion,
                value=value,
                weight=float(rng.randint(1, 5)),
                hard=rng.random() < hard_probability,
            )
        )

    if rng.random() < roommate_probability:
        others = [peer for peer in peer_ids if peer != student_id]
        if others:
            preferences.append(
                Preference(
                    criterion=Criterion.ROOMMATE,
                    value=rng.choice(others),
                    weight=float(rng.randint(1, 5)),
                    hard=False,
                )
            )

    return PreferenceSet(student_id, tuple(preferences))


def generate_pool(
    students: int = 30,
    seed: int = 0,
    roommate_probability: float = 0.3,
    hard_probability: float = 0.0,
    hostels: tuple[str, ...] = HOSTELS,
) -> SwapPool:
    """Build a pool of `students` participants.

    Seeded, so the same seed gives the same pool. Hard preferences are
    off by default -- random ones tend to make the pool unsolvable.
    """
    rng = random.Random(seed)

    student_ids = [f"s{i:03d}" for i in range(students)]
    rooms, slots = _build_rooms(rng, students, hostels)

    held = slots[:]
    rng.shuffle(held)

    return SwapPool(
        students=tuple(Student(sid, f"Student {sid[1:]}") for sid in student_ids),
        preferences={
            sid: _build_preferences(
                rng, sid, student_ids, roommate_probability, hard_probability, hostels
            )
            for sid in student_ids
        },
        rooms={room.id: room for room in rooms},
        slots=tuple(slots),
        allocations=tuple(
            Allocation(sid, slot.id, EPOCH) for sid, slot in zip(student_ids, held)
        ),
    )
