import pytest

from hostelswap.domain.kbest import k_best
from hostelswap.domain.matrix import build_matrix
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.solver import NoFeasibleAssignment, solve
from tests.factories import make_pool, room

H7 = room("H7-101", hostel="H7", floor=1)
H9 = room("H9-201", hostel="H9", floor=2)
H11 = room("H11-301", hostel="H11", floor=3)

ASSIGNMENT = {"s1": "H7-101-a", "s2": "H9-201-a", "s3": "H11-301-a"}


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


def rotated_pool():
    """Each student wants the next student's hostel: one clean 3-cycle."""
    return make_pool(
        [H7, H9, H11],
        ASSIGNMENT,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )


def test_first_is_optimal():
    matrix = build_matrix(rotated_pool())

    candidates = k_best(matrix, 4)

    assert candidates[0].edges == solve(matrix).edges


def test_sorted_by_cost():
    matrix = build_matrix(rotated_pool())

    costs = [candidate.cost for candidate in k_best(matrix, 6)]

    assert costs == sorted(costs)


def test_no_duplicates():
    matrix = build_matrix(rotated_pool())

    candidates = k_best(matrix, 6)

    assert len({candidate.edges for candidate in candidates}) == len(candidates)


def test_enumerates_all():
    matrix = build_matrix(rotated_pool())

    # Three students over three slots: 3! = 6 distinct assignments.
    assert len(k_best(matrix, 100)) == 6


def test_k_one():
    matrix = build_matrix(rotated_pool())

    assert len(k_best(matrix, 1)) == 1


def test_hard_constraints_prune():
    pool = make_pool(
        [H7, H9, H11],
        ASSIGNMENT,
        preferences={
            # s1 will only accept H9, which fixes one edge for every candidate.
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s2": wants("s2"),
            "s3": wants("s3"),
        },
    )
    matrix = build_matrix(pool)

    candidates = k_best(matrix, 100)

    assert len(candidates) == 2  # s1 pinned to H9; s2 and s3 may swap
    assert all(c.slot_by_student["s1"] == "H9-201-a" for c in candidates)


def test_infeasible_raises():
    pool = make_pool(
        [H7, H9, H11],
        ASSIGNMENT,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s3": wants("s3"),
        },
    )

    with pytest.raises(NoFeasibleAssignment):
        k_best(build_matrix(pool), 3)
