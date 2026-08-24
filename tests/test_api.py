from fastapi.testclient import TestClient

from hostelswap.api import app

client = TestClient(app)
DEMO = client.get("/api/demo").json()


def test_page_loads():
    assert client.get("/").status_code == 200


def test_every_student_appears_in_the_master_table():
    assert len(DEMO["students"]) == 30
    assert all(row["name"] and row["room"] for row in DEMO["students"])


def test_the_swap_raises_cohort_satisfaction():
    assert DEMO["after"] > DEMO["before"]


def test_nobody_is_left_worse_off():
    assert DEMO["worseOff"] == 0
    assert all(row["after"] >= row["before"] for row in DEMO["students"])


def test_a_student_who_moves_gets_a_different_room():
    movers = [row for row in DEMO["students"] if row["newRoom"]]

    assert movers
    assert all(row["newRoom"] != row["room"] for row in movers)


def test_students_who_stay_keep_their_score():
    for row in DEMO["students"]:
        if row["newRoom"] is None:
            assert row["after"] == row["before"]


def test_every_chain_member_is_a_student_in_the_table():
    names = {row["name"] for row in DEMO["students"]}

    for chain in DEMO["chains"]:
        assert len(chain) >= 2
        assert {move["name"] for move in chain} <= names


def test_no_student_is_in_two_chains():
    members = [move["name"] for chain in DEMO["chains"] for move in chain]

    assert len(members) == len(set(members))


def test_a_cycle_closes_on_the_room_it_started_from():
    for chain in DEMO["chains"]:
        assert chain[-1]["to"] == chain[0]["from"]


def test_rooms_are_plain_numbers_with_no_bed_suffix():
    for row in DEMO["students"]:
        assert row["room"].count("-") == 1
        if row["newRoom"]:
            assert row["newRoom"].count("-") == 1


def test_each_student_holds_a_room_of_their_own():
    rooms = [row["room"] for row in DEMO["students"]]

    assert len(rooms) == len(set(rooms))
