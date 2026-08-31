import pytest

from hostelswap.domain.models import Direction, Room, WashroomType
from hostelswap.domain.preferences import Criterion, Preference, PreferenceSet
from hostelswap.domain.scoring import score

ROOM = Room(
    id="H7-101",
    hostel="H7",
    floor=1,
    direction=Direction.N,
    washroom_type=WashroomType.ATTACHED,
    capacity=2,
)


def prefs(*preferences):
    return PreferenceSet(student_id="s1", preferences=preferences)


def test_weighted_fraction():
    result = score(
        prefs(
            Preference(Criterion.HOSTEL, "H7", weight=3.0),  # satisfied
            Preference(Criterion.FLOOR, 4, weight=1.0),      # not satisfied
        ),
        ROOM,
        occupants=(),
    )

    assert result.value == 0.75


def test_no_prefs_scores_one():
    assert score(prefs(), ROOM, occupants=()).value == 1.0


@pytest.mark.parametrize(
    "preference,expected",
    [
        (Preference(Criterion.HOSTEL, "H7", weight=1.0), True),
        (Preference(Criterion.HOSTEL, "H9", weight=1.0), False),
        (Preference(Criterion.FLOOR, 1, weight=1.0), True),
        (Preference(Criterion.FLOOR, 2, weight=1.0), False),
        (Preference(Criterion.DIRECTION, Direction.N, weight=1.0), True),
        (Preference(Criterion.DIRECTION, Direction.S, weight=1.0), False),
        (Preference(Criterion.WASHROOM, "attached", weight=1.0), True),
        (Preference(Criterion.WASHROOM, "common", weight=1.0), False),
        (Preference(Criterion.ROOM_TYPE, "2SNAC", weight=1.0), True),
        (Preference(Criterion.ROOM_TYPE, "2SAC", weight=1.0), False),
    ],
)
def test_room_criteria(preference, expected):
    result = score(prefs(preference), ROOM, occupants=())

    assert result.value == (1.0 if expected else 0.0)


def test_roommate():
    preference = Preference(Criterion.ROOMMATE, "s2", weight=1.0)

    assert score(prefs(preference), ROOM, occupants=("s2",)).value == 1.0
    assert score(prefs(preference), ROOM, occupants=("s9",)).value == 0.0


def test_hard_unmet_infeasible():
    result = score(
        prefs(Preference(Criterion.HOSTEL, "H9", weight=1.0, hard=True)),
        ROOM,
        occupants=(),
    )

    assert result.feasible is False


def test_hard_met_feasible():
    result = score(
        prefs(Preference(Criterion.HOSTEL, "H7", weight=1.0, hard=True)),
        ROOM,
        occupants=(),
    )

    assert result.feasible is True


def test_hard_not_in_score():
    # Only the soft FLOOR preference is unsatisfied, so the value is 0.0
    # even though the hard HOSTEL preference is met.
    result = score(
        prefs(
            Preference(Criterion.HOSTEL, "H7", weight=5.0, hard=True),
            Preference(Criterion.FLOOR, 4, weight=1.0),
        ),
        ROOM,
        occupants=(),
    )

    assert result.value == 0.0
    assert result.feasible is True


def test_breakdown():
    hostel = Preference(Criterion.HOSTEL, "H7", weight=1.0)
    floor = Preference(Criterion.FLOOR, 4, weight=1.0)

    result = score(prefs(hostel, floor), ROOM, occupants=())

    assert result.satisfied == (hostel,)
    assert result.unsatisfied == (floor,)
