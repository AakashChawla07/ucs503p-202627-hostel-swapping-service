"""Cost matrix for the Hungarian solver."""

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from .pool import SwapPool
from .scoring import Score, score

INFEASIBLE = np.inf

# Every preference is a property of the room, so moving a student to a
# different bed in the same room changes nothing for them. Breaking ties
# towards their current bed stops the solver shuffling people for no
# gain, which otherwise shows up as a swap from a room to itself.
INERTIA = 1e-9


@dataclass(frozen=True)
class CostMatrix:
    costs: np.ndarray
    student_ids: tuple[str, ...]
    slot_ids: tuple[str, ...]
    # Cell scores are kept so options can explain themselves later.
    scores: Mapping[tuple[str, str], Score] = field(repr=False)

    def score_for(self, student_id: str, slot_id: str) -> Score:
        return self.scores[(student_id, slot_id)]

    def row_of(self, student_id: str) -> int:
        return self.student_ids.index(student_id)

    def column_of(self, slot_id: str) -> int:
        return self.slot_ids.index(slot_id)


def build_matrix(pool: SwapPool) -> CostMatrix:
    """Rows are students, columns are bed slots."""
    student_ids = tuple(student.id for student in pool.students)
    slot_ids = tuple(slot.id for slot in pool.slots)

    costs = np.zeros((len(student_ids), len(slot_ids)), dtype=float)
    scores: dict[tuple[str, str], Score] = {}

    for row, student_id in enumerate(student_ids):
        preferences = pool.preferences_of(student_id)
        for column, slot_id in enumerate(slot_ids):
            room = pool.room_of_slot(slot_id)
            occupants = tuple(
                occupant
                for occupant in pool.occupants_of(room.id)
                if occupant != student_id
            )
            cell = score(preferences, room, occupants)
            scores[(student_id, slot_id)] = cell
            if not cell.feasible:
                costs[row, column] = INFEASIBLE
                continue
            # The solver minimises, so negate the match.
            costs[row, column] = -cell.value
            if slot_id != pool.current_slot_id(student_id):
                costs[row, column] += INERTIA

    return CostMatrix(
        costs=costs,
        student_ids=student_ids,
        slot_ids=slot_ids,
        scores=scores,
    )
