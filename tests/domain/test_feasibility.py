from hostelswap.domain.cycles import Chain
from hostelswap.domain.feasibility import feasible_chains, is_pareto_improving
from hostelswap.domain.matrix import build_matrix
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.solver import Assignment
from tests.factories import make_pool, room

H7 = room("H7-101", hostel="H7")
H9 = room("H9-201", hostel="H9")
H11 = room("H11-301", hostel="H11")

HELD = {"s1": "H7-101-a", "s2": "H9-201-a", "s3": "H11-301-a"}
SWAP_12 = Assignment({"s1": HELD["s2"], "s2": HELD["s1"]}, cost=0.0)
CHAIN_12 = Chain(("s1", "s2"))


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


def two_student_pool(s1_prefs, s2_prefs):
    return make_pool(
        [H7, H9],
        {"s1": HELD["s1"], "s2": HELD["s2"]},
        preferences={"s1": s1_prefs, "s2": s2_prefs},
    )


def check(pool, assignment=SWAP_12, chain=CHAIN_12):
    return is_pareto_improving(pool, build_matrix(pool), assignment, chain)


def test_all_gain_ok():
    pool = two_student_pool(
        wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
        wants("s2", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
    )

    assert check(pool) is True


def test_reject_if_worse_off():
    pool = two_student_pool(
        wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
        # s2 already has what they want; the swap takes it away.
        wants("s2", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
    )

    assert check(pool) is False


def test_reject_if_no_gain():
    pool = two_student_pool(wants("s1"), wants("s2"))

    assert check(pool) is False


def test_neutral_member_ok():
    pool = two_student_pool(
        wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
        wants("s2"),  # indifferent: same score either way
    )

    assert check(pool) is True


def test_filter_drops_bad_chains():
    pool = make_pool(
        [H7, H9, H11],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
            # s3 is happy where they are, so moving them is a loss.
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
        },
    )
    # A good 2-chain, plus a bogus 1-cycle claim that would demote s3.
    assignment = Assignment(
        {"s1": HELD["s2"], "s2": HELD["s3"], "s3": HELD["s1"]}, cost=0.0
    )

    kept = feasible_chains(
        pool, build_matrix(pool), assignment, (Chain(("s1", "s2", "s3")),)
    )

    assert kept == ()
