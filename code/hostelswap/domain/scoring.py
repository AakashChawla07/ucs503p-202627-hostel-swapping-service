"""Scoring a room for a student."""

from dataclasses import dataclass

from .models import Room
from .preferences import Criterion, Preference, PreferenceSet


@dataclass(frozen=True)
class Score:
    value: float
    satisfied: tuple[Preference, ...]
    unsatisfied: tuple[Preference, ...]
    feasible: bool

    @property
    def percentage(self) -> int:
        return round(self.value * 100)


def _satisfies(preference: Preference, room: Room, occupants: tuple[str, ...]) -> bool:
    match preference.criterion:
        case Criterion.ROOM:
            return room.id == preference.value
        case Criterion.HOSTEL:
            return room.hostel == preference.value
        case Criterion.FLOOR:
            return room.floor == preference.value
        case Criterion.DIRECTION:
            return room.direction == preference.value
        case Criterion.WASHROOM:
            return room.has_attached_washroom == preference.value
        case Criterion.ROOM_TYPE:
            return room.capacity == preference.value
        case Criterion.ROOMMATE:
            return preference.value in occupants
    raise ValueError(f"unhandled criterion: {preference.criterion}")


def score(
    preferences: PreferenceSet,
    room: Room,
    occupants: tuple[str, ...] = (),
) -> Score:
    """Fraction of the student's soft preference weight that `room` meets.

    An unmet hard preference makes the room infeasible instead of just
    lowering the score.
    """
    satisfied: list[Preference] = []
    unsatisfied: list[Preference] = []
    for preference in preferences.preferences:
        bucket = satisfied if _satisfies(preference, room, occupants) else unsatisfied
        bucket.append(preference)

    total_weight = sum(p.weight for p in preferences.soft())
    met_weight = sum(p.weight for p in satisfied if not p.hard)

    return Score(
        # No soft preferences means the student is content anywhere.
        value=1.0 if total_weight == 0 else met_weight / total_weight,
        satisfied=tuple(satisfied),
        unsatisfied=tuple(unsatisfied),
        feasible=not any(p.hard for p in unsatisfied),
    )
