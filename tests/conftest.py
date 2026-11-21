"""
tests/conftest.py
Shared pytest fixtures for Gaia civilization simulation tests.
Provides real local SQLite and DuckDB fixtures — never mocks database calls.
"""

import sqlite3
from pathlib import Path

import pytest

from sim_core.persistence.db import init_db


@pytest.fixture
def repo_root() -> Path:
    """Returns the absolute Path to the repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Provides an isolated directory for testing file modifications."""
    return tmp_path


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Initializes and returns the path to a real local SQLite test database."""
    db_file = tmp_path / "test_civilization.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def db_session(test_db_path: Path):
    """Provides an active sqlite3 connection to the real local test database."""
    conn = sqlite3.connect(test_db_path)
    try:
        yield conn
    finally:
        conn.close()
