"""Helpers for building small, explicit pools in tests.

Test-only code lives here rather than in the domain package.
"""

from datetime import datetime

from hostelswap.domain.models import Allocation, BedSlot, Direction, Room, Student
from hostelswap.domain.pool import SwapPool
from hostelswap.domain.preferences import PreferenceSet

EPOCH = datetime(2026, 1, 1)


def room(room_id, hostel="H7", floor=1, direction=Direction.N, washroom=True, capacity=1):
    return Room(room_id, hostel, floor, direction, washroom, capacity)


def slots_for(rooms):
    return tuple(
        BedSlot(f"{r.id}-{chr(ord('a') + i)}", r.id)
        for r in rooms
        for i in range(r.capacity)
    )


def make_pool(rooms, assignment, preferences=None):
    """Build a pool from `assignment`, a mapping of student id -> slot id."""
    occupied = set(assignment.values())
    students = tuple(Student(sid, sid.upper()) for sid in assignment)
    return SwapPool(
        students=students,
        preferences=preferences or {s.id: PreferenceSet(s.id) for s in students},
        rooms={r.id: r for r in rooms},
        slots=tuple(s for s in slots_for(rooms) if s.id in occupied),
        allocations=tuple(
            Allocation(sid, slot_id, EPOCH) for sid, slot_id in assignment.items()
        ),
    )
