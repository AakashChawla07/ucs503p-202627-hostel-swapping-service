"""Student preferences over rooms."""

from dataclasses import dataclass
from enum import Enum

from .models import Direction


class Criterion(Enum):
    HOSTEL = "hostel"
    FLOOR = "floor"
    DIRECTION = "direction"
    WASHROOM = "washroom"
    ROOM_TYPE = "room_type"
    # Unlike the others this depends on another student, not on the room.
    ROOMMATE = "roommate"


@dataclass(frozen=True)
class Preference:
    criterion: Criterion
    value: str | int | bool | Direction
    weight: float
    hard: bool = False


@dataclass(frozen=True)
class PreferenceSet:
    student_id: str
    preferences: tuple[Preference, ...] = ()

    def soft(self) -> tuple[Preference, ...]:
        return tuple(p for p in self.preferences if not p.hard)
