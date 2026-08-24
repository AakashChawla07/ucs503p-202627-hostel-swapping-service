"""Keep the suite hermetic.

Tests must never reach a real database: it makes them slow and they
would fail on any machine without credentials. conftest is imported
before any test module, so neutralising here also covers module-level
code that runs at collection time.
"""

import os
import pathlib

import pytest

from hostelswap import db

_NO_ENV_FILE = pathlib.Path("does-not-exist.env")

os.environ.pop("DATABASE_URL", None)
db.ENV_FILE = _NO_ENV_FILE


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "ENV_FILE", _NO_ENV_FILE)
