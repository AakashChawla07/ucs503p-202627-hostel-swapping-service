import pytest

from hostelswap.domain.pipeline import find_swap_options
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.ranking import OptionKind
from hostelswap.domain.solver import NoFeasibleAssignment
from tests.factories import make_pool, room

A = room("H7-101", hostel="H7", floor=1)
B = room("H9-201", hostel="H9", floor=2)
C = room("H11-301", hostel="H11", floor=3)

HELD = {"s1": "H7-101-a", "s2": "H9-201-a", "s3": "H11-301-a"}


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


def test_two_way_swap():
    pool = make_pool(
        [A, B],
        {"s1": HELD["s1"], "s2": HELD["s2"]},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )

    options = find_swap_options(pool)

    assert options[0].chains[0].students == ("s1", "s2")
    assert options[0].mean_match == 1.0


def test_three_way_ring():
    pool = make_pool(
        [A, B, C],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )

    options = find_swap_options(pool)

    assert options[0].chains[0].students == ("s1", "s2", "s3")
    assert options[0].mean_match == 1.0


def test_nothing_to_gain():
    pool = make_pool(
        [A, B],
        {"s1": HELD["s1"], "s2": HELD["s2"]},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
        },
    )

    assert find_swap_options(pool) == ()


def test_over_constrained_raises():
    pool = make_pool(
        [A, B],
        {"s1": HELD["s1"], "s2": HELD["s2"]},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
        },
    )

    with pytest.raises(NoFeasibleAssignment):
        find_swap_options(pool)


def test_at_most_three():
    pool = make_pool(
        [A, B, C],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )

    assert len(find_swap_options(pool, k=50)) <= 3


def test_kinds_are_distinct():
    pool = make_pool(
        [A, B, C],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )

    options = find_swap_options(pool)
    kinds = [option.kind for option in options]

    assert len(kinds) == len(set(kinds))
    assert all(isinstance(kind, OptionKind) for kind in kinds)
