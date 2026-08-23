"""The approval workflow for one swap chain.

One proposal is one chain. Chains inside an option are disjoint, so
they execute independently -- which is why a student dropping out of
one chain cannot invalidate any other.

Every transition returns a new proposal. Nothing is mutated, and
executing a swap emits fresh allocation rows rather than editing old
ones, matching the append-only allocation history.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .models import Allocation


class ProposalStatus(Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Response(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


OPEN = ProposalStatus.PROPOSED
LIVE = (ProposalStatus.PROPOSED, ProposalStatus.APPROVED)


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class Move:
    student_id: str
    from_slot_id: str
    to_slot_id: str
    response: Response = Response.PENDING


@dataclass(frozen=True)
class Proposal:
    id: str
    moves: tuple[Move, ...]
    status: ProposalStatus
    expires_at: datetime
    settled_at: datetime | None = None

    @classmethod
    def opening(cls, id: str, moves, expires_at: datetime) -> "Proposal":
        return cls(
            id=id,
            moves=tuple(Move(*move) for move in moves),
            status=ProposalStatus.PROPOSED,
            expires_at=expires_at,
        )

    def replace(self, **changes) -> "Proposal":
        return replace(self, **changes)

    def move_of(self, student_id: str) -> Move:
        for move in self.moves:
            if move.student_id == student_id:
                return move
        raise InvalidTransition(f"{student_id} is not in this chain")


def respond(
    proposal: Proposal, student_id: str, accept: bool, now: datetime
) -> Proposal:
    if proposal.status is not OPEN:
        raise InvalidTransition(f"cannot respond to a {proposal.status.value} proposal")

    move = proposal.move_of(student_id)
    if move.response is not Response.PENDING:
        raise InvalidTransition(f"{student_id} has already responded")

    answer = Response.APPROVED if accept else Response.REJECTED
    moves = tuple(
        replace(m, response=answer) if m.student_id == student_id else m
        for m in proposal.moves
    )

    # One refusal is enough: a cycle only works whole.
    if not accept:
        return proposal.replace(
            moves=moves, status=ProposalStatus.REJECTED, settled_at=now
        )

    if all(m.response is Response.APPROVED for m in moves):
        return proposal.replace(moves=moves, status=ProposalStatus.APPROVED)

    return proposal.replace(moves=moves)


def expire_if_due(proposal: Proposal, now: datetime) -> Proposal:
    """Only a proposal still collecting approvals can expire."""
    if proposal.status is OPEN and now > proposal.expires_at:
        return proposal.replace(status=ProposalStatus.EXPIRED, settled_at=now)
    return proposal


def cancel(proposal: Proposal) -> Proposal:
    if proposal.status not in LIVE:
        raise InvalidTransition(f"cannot cancel a {proposal.status.value} proposal")
    return proposal.replace(status=ProposalStatus.CANCELLED)


def execute(proposal: Proposal, now: datetime) -> tuple[Proposal, tuple[Allocation, ...]]:
    """Emit the new allocation rows for an approved chain."""
    if proposal.status is not ProposalStatus.APPROVED:
        raise InvalidTransition(f"cannot execute a {proposal.status.value} proposal")

    allocations = tuple(
        Allocation(move.student_id, move.to_slot_id, now) for move in proposal.moves
    )
    settled = proposal.replace(status=ProposalStatus.EXECUTED, settled_at=now)
    return settled, allocations
