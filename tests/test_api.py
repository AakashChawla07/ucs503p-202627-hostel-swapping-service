from fastapi.testclient import TestClient

from hostelswap.api import app

client = TestClient(app)


def test_page_loads():
    assert client.get("/").status_code == 200


def test_options_returns_three_kinds():
    body = client.get("/api/options?students=12&seed=23&k=30").json()

    assert [o["kind"] for o in body] == ["best_overall", "fastest", "best_location"]


def test_each_move_names_a_source_and_a_destination():
    body = client.get("/api/options?students=12&seed=23&k=30").json()

    for move in body[0]["chains"][0]:
        assert move["from"] != move["to"]
        assert 0 <= move["match"] <= 100
