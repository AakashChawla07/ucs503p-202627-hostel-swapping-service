"""The students seeking a swap and the slots they hold."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property

from .models import Allocation, BedSlot, Room, Student
from .preferences import PreferenceSet


class InvalidPool(Exception):
    pass


@dataclass(frozen=True)
class SwapPool:
    students: tuple[Student, ...]
    preferences: Mapping[str, PreferenceSet]
    rooms: Mapping[str, Room]
    slots: tuple[BedSlot, ...]
    allocations: tuple[Allocation, ...]

    def __post_init__(self) -> None:
        # A pool must be closed -- as many slots as students -- or the
        # assignment is not a permutation and cycle decomposition breaks.
        if len(self.students) != len(self.slots):
            raise InvalidPool(
                f"pool has {len(self.students)} students but {len(self.slots)} slots"
            )
        for student in self.students:
            if student.id not in self._latest_allocation:
                raise InvalidPool(f"student {student.id} has no allocation")

    @cached_property
    def _latest_allocation(self) -> Mapping[str, Allocation]:
        # Allocation history is append-only, so current state is the
        # newest row per student rather than a stored field.
        latest: dict[str, Allocation] = {}
        for allocation in self.allocations:
            previous = latest.get(allocation.student_id)
            if previous is None or allocation.effective_from >= previous.effective_from:
                latest[allocation.student_id] = allocation
        return latest

    @cached_property
    def _slots_by_id(self) -> Mapping[str, BedSlot]:
        return {slot.id: slot for slot in self.slots}

    def current_slot_id(self, student_id: str) -> str:
        return self._latest_allocation[student_id].slot_id

    def room_of_slot(self, slot_id: str) -> Room:
        return self.rooms[self._slots_by_id[slot_id].room_id]

    def current_room(self, student_id: str) -> Room:
        return self.room_of_slot(self.current_slot_id(student_id))

    def occupants_of(self, room_id: str) -> tuple[str, ...]:
        return tuple(
            student.id
            for student in self.students
            if self._slots_by_id[self.current_slot_id(student.id)].room_id == room_id
        )

    def preferences_of(self, student_id: str) -> PreferenceSet:
        return self.preferences[student_id]
