from hostelswap.domain.pool import SwapPool
from hostelswap.synth.generator import generate_pool


def test_pool_size():
    pool = generate_pool(students=20, seed=1)

    assert isinstance(pool, SwapPool)
    assert len(pool.students) == 20
    assert len(pool.slots) == 20


def test_students_complete():
    pool = generate_pool(students=15, seed=2)

    for student in pool.students:
        assert pool.current_slot_id(student.id)
        assert pool.preferences_of(student.id).preferences


def test_same_seed_same_pool():
    first = generate_pool(students=12, seed=7)
    second = generate_pool(students=12, seed=7)

    assert first.allocations == second.allocations
    assert first.preferences == second.preferences


def test_different_seeds():
    first = generate_pool(students=12, seed=7)
    second = generate_pool(students=12, seed=8)

    assert first.allocations != second.allocations


def test_slots_unique():
    pool = generate_pool(students=25, seed=3)

    held = [pool.current_slot_id(s.id) for s in pool.students]

    assert len(held) == len(set(held))


def test_roommate_not_self():
    pool = generate_pool(students=30, seed=4, roommate_probability=1.0)

    for student in pool.students:
        for preference in pool.preferences_of(student.id).preferences:
            assert preference.value != student.id


def test_no_hard_prefs_by_default():
    pool = generate_pool(students=20, seed=5)

    assert all(
        not p.hard
        for student in pool.students
        for p in pool.preferences_of(student.id).preferences
    )
