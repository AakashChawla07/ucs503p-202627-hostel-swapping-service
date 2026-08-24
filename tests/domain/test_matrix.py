import numpy as np

from hostelswap.domain.matrix import build_matrix
from hostelswap.domain.models import Direction
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from tests.factories import make_pool, room

H7 = room("H7-101", hostel="H7", floor=1)
H9 = room("H9-201", hostel="H9", floor=2)


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


def test_shape():
    pool = make_pool([H7, H9], {"s1": "H7-101-a", "s2": "H9-201-a"})

    matrix = build_matrix(pool)

    assert matrix.costs.shape == (2, 2)
    assert set(matrix.student_ids) == {"s1", "s2"}
    assert set(matrix.slot_ids) == {"H7-101-a", "H9-201-a"}


def test_cost_is_negated_score():
    pool = make_pool(
        [H7, H9],
        {"s1": "H7-101-a", "s2": "H9-201-a"},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2"),
        },
    )

    matrix = build_matrix(pool)
    row = matrix.student_ids.index("s1")

    # s1 wants H9, so the H9 slot costs -1.0 and the H7 slot costs 0.0
    assert matrix.costs[row][matrix.slot_ids.index("H9-201-a")] == -1.0
    assert matrix.costs[row][matrix.slot_ids.index("H7-101-a")] == 0.0


def test_hard_violation_is_inf():
    pool = make_pool(
        [H7, H9],
        {"s1": "H7-101-a", "s2": "H9-201-a"},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
            "s2": wants("s2"),
        },
    )

    matrix = build_matrix(pool)
    row = matrix.student_ids.index("s1")

    assert matrix.costs[row][matrix.slot_ids.index("H7-101-a")] == np.inf
    assert np.isfinite(matrix.costs[row][matrix.slot_ids.index("H9-201-a")])


def test_scores_are_kept():
    pool = make_pool(
        [H7, H9],
        {"s1": "H7-101-a", "s2": "H9-201-a"},
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2"),
        },
    )

    matrix = build_matrix(pool)
    score = matrix.score_for("s1", "H9-201-a")

    assert score.value == 1.0
    assert score.satisfied[0].criterion is Criterion.HOSTEL


def test_roommate_uses_occupants():
    double = room("H7-101", hostel="H7", capacity=2)
    single = room("H9-201", hostel="H9", capacity=1)
    pool = make_pool(
        [double, single],
        {"s1": "H7-101-a", "s2": "H7-101-b", "s3": "H9-201-a"},
        preferences={
            "s1": wants("s1"),
            "s2": wants("s2"),
            # s3 wants to room with s2, who currently lives in the double.
            "s3": wants("s3", Preference(Criterion.ROOMMATE, "s2", weight=1.0)),
        },
    )

    matrix = build_matrix(pool)

    assert matrix.score_for("s3", "H7-101-a").value == 1.0
    assert matrix.score_for("s3", "H9-201-a").value == 0.0


def test_roommate_excludes_self():
    double = room("H7-101", hostel="H7", capacity=2)
    single = room("H9-201", hostel="H9", capacity=1)
    pool = make_pool(
        [double, single],
        {"s1": "H7-101-a", "s2": "H7-101-b", "s3": "H9-201-a"},
        preferences={
            # s1 asks for s1 -- nonsense, but it must not self-satisfy.
            "s1": wants("s1", Preference(Criterion.ROOMMATE, "s1", weight=1.0)),
            "s2": wants("s2"),
            "s3": wants("s3"),
        },
    )

    matrix = build_matrix(pool)

    assert matrix.score_for("s1", "H7-101-a").value == 0.0
