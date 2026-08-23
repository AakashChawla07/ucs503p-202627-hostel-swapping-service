"""Pick options that differ in kind, not just in score."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import fmean

from .cycles import Chain, decompose
from .feasibility import delta, feasible_chains
from .matrix import CostMatrix
from .pool import SwapPool
from .preferences import Criterion
from .scoring import Score
from .solver import Assignment

LOCATION_CRITERIA = frozenset({Criterion.HOSTEL, Criterion.FLOOR, Criterion.DIRECTION})


class OptionKind(Enum):
    BEST_OVERALL = "best_overall"
    FASTEST = "fastest"
    BEST_LOCATION = "best_location"


@dataclass(frozen=True)
class Outcome:
    student_id: str
    from_slot_id: str
    to_slot_id: str
    match: Score
    delta: float


@dataclass(frozen=True)
class SwapOption:
    kind: OptionKind
    chains: tuple[Chain, ...]
    outcomes: Mapping[str, Outcome]
    mean_match: float
    longest_chain: int
    location_match: float

    def with_kind(self, kind: OptionKind) -> "SwapOption":
        return SwapOption(
            kind=kind,
            chains=self.chains,
            outcomes=self.outcomes,
            mean_match=self.mean_match,
            longest_chain=self.longest_chain,
            location_match=self.location_match,
        )


def _location_value(score: Score) -> float:
    # Re-read an existing score through a location-only lens rather than
    # scoring again, so the two numbers cannot drift apart.
    relevant = [
        p
        for p in (*score.satisfied, *score.unsatisfied)
        if p.criterion in LOCATION_CRITERIA and not p.hard
    ]
    total = sum(p.weight for p in relevant)
    if total == 0:
        return 1.0
    met = sum(
        p.weight
        for p in score.satisfied
        if p.criterion in LOCATION_CRITERIA and not p.hard
    )
    return met / total


def _build_option(
    pool: SwapPool, matrix: CostMatrix, assignment: Assignment
) -> SwapOption | None:
    chains = feasible_chains(pool, matrix, assignment, decompose(pool, assignment))
    if not chains:
        return None

    outcomes: dict[str, Outcome] = {}
    for chain in chains:
        for student_id in chain.students:
            to_slot_id = assignment.slot_by_student[student_id]
            outcomes[student_id] = Outcome(
                student_id=student_id,
                from_slot_id=pool.current_slot_id(student_id),
                to_slot_id=to_slot_id,
                match=matrix.score_for(student_id, to_slot_id),
                delta=delta(pool, matrix, student_id, to_slot_id),
            )

    return SwapOption(
        kind=OptionKind.BEST_OVERALL,  # provisional, replaced by the selector
        chains=chains,
        outcomes=outcomes,
        mean_match=fmean(o.match.value for o in outcomes.values()),
        longest_chain=max(chain.length for chain in chains),
        location_match=fmean(_location_value(o.match) for o in outcomes.values()),
    )


def _signature(option: SwapOption) -> tuple:
    return tuple(chain.students for chain in option.chains)


# Each axis, phrased so higher is better.
_AXES: Sequence[tuple[OptionKind, Callable[[SwapOption], float]]] = (
    (OptionKind.BEST_OVERALL, lambda o: o.mean_match),
    (OptionKind.FASTEST, lambda o: -float(o.longest_chain)),
    (OptionKind.BEST_LOCATION, lambda o: o.location_match),
)


def rank(
    pool: SwapPool, matrix: CostMatrix, candidates: Iterable[Assignment]
) -> tuple[SwapOption, ...]:
    """Up to three options, each best at something the others are not."""
    options: list[SwapOption] = []
    seen: set[tuple] = set()
    for assignment in candidates:
        option = _build_option(pool, matrix, assignment)
        if option is None or _signature(option) in seen:
            continue
        seen.add(_signature(option))
        options.append(option)

    chosen: list[SwapOption] = []
    taken: set[tuple] = set()
    for kind, axis in _AXES:
        remaining = [o for o in options if _signature(o) not in taken]
        if not remaining:
            break

        winner = max(remaining, key=lambda o: (axis(o), o.mean_match, -o.longest_chain))

        # Only award a label the option actually beats the others on,
        # otherwise "fastest" can name a longer chain than the option
        # listed above it. Fewer options is better than a wrong label.
        if chosen and axis(winner) <= max(axis(o) for o in chosen):
            continue

        taken.add(_signature(winner))
        chosen.append(winner.with_kind(kind))

    return tuple(chosen)
