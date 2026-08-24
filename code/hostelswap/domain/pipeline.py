"""Full matching run: pool in, options out."""

from .kbest import k_best
from .matrix import build_matrix
from .pool import SwapPool
from .ranking import SwapOption, rank

# The optimal assignment is often rejected by the Pareto filter, so the
# alternatives are where an executable option is usually found.
DEFAULT_K = 50


def find_swap_options(pool: SwapPool, k: int = DEFAULT_K) -> tuple[SwapOption, ...]:
    """Raises NoFeasibleAssignment if hard constraints cannot all be met.

    Returns an empty tuple when the pool is solvable but nobody can be
    made better off.
    """
    matrix = build_matrix(pool)
    return rank(pool, matrix, k_best(matrix, k))
