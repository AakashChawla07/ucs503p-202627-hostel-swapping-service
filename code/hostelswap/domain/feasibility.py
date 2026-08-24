"""Which chains students would actually approve."""

from collections.abc import Iterable

from .cycles import Chain
from .matrix import CostMatrix
from .pool import SwapPool
from .solver import Assignment

EPSILON = 1e-9


def delta(
    pool: SwapPool, matrix: CostMatrix, student_id: str, new_slot_id: str
) -> float:
    current = matrix.score_for(student_id, pool.current_slot_id(student_id))
    proposed = matrix.score_for(student_id, new_slot_id)
    return proposed.value - current.value


def is_pareto_improving(
    pool: SwapPool, matrix: CostMatrix, assignment: Assignment, chain: Chain
) -> bool:
    """Nobody worse off, at least one better off.

    Checked after the solve, not during it: the solver maximises the
    total, which can mean demoting one student to benefit several. That
    chain would just be rejected at the approval step.
    """
    deltas = [
        delta(pool, matrix, student_id, assignment.slot_by_student[student_id])
        for student_id in chain.students
    ]
    return all(d >= -EPSILON for d in deltas) and any(d > EPSILON for d in deltas)


def feasible_chains(
    pool: SwapPool,
    matrix: CostMatrix,
    assignment: Assignment,
    chains: Iterable[Chain],
) -> tuple[Chain, ...]:
    return tuple(
        chain for chain in chains if is_pareto_improving(pool, matrix, assignment, chain)
    )
