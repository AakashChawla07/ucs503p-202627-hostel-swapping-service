import pytest

from hostelswap import db
from hostelswap.api import current_pool
from hostelswap.domain.models import Direction
from hostelswap.domain.preferences import Criterion


def test_no_database_configured_means_no_dsn():
    assert db.dsn() is None


def test_an_empty_variable_is_treated_as_unset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")

    assert db.dsn() is None


def test_the_environment_wins_over_the_env_file(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-environment")

    assert db.dsn() == "postgresql://from-environment"


def test_the_app_falls_back_to_the_fixed_table():
    pool, source = current_pool()

    assert source == "hardcoded table"
    assert len(pool.students) == 30


@pytest.mark.parametrize(
    "criterion,raw,expected",
    [
        (Criterion.FLOOR, "4", 4),
        (Criterion.ROOM_TYPE, "2SAC", "2SAC"),
        (Criterion.DIRECTION, "N", Direction.N),
        (Criterion.WASHROOM, "attached", "attached"),
        (Criterion.WASHROOM, "common", "common"),
        (Criterion.ROOM, "A-433", "A-433"),
    ],
)
def test_stored_text_is_converted_back_to_its_type(criterion, raw, expected):
    # Preferences are stored as text in Postgres; a floor must come back
    # as an int or scoring silently never matches.
    assert db._value(criterion, raw) == expected
