from hostelswap.domain.cycles import decompose
from hostelswap.domain.solver import Assignment
from tests.factories import make_pool, room

ROOMS = [
    room("H7-101", hostel="H7"),
    room("H9-201", hostel="H9"),
    room("H11-301", hostel="H11"),
    room("H13-401", hostel="H13"),
]
HELD = {
    "s1": "H7-101-a",
    "s2": "H9-201-a",
    "s3": "H11-301-a",
    "s4": "H13-401-a",
}


def pool(students=("s1", "s2", "s3", "s4")):
    return make_pool(ROOMS, {s: HELD[s] for s in students})


def assignment(mapping):
    return Assignment(slot_by_student=mapping, cost=0.0)


def test_two_way_swap():
    chains = decompose(
        pool(("s1", "s2")),
        assignment({"s1": HELD["s2"], "s2": HELD["s1"]}),
    )

    assert len(chains) == 1
    assert chains[0].students == ("s1", "s2")
    assert chains[0].length == 2


def test_three_way_rotation():
    chains = decompose(
        pool(("s1", "s2", "s3")),
        assignment({"s1": HELD["s2"], "s2": HELD["s3"], "s3": HELD["s1"]}),
    )

    assert len(chains) == 1
    assert chains[0].students == ("s1", "s2", "s3")


def test_no_moves_no_chains():
    chains = decompose(
        pool(("s1", "s2", "s3")),
        assignment({"s1": HELD["s1"], "s2": HELD["s2"], "s3": HELD["s3"]}),
    )

    assert chains == ()


def test_fixed_point_excluded():
    chains = decompose(
        pool(("s1", "s2", "s3")),
        assignment({"s1": HELD["s2"], "s2": HELD["s1"], "s3": HELD["s3"]}),
    )

    assert len(chains) == 1
    assert chains[0].students == ("s1", "s2")


def test_disjoint_swaps_split():
    chains = decompose(
        pool(),
        assignment(
            {
                "s1": HELD["s2"],
                "s2": HELD["s1"],
                "s3": HELD["s4"],
                "s4": HELD["s3"],
            }
        ),
    )

    assert len(chains) == 2
    assert {chain.students for chain in chains} == {("s1", "s2"), ("s3", "s4")}


def test_chains_are_disjoint():
    chains = decompose(
        pool(),
        assignment(
            {
                "s1": HELD["s2"],
                "s2": HELD["s3"],
                "s3": HELD["s4"],
                "s4": HELD["s1"],
            }
        ),
    )

    members = [student for chain in chains for student in chain.students]

    assert len(members) == len(set(members))


def test_cycle_order():
    moves = {"s1": HELD["s2"], "s2": HELD["s3"], "s3": HELD["s1"]}
    swap_pool = pool(("s1", "s2", "s3"))

    chain = decompose(swap_pool, assignment(moves))[0]

    for giver, receiver in zip(chain.students, chain.students[1:] + chain.students[:1]):
        assert moves[giver] == swap_pool.current_slot_id(receiver)
