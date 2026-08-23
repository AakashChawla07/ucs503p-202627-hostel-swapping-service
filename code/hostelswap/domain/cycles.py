"""Swap chains from an assignment."""

from dataclasses import dataclass

from .pool import SwapPool
from .solver import Assignment


@dataclass(frozen=True)
class Chain:
    students: tuple[str, ...]

    @property
    def length(self) -> int:
        return len(self.students)

    def __len__(self) -> int:
        return len(self.students)


def decompose(pool: SwapPool, assignment: Assignment) -> tuple[Chain, ...]:
    """Split an assignment into disjoint swap cycles.

    A cycle (a, b, c) means a takes b's slot, b takes c's, c takes a's.
    Students who keep their own slot are dropped. Cycles are disjoint,
    so each one can execute on its own.
    """
    holder_of_slot = {
        pool.current_slot_id(student.id): student.id for student in pool.students
    }
    successor = {
        student_id: holder_of_slot[slot_id]
        for student_id, slot_id in assignment.slot_by_student.items()
    }

    chains: list[Chain] = []
    visited: set[str] = set()

    for student_id in sorted(successor):
        if student_id in visited:
            continue

        cycle: list[str] = []
        walker = student_id
        while walker not in visited:
            visited.add(walker)
            cycle.append(walker)
            walker = successor[walker]

        if len(cycle) > 1:
            chains.append(Chain(tuple(cycle)))

    return tuple(chains)
