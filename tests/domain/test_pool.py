from datetime import datetime

import pytest

from hostelswap.domain.models import Allocation, BedSlot, Direction, Room, Student
from hostelswap.domain.pool import InvalidPool, SwapPool
from hostelswap.domain.preferences import PreferenceSet

ROOM_A = Room("H7-101", "H7", 1, Direction.N, True, capacity=2)
ROOM_B = Room("H9-201", "H9", 2, Direction.S, False, capacity=1)

SLOT_A1 = BedSlot("H7-101-a", "H7-101")
SLOT_A2 = BedSlot("H7-101-b", "H7-101")
SLOT_B1 = BedSlot("H9-201-a", "H9-201")

JAN = datetime(2026, 1, 1)
JUN = datetime(2026, 6, 1)


def build(allocations, slots=(SLOT_A1, SLOT_A2, SLOT_B1), students=("s1", "s2", "s3")):
    return SwapPool(
        students=tuple(Student(s, s.upper()) for s in students),
        preferences={s: PreferenceSet(s) for s in students},
        rooms={r.id: r for r in (ROOM_A, ROOM_B)},
        slots=slots,
        allocations=allocations,
    )


def test_current_slot_is_latest():
    pool = build(
        allocations=(
            Allocation("s1", SLOT_A1.id, JAN),
            Allocation("s1", SLOT_B1.id, JUN),  # s1 moved in June
            Allocation("s2", SLOT_A2.id, JAN),
            Allocation("s3", SLOT_A1.id, JUN),  # s3 took the slot s1 left
        ),
    )

    assert pool.current_slot_id("s1") == SLOT_B1.id
    assert pool.current_slot_id("s3") == SLOT_A1.id


def test_history_is_append_only():
    allocations = (
        Allocation("s1", SLOT_A1.id, JAN),
        Allocation("s1", SLOT_B1.id, JUN),
        Allocation("s2", SLOT_A2.id, JAN),
        Allocation("s3", SLOT_A1.id, JUN),
    )
    pool = build(allocations=allocations)

    # The superseded January row for s1 is still present.
    assert pool.allocations == allocations


def test_occupants():
    pool = build(
        allocations=(
            Allocation("s1", SLOT_A1.id, JAN),
            Allocation("s2", SLOT_A2.id, JAN),
            Allocation("s3", SLOT_B1.id, JAN),
        ),
    )

    assert set(pool.occupants_of("H7-101")) == {"s1", "s2"}
    assert pool.occupants_of("H9-201") == ("s3",)


def test_room_of_slot():
    pool = build(
        allocations=(
            Allocation("s1", SLOT_A1.id, JAN),
            Allocation("s2", SLOT_A2.id, JAN),
            Allocation("s3", SLOT_B1.id, JAN),
        ),
    )

    assert pool.room_of_slot(SLOT_A1.id) is ROOM_A
    assert pool.room_of_slot(SLOT_B1.id) is ROOM_B


def test_slot_count_mismatch():
    with pytest.raises(InvalidPool, match="3 students"):
        build(
            allocations=(
                Allocation("s1", SLOT_A1.id, JAN),
                Allocation("s2", SLOT_A2.id, JAN),
                Allocation("s3", SLOT_B1.id, JAN),
            ),
            slots=(SLOT_A1, SLOT_A2),
        )


def test_missing_allocation():
    with pytest.raises(InvalidPool, match="s3"):
        build(
            allocations=(
                Allocation("s1", SLOT_A1.id, JAN),
                Allocation("s2", SLOT_A2.id, JAN),
            ),
        )
