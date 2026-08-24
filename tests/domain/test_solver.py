import pytest

from hostelswap.domain.matrix import build_matrix
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.solver import NoFeasibleAssignment, solve
from tests.factories import make_pool, room

H7 = room("H7-101", hostel="H7")
H9 = room("H9-201", hostel="H9")


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


def crossed_pool(hard=False):
    """s1 sits in H7 and wants H9; s2 sits in H9 and wants H7."""
    return make_pool(
        [H7, H9],
        {"s1": "H7-101-a", "s2": "H9-201-a"},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=hard)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H7", weight=1.0, hard=hard)),
        },
    )


def test_is_a_permutation():
    matrix = build_matrix(crossed_pool())

    assignment = solve(matrix)

    assert set(assignment.slot_by_student) == {"s1", "s2"}
    assert len(set(assignment.slot_by_student.values())) == 2


def test_picks_the_swap():
    matrix = build_matrix(crossed_pool())

    assignment = solve(matrix)

    assert assignment.slot_by_student["s1"] == "H9-201-a"
    assert assignment.slot_by_student["s2"] == "H7-101-a"


def test_forbid_edge():
    matrix = build_matrix(crossed_pool())

    assignment = solve(matrix, forbidden={("s1", "H9-201-a")})

    assert assignment.slot_by_student["s1"] == "H7-101-a"


def test_require_edge():
    matrix = build_matrix(crossed_pool())

    assignment = solve(matrix, required={("s1", "H7-101-a")})

    assert assignment.slot_by_student["s1"] == "H7-101-a"
    assert assignment.slot_by_student["s2"] == "H9-201-a"


def test_over_constrained_raises():
    # Both students hard-require H9, but there is only one H9 slot.
    pool = make_pool(
        [H7, H9],
        {"s1": "H7-101-a", "s2": "H9-201-a"},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
        },
    )

    with pytest.raises(NoFeasibleAssignment):
        solve(build_matrix(pool))


def test_forbid_last_option_raises():
    matrix = build_matrix(crossed_pool(hard=True))

    with pytest.raises(NoFeasibleAssignment):
        solve(matrix, forbidden={("s1", "H9-201-a")})


def test_cost_total():
    matrix = build_matrix(crossed_pool())

    assignment = solve(matrix)

    # Both students fully satisfied: two cells of -1.0
    assert assignment.cost == pytest.approx(-2.0)
