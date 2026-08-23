from hostelswap.domain.matrix import build_matrix
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.ranking import OptionKind, rank
from hostelswap.domain.solver import Assignment
from tests.factories import make_pool, room

A = room("H7-101", hostel="H7", floor=1)
B = room("H9-201", hostel="H9", floor=2)
C = room("H11-301", hostel="H11", floor=3)
D = room("H13-401", hostel="H13", floor=4)

HELD = {"s1": "H7-101-a", "s2": "H9-201-a", "s3": "H11-301-a", "s4": "H13-401-a"}

# Everyone wants the hostel of the student one step along the ring.
CHAIN_POOL_PREFS = {
    "s1": PreferenceSet("s1", (Preference(Criterion.HOSTEL, "H9", weight=1.0),)),
    "s2": PreferenceSet("s2", (Preference(Criterion.HOSTEL, "H11", weight=1.0),)),
    "s3": PreferenceSet("s3", (Preference(Criterion.HOSTEL, "H13", weight=1.0),)),
    "s4": PreferenceSet("s4", (Preference(Criterion.HOSTEL, "H7", weight=1.0),)),
}

# A four-way rotation: everyone gets exactly what they asked for.
LONG = Assignment({"s1": HELD["s2"], "s2": HELD["s3"], "s3": HELD["s4"], "s4": HELD["s1"]}, 0.0)
# A three-way rotation: s1 and s2 gain, s3 is neutral, s4 untouched.
MID = Assignment({"s1": HELD["s2"], "s2": HELD["s3"], "s3": HELD["s1"], "s4": HELD["s4"]}, 0.0)
# A single exchange: s1 gains, s2 is neutral.
SHORT = Assignment({"s1": HELD["s2"], "s2": HELD["s1"], "s3": HELD["s3"], "s4": HELD["s4"]}, 0.0)


def ring_pool():
    return make_pool([A, B, C, D], HELD, preferences=CHAIN_POOL_PREFS)


def ranked(*candidates):
    pool = ring_pool()
    return rank(pool, build_matrix(pool), candidates)


def by_kind(options):
    return {option.kind: option for option in options}


def test_ring_gives_two_options():
    # LONG maximises both match and location fit; SHORT is strictly
    # faster.  Nothing remaining beats either, so a third option would
    # be padding with a label it has not earned.
    options = ranked(LONG, MID, SHORT)

    assert len(options) == 2
    assert {o.kind for o in options} == {OptionKind.BEST_OVERALL, OptionKind.FASTEST}


def test_options_are_distinct():
    options = ranked(LONG, MID, SHORT)

    signatures = {tuple(chain.students for chain in o.chains) for o in options}

    assert len(signatures) == len(options)


def test_best_overall():
    options = by_kind(ranked(LONG, MID, SHORT))

    assert options[OptionKind.BEST_OVERALL].mean_match == 1.0
    assert options[OptionKind.BEST_OVERALL].chains[0].length == 4


def test_fastest():
    options = by_kind(ranked(LONG, MID, SHORT))

    assert options[OptionKind.FASTEST].longest_chain == 2


def test_no_padding():
    options = ranked(LONG, SHORT)

    assert len(options) == 2
    assert len({tuple(c.students for c in o.chains) for o in options}) == 2


def test_infeasible_dropped():
    # s1 already holds the hostel they want, so any move demotes them.
    pool = make_pool(
        [A, B],
        {"s1": HELD["s1"], "s2": HELD["s2"]},
        preferences={
            "s1": PreferenceSet("s1", (Preference(Criterion.HOSTEL, "H7", weight=1.0),)),
            "s2": PreferenceSet("s2", (Preference(Criterion.HOSTEL, "H9", weight=1.0),)),
        },
    )
    swap = Assignment({"s1": HELD["s2"], "s2": HELD["s1"]}, 0.0)

    assert rank(pool, build_matrix(pool), (swap,)) == ()


def test_outcome_details():
    options = ranked(LONG)

    outcome = options[0].outcomes["s1"]

    assert outcome.from_slot_id == HELD["s1"]
    assert outcome.to_slot_id == HELD["s2"]
    assert outcome.match.percentage == 100
    assert outcome.delta == 1.0
    assert [p.criterion for p in outcome.match.satisfied] == [Criterion.HOSTEL]


def test_only_movers_listed():
    options = ranked(SHORT)

    assert set(options[0].outcomes) == {"s1", "s2"}


# --- Label honesty -----------------------------------------------------
# A kind is a claim made to a student.  "Fastest to execute" must mean
# fastest among the options actually shown, or the label misleads.


def test_fastest_label_is_true():
    options = ranked(LONG, MID, SHORT)
    fastest = by_kind(options).get(OptionKind.FASTEST)

    if fastest is not None:
        others = [o for o in options if o.kind is not OptionKind.FASTEST]
        assert all(fastest.longest_chain < o.longest_chain for o in others)


def test_location_label_is_true():
    options = ranked(LONG, MID, SHORT)
    best_location = by_kind(options).get(OptionKind.BEST_LOCATION)

    if best_location is not None:
        others = [o for o in options if o.kind is not OptionKind.BEST_LOCATION]
        assert all(best_location.location_match > o.location_match for o in others)


def test_dominated_not_shown():
    # LONG beats MID on match and on location; SHORT beats MID on speed.
    # MID is best at nothing, so it must not appear at all.
    options = ranked(LONG, MID, SHORT)

    assert all(o.chains[0].length != 3 for o in options)
