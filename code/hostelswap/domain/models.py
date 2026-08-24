"""Entities of the swap pool."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(Enum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"


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
    has_attached_washroom: bool
    capacity: int


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
