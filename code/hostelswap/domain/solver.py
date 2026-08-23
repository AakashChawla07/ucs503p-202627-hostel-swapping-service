"""Hungarian assignment over the cost matrix."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from .matrix import INFEASIBLE, CostMatrix

Edge = tuple[str, str]


class NoFeasibleAssignment(Exception):
    pass


@dataclass(frozen=True)
class Assignment:
    slot_by_student: Mapping[str, str]
    cost: float

    @property
    def edges(self) -> frozenset[Edge]:
        return frozenset(self.slot_by_student.items())

    def __len__(self) -> int:
        return len(self.slot_by_student)


def _constrained_costs(
    matrix: CostMatrix, forbidden: Iterable[Edge], required: Iterable[Edge]
) -> np.ndarray:
    costs = matrix.costs.copy()

    for student_id, slot_id in forbidden:
        costs[matrix.row_of(student_id), matrix.column_of(slot_id)] = INFEASIBLE

    for student_id, slot_id in required:
        row, column = matrix.row_of(student_id), matrix.column_of(slot_id)
        keep = costs[row, column]
        # Poison the rest of the row and column so the solver has no
        # alternative. Avoids carving submatrices for Murty's.
        costs[row, :] = INFEASIBLE
        costs[:, column] = INFEASIBLE
        costs[row, column] = keep

    return costs


def solve(
    matrix: CostMatrix,
    forbidden: Iterable[Edge] = (),
    required: Iterable[Edge] = (),
) -> Assignment:
    costs = _constrained_costs(matrix, forbidden, required)

    try:
        rows, columns = linear_sum_assignment(costs)
    except ValueError as exc:
        raise NoFeasibleAssignment("hard constraints cannot all be met") from exc

    total = float(costs[rows, columns].sum())
    if not np.isfinite(total):
        raise NoFeasibleAssignment("hard constraints cannot all be met")

    return Assignment(
        slot_by_student={
            matrix.student_ids[row]: matrix.slot_ids[column]
            for row, column in zip(rows, columns)
        },
        cost=total,
    )
