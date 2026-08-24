from datetime import datetime, timedelta

import pytest

from hostelswap.domain.proposal import (
    InvalidTransition,
    Proposal,
    ProposalStatus,
    Response,
    cancel,
    execute,
    expire_if_due,
    respond,
)

NOW = datetime(2026, 8, 24, 10, 0)
LATER = NOW + timedelta(days=1)


def proposal(status=ProposalStatus.PROPOSED):
    return Proposal.opening(
        id="p1",
        moves=(("s1", "A-101-a", "A-202-a"), ("s2", "A-202-a", "A-101-a")),
        expires_at=LATER,
    ).replace(status=status)


def test_opens_with_everyone_pending():
    p = proposal()

    assert p.status is ProposalStatus.PROPOSED
    assert all(m.response is Response.PENDING for m in p.moves)


def test_one_approval_is_not_enough():
    p = respond(proposal(), "s1", accept=True, now=NOW)

    assert p.status is ProposalStatus.PROPOSED


def test_everyone_approving_moves_it_to_approved():
    p = respond(proposal(), "s1", accept=True, now=NOW)
    p = respond(p, "s2", accept=True, now=NOW)

    assert p.status is ProposalStatus.APPROVED


def test_a_single_rejection_kills_it():
    p = respond(proposal(), "s1", accept=False, now=NOW)

    assert p.status is ProposalStatus.REJECTED


def test_dropping_out_after_others_agreed_still_kills_it():
    p = respond(proposal(), "s1", accept=True, now=NOW)
    p = respond(p, "s2", accept=False, now=NOW)

    assert p.status is ProposalStatus.REJECTED


def test_a_student_outside_the_chain_cannot_respond():
    with pytest.raises(InvalidTransition, match="s9"):
        respond(proposal(), "s9", accept=True, now=NOW)


def test_nobody_may_respond_twice():
    p = respond(proposal(), "s1", accept=True, now=NOW)

    with pytest.raises(InvalidTransition, match="already"):
        respond(p, "s1", accept=True, now=NOW)


def test_it_expires_if_the_deadline_passes_first():
    p = expire_if_due(proposal(), now=LATER + timedelta(seconds=1))

    assert p.status is ProposalStatus.EXPIRED


def test_it_does_not_expire_once_everyone_has_agreed():
    p = respond(proposal(), "s1", accept=True, now=NOW)
    p = respond(p, "s2", accept=True, now=NOW)

    assert expire_if_due(p, now=LATER + timedelta(days=9)).status is ProposalStatus.APPROVED


def test_an_expired_proposal_takes_no_more_responses():
    p = expire_if_due(proposal(), now=LATER + timedelta(seconds=1))

    with pytest.raises(InvalidTransition):
        respond(p, "s1", accept=True, now=LATER)


def test_it_can_be_cancelled_while_still_open():
    assert cancel(proposal()).status is ProposalStatus.CANCELLED


def test_an_executed_swap_cannot_be_cancelled():
    p = proposal(ProposalStatus.EXECUTED)

    with pytest.raises(InvalidTransition):
        cancel(p)


def test_only_an_approved_proposal_executes():
    with pytest.raises(InvalidTransition, match="proposed"):
        execute(proposal(), now=NOW)


def test_executing_emits_one_new_allocation_per_student():
    p, allocations = execute(proposal(ProposalStatus.APPROVED), now=NOW)

    assert p.status is ProposalStatus.EXECUTED
    assert {(a.student_id, a.slot_id) for a in allocations} == {
        ("s1", "A-202-a"),
        ("s2", "A-101-a"),
    }
    assert all(a.effective_from == NOW for a in allocations)


def test_one_chain_collapsing_leaves_the_others_untouched():
    # Chains within an option are disjoint, so they are separate
    # proposals and a drop-out in one cannot reach the other.
    mine = respond(proposal(), "s1", accept=False, now=NOW)
    theirs = Proposal.opening(
        id="p2",
        moves=(("s3", "B-301-a", "B-404-a"), ("s4", "B-404-a", "B-301-a")),
        expires_at=LATER,
    )

    assert mine.status is ProposalStatus.REJECTED
    assert theirs.status is ProposalStatus.PROPOSED
