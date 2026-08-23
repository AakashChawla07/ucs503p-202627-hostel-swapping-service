"""Murty's algorithm for the K best assignments."""

import heapq
from dataclasses import dataclass
from itertools import count

from .matrix import CostMatrix
from .solver import Assignment, Edge, NoFeasibleAssignment, solve


@dataclass(frozen=True)
class _Node:
    assignment: Assignment
    forbidden: frozenset[Edge]
    required: frozenset[Edge]


def k_best(matrix: CostMatrix, k: int) -> tuple[Assignment, ...]:
    """Up to `k` assignments, cheapest first.

    Any assignment other than the best must exclude at least one of its
    edges. So for each edge in turn, forbid it while requiring the ones
    before it. Those subproblems are disjoint and together cover
    everything except the parent, so nothing repeats and nothing is
    missed.
    """
    if k <= 0:
        return ()

    best = solve(matrix)

    tiebreak = count()
    queue: list[tuple[float, int, _Node]] = [
        (best.cost, next(tiebreak), _Node(best, frozenset(), frozenset()))
    ]
    results: list[Assignment] = []
    seen: set[frozenset[Edge]] = set()

    while queue and len(results) < k:
        _, _, node = heapq.heappop(queue)
        if node.assignment.edges in seen:
            continue
        seen.add(node.assignment.edges)
        results.append(node.assignment)

        required = set(node.required)
        for edge in sorted(node.assignment.edges - node.required):
            child_forbidden = node.forbidden | {edge}
            try:
                child = solve(matrix, forbidden=child_forbidden, required=required)
            except NoFeasibleAssignment:
                pass
            else:
                if child.edges not in seen:
                    heapq.heappush(
                        queue,
                        (
                            child.cost,
                            next(tiebreak),
                            _Node(child, child_forbidden, frozenset(required)),
                        ),
                    )
            required.add(edge)

    return tuple(results)
