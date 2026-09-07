"""Orchestrates one swap round: enroll -> prioritise -> lock -> run -> offer -> respond.

This module owns the workflow; it has no SQL of its own (that's `db.py`)
and no matching math of its own (that's `domain/`). It just wires the two
together in the right order and enforces round-state rules like "you can't
change your priorities once the round is locked."
"""

from datetime import datetime, timedelta, timezone
from statistics import fmean

from . import db
from .domain.pipeline import recommend_chains
from .domain.proposal import InvalidTransition, Move, Proposal, ProposalStatus, Response
from .domain.proposal import execute as domain_execute
from .domain.proposal import respond as domain_respond

PROPOSAL_LIFETIME = timedelta(days=3)

# How many chains each student is shown. They overlap by design -- see
# `candidate_chains` -- so more of them means more students with
# something to choose from, and more races for the same rooms.
PER_STUDENT_OPTIONS = 3

# Chains are now recommendations addressed to a student rather than
# hostel-wide plans, so they no longer carry a "best overall"/"fastest"
# label; `chain_no` alone identifies one within a round.
OPTION_KIND = "recommended"


class InvalidRoundState(Exception):
    pass


def open_round(connection_string: str, round_id: str) -> None:
    round_data = _require_round(connection_string, round_id)
    if round_data["status"] != "draft":
        raise InvalidRoundState(f"round is {round_data['status']}, expected draft")
    db.set_round_status(connection_string, round_id, "open")


def enroll(connection_string: str, round_id: str, student_id: str, enrolled: bool) -> None:
    round_data = _require_round(connection_string, round_id)
    if round_data["status"] != "open":
        raise InvalidRoundState("registration is closed for this round")
    db.set_enrollment(connection_string, round_id, student_id, enrolled)


def save_priorities(
    connection_string: str, round_id: str, student_id: str, priorities: list[dict]
) -> None:
    round_data = _require_round(connection_string, round_id)
    if round_data["status"] != "open":
        raise InvalidRoundState("priorities are locked once the round is running")
    db.replace_preferences(connection_string, student_id, round_id, priorities)


def lock_and_run(connection_string: str, round_id: str, k: int = 50) -> dict:
    round_data = _require_round(connection_string, round_id)
    if round_data["status"] != "open":
        raise InvalidRoundState(f"round must be open to run, is {round_data['status']}")

    db.set_round_status(connection_string, round_id, "locked", locked_at=datetime.now(timezone.utc))
    db.set_round_status(connection_string, round_id, "running")

    round_pool = db.load_round_pool(connection_string, round_id)
    # Every chain a student could reasonably be offered, not the single
    # best plan for the hostel: the students who are not in that one plan
    # would otherwise be told there is nothing for them when there is.
    offers = recommend_chains(round_pool.pool, k, PER_STUDENT_OPTIONS)

    rows = [
        {
            "kind": OPTION_KIND,
            "chain_no": chain_no,
            "student_id": round_pool.student_uuid[student_id],
            "from_slot_id": round_pool.slot_uuid[offer.outcomes[student_id].from_slot_id],
            "to_slot_id": round_pool.slot_uuid[offer.outcomes[student_id].to_slot_id],
            "match_value": offer.outcomes[student_id].match.value,
        }
        for chain_no, offer in enumerate(offers)
        for student_id in offer.students
    ]

    db.clear_chain_options(connection_string, round_id)
    if rows:
        db.insert_chain_options(connection_string, round_id, rows)

    db.set_round_status(
        connection_string, round_id, "completed", completed_at=datetime.now(timezone.utc)
    )
    return {
        "roundId": round_id,
        "options": len(offers),
        "chains": len({(r["kind"], r["chain_no"]) for r in rows}),
    }


def offer_chain(
    connection_string: str, round_id: str, student_roll_no: str, option_kind: str, chain_no: int
) -> str:
    round_data = _require_round(connection_string, round_id)
    if round_data["status"] != "completed":
        raise InvalidRoundState("results are not ready yet")

    chains = db.fetch_chain_options(connection_string, round_id)
    chain = next(
        (c for c in chains if c["optionKind"] == option_kind and c["chainNo"] == chain_no), None
    )
    if chain is None:
        raise ValueError("no such chain option")
    members = chain["members"]
    if student_roll_no not in {m["rollNo"] for m in members}:
        raise PermissionError("you are not part of this chain")

    mean_match = fmean(m["match"] for m in members) / 100
    expires_at = datetime.now(timezone.utc) + PROPOSAL_LIFETIME
    insert_members = [
        {
            "studentId": m["studentId"],
            "rollNo": m["rollNo"],
            "fromSlotId": m["fromSlotId"],
            "toSlotId": m["toSlotId"],
            "matchValue": m["match"] / 100,
        }
        for m in members
    ]
    return db.insert_proposal(
        connection_string, round_id, option_kind, mean_match, len(members),
        expires_at, insert_members, offering_roll_no=student_roll_no,
    )


def respond(connection_string: str, proposal_id: str, student_roll_no: str, accept: bool) -> dict:
    now = datetime.now(timezone.utc)
    data = db.fetch_proposal(connection_string, proposal_id)
    if data is None:
        raise ValueError(f"no such proposal: {proposal_id}")

    roll_uuid = {m["rollNo"]: m["studentId"] for m in data["members"]}
    moves = tuple(
        Move(m["rollNo"], m["fromSlotId"], m["toSlotId"], Response(m["approval"]))
        for m in data["members"]
    )
    current = Proposal(
        id=data["id"], moves=moves, status=ProposalStatus(data["status"]),
        expires_at=data["expiresAt"], settled_at=data["settledAt"],
    )
    try:
        updated = domain_respond(current, student_roll_no, accept, now)
    except InvalidTransition as exc:
        # Not a member, already responded, or the proposal already
        # settled -- all client mistakes (a stale page, a double click),
        # not server errors.
        raise InvalidRoundState(str(exc)) from exc

    if updated.status is ProposalStatus.REJECTED:
        # One refusal voids the whole chain; free every member so they can
        # join a different proposal, not just the one who refused.
        approvals = {uuid: "rejected" for uuid in roll_uuid.values()}
        db.update_proposal(connection_string, proposal_id, "rejected", approvals, settled=True)
        return {"status": "rejected"}

    if updated.status is ProposalStatus.APPROVED:
        executed, allocations = domain_execute(updated, now)
        approvals = {roll_uuid[m.student_id]: "approved" for m in executed.moves}
        db.update_proposal(connection_string, proposal_id, "executed", approvals, settled=True)
        db.insert_allocations(
            connection_string,
            [(roll_uuid[a.student_id], a.slot_id, a.effective_from) for a in allocations],
        )
        return {"status": "executed"}

    approvals = {roll_uuid[m.student_id]: m.response.value for m in updated.moves}
    db.update_proposal(connection_string, proposal_id, "proposed", approvals, settled=False)
    return {"status": "proposed"}


def _require_round(connection_string: str, round_id: str) -> dict:
    round_data = db.fetch_round(connection_string, round_id)
    if round_data is None:
        raise ValueError(f"no such round: {round_id}")
    return round_data
