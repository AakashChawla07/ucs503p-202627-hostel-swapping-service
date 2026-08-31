"""Entities of the swap pool."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(Enum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"


class WashroomType(Enum):
    ATTACHED = "attached"
    COMMON = "common"
    SHARING = "sharing"


@dataclass(frozen=True)
class Student:
    id: str
    name: str


@dataclass(frozen=True)
class Room:
    id: str
    hostel: str
    floor: int
    direction: Direction
    washroom_type: WashroomType
    capacity: int
    ac: bool = False

    @property
    def room_type_code(self) -> str:
        # e.g. "2SAC" / "2SNAC" -- always derived from capacity + ac so it
        # can never drift from the columns it is made of.
        return f"{self.capacity}S{'A' if self.ac else 'NA'}C"


@dataclass(frozen=True)
class BedSlot:
    # Assignment is per bed, not per room: a triple room is three slots.
    id: str
    room_id: str


@dataclass(frozen=True)
class Allocation:
    student_id: str
    slot_id: str
    effective_from: datetime
