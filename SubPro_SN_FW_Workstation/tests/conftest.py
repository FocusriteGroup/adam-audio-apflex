"""
conftest.py – shared pytest fixtures for Sub-Pro SN/FW Workstation tests.

Provides an isolated, in-memory (or temp-file) Database instance per test.
"""
import sys
import pathlib
import tempfile
import pytest

# Make parent repo importable (oca/, services/, etc.)
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Make this project importable
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture
def db(tmp_path):
    """Return a fresh Database backed by a temporary file."""
    from app.db.database import Database
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_gs(db):
    """Database pre-populated with one golden sample per variant."""
    db.add_golden_sample("A8S",  "CIGS00001", "GS A8S unit 1")
    db.add_golden_sample("A8S",  "CIGS00002", "GS A8S unit 2")
    db.add_golden_sample("A10S", "CJGS00001", "GS A10S unit 1")
    return db
