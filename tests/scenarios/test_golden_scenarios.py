"""Known-answer scenarios: the claims this service makes, as tests.

Each case is hand-constructed so the right answer is obvious by
inspection, which is what makes a failure here meaningful rather than
merely red.
"""

import time

from hostelswap.domain.pipeline import find_swap_options
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.ranking import OptionKind
from hostelswap.synth.generator import generate_pool
from tests.factories import make_pool, room

A = room("H7-101", hostel="H7", floor=1)
B = room("H9-201", hostel="H9", floor=2)
C = room("H11-301", hostel="H11", floor=3)

HELD = {"s1": "H7-101-a", "s2": "H9-201-a", "s3": "H11-301-a"}


def wants(student_id, *preferences):
    return PreferenceSet(student_id, preferences)


# --- The premise -------------------------------------------------------


def test_three_way_cycle_no_pair_works():
    """The reason this service exists.

    s1 wants s2's hostel, s2 wants s3's, s3 wants s1's.  No two of them
    can help each other directly -- every direct swap leaves one of the
    pair no better off.  The rotation satisfies all three.
    """
    pool = make_pool(
        [A, B, C],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H9", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s3": wants("s3", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
        },
    )

    best = find_swap_options(pool)[0]

    assert best.chains[0].students == ("s1", "s2", "s3")
    assert best.mean_match == 1.0
    assert all(outcome.match.percentage == 100 for outcome in best.outcomes.values())


# --- Why K-best is a correctness requirement ---------------------------


def dominant_but_unfair_pool():
    """The optimal assignment is the one nobody would approve.

    Scores: s1 rates C at 1.00, s2 rates A at 1.00, s3 rates C at 0.50
    (it is their hostel but the wrong floor) and everything else at 0.

    The best total is s1->C, s2->A, s3->B, scoring 2.00 -- but it drags
    s3 from 0.50 down to 0.  The second best, s1->B, s2->A, s3 stays,
    scores only 1.50 and is the one that can actually execute.
    """
    return make_pool(
        [A, B, C],
        HELD,
        preferences={
            "s1": wants("s1", Preference(Criterion.HOSTEL, "H11", weight=1.0)),
            "s2": wants("s2", Preference(Criterion.HOSTEL, "H7", weight=1.0)),
            "s3": wants(
                "s3",
                Preference(Criterion.HOSTEL, "H11", weight=1.0),
                Preference(Criterion.FLOOR, 9, weight=1.0),  # no such floor
            ),
        },
    )


def test_k1_finds_nothing():
    assert find_swap_options(dominant_but_unfair_pool(), k=1) == ()


def test_k2_finds_the_swap():
    options = find_swap_options(dominant_but_unfair_pool(), k=2)

    assert options[0].chains[0].students == ("s1", "s2")
    # s3 is untouched, so they are not a participant at all.
    assert "s3" not in options[0].outcomes


# --- The differentiated top three --------------------------------------


def test_shorter_chain_for_less_match():
    """The answer to "a single score is unidimensional".

    The fastest option here gives up a little match quality to shorten
    the longest chain, from six students to four.
    Ranking on match alone would hide that.
    """
    options = find_swap_options(generate_pool(students=12, seed=3), k=30)

    assert len(options) == 3
    assert [o.kind for o in options] == [
        OptionKind.BEST_OVERALL,
        OptionKind.FASTEST,
        OptionKind.BEST_LOCATION,
    ]

    best, fastest, _ = options
    assert fastest.longest_chain < best.longest_chain
    assert best.mean_match - fastest.mean_match < 0.07


def test_labels_are_true():
    options = find_swap_options(generate_pool(students=12, seed=3), k=30)
    by_kind = {option.kind: option for option in options}

    assert all(
        by_kind[OptionKind.FASTEST].longest_chain < other.longest_chain
        for other in options
        if other.kind is not OptionKind.FASTEST
    )
    assert all(
        by_kind[OptionKind.BEST_LOCATION].location_match > other.location_match
        for other in options
        if other.kind is not OptionKind.BEST_LOCATION
    )


# --- Structural invariants over a realistic pool -----------------------


def test_pareto_holds():
    options = find_swap_options(generate_pool(students=40, seed=3), k=25)

    assert options
    for option in options:
        assert all(outcome.delta >= 0 for outcome in option.outcomes.values())
        assert any(outcome.delta > 0 for outcome in option.outcomes.values())


def test_chains_disjoint():
    options = find_swap_options(generate_pool(students=40, seed=3), k=25)

    for option in options:
        members = [s for chain in option.chains for s in chain.students]
        assert len(members) == len(set(members))


def test_moves_are_closed():
    pool = generate_pool(students=40, seed=3)
    options = find_swap_options(pool, k=25)

    held = {pool.current_slot_id(s.id) for s in pool.students}
    for option in options:
        destinations = [o.to_slot_id for o in option.outcomes.values()]
        assert set(destinations) <= held
        assert len(destinations) == len(set(destinations))


# --- Scalability -------------------------------------------------------


def test_100_students_under_10s():
    pool = generate_pool(students=100, seed=1)

    started = time.perf_counter()
    options = find_swap_options(pool, k=25)
    elapsed = time.perf_counter() - started

    assert options
    assert elapsed < 10.0, f"took {elapsed:.2f}s"
