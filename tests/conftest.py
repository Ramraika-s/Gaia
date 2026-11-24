"""
tests/conftest.py
Shared pytest fixtures and factory helpers for Gaia civilization simulation tests.
Provides real local SQLite fixtures, isolated paths, headless simulation engines,
and typed domain factories for agents, buildings, and knowledge entries.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.knowledge.schema import KnowledgeEntry
from sim_core.persistence.db import init_db
from sim_core.schemas import (
    AgentRecord,
    AgentRole,
    BuildingRecord,
    BuildingType,
    Gender,
    RaceId,
    RacialStyle,
    Stage,
    Vec3,
    WorldLibraryEntry,
)


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
def db_session(test_db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Provides an active sqlite3 connection to the real local test database."""
    conn = sqlite3.connect(test_db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def isolated_engine_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Returns isolated (db_path, checkpoints_dir, god_ledger_dir) under tmp_path."""
    db_path = tmp_path / "civilization.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"
    return db_path, checkpoints_dir, god_ledger_dir


@pytest.fixture
def engine(isolated_engine_paths: tuple[Path, Path, Path]) -> SimulationEngine:
    """
    Provides a fast, clean, headless SimulationEngine backed by isolated paths
    and MockWorldAdapter.
    """
    db_path, checkpoints_dir, god_ledger_dir = isolated_engine_paths
    return SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        adapter=MockWorldAdapter(),
        headless=True,
    )


# ---------------------------------------------------------------------------
# Factory Helpers
# ---------------------------------------------------------------------------


def make_agent(
    agent_id: str = "agent_test_01",
    slot_idx: int = 0,
    race: RaceId = "HUMAN",
    gender: Gender = "BOY",
    stage: Stage = "ADULT",
    display_name: str = "Aiden",
    dynasty_surname: str = "Vanguard",
    credits: float = 25.0,
    pos: Vec3 | None = None,
    role: AgentRole = "CITIZEN",
    profession: str = "FARMER",
    profession_level: int = 1,
    alive: bool = True,
    **kwargs: Any,
) -> AgentRecord:
    """Factory helper creating an AgentRecord with realistic simulation defaults."""
    return AgentRecord(
        agent_id=agent_id,
        slot_idx=slot_idx,
        race=race,
        gender=gender,
        stage=stage,
        display_name=display_name,
        dynasty_surname=dynasty_surname,
        credits=credits,
        pos=pos or Vec3(x=0.0, y=10.0, z=0.0),
        role=role,
        profession=profession,
        profession_level=profession_level,
        alive=alive,
        **kwargs,
    )


def make_building(
    building_id: str = "bld_test_01",
    city_id: str = "aurelia",
    building_type: BuildingType = "HOUSE_T1_COTTAGE",
    racial_style: RacialStyle = "HUMAN",
    x: float = 355.0,
    y: float = 18.0,
    z: float = 1090.0,
    rotation_y: float = 0.0,
    parcel_x: int = 22,
    parcel_z: int = 68,
    footprint_radius: float = 8.0,
    for_sale: bool = False,
    sale_price: float = 100.0,
    owner_id: str | None = None,
    owner_name: str | None = None,
    is_frontier: bool = False,
    **kwargs: Any,
) -> BuildingRecord:
    """Factory helper creating a BuildingRecord with valid geometry."""
    return BuildingRecord(
        building_id=building_id,
        city_id=city_id,
        building_type=building_type,
        racial_style=racial_style,
        x=x,
        y=y,
        z=z,
        rotation_y=rotation_y,
        parcel_x=parcel_x,
        parcel_z=parcel_z,
        footprint_radius=footprint_radius,
        for_sale=for_sale,
        sale_price=sale_price,
        owner_id=owner_id,
        owner_name=owner_name,
        is_frontier=is_frontier,
        **kwargs,
    )


def make_knowledge_entry(
    entry_id: str = "tactics_sample_001",
    subject: str = "tactics_and_warfare",
    target_section: str = "military_tactics",
    fact_key: str = "tactics_and_warfare.siege.murder_holes",
    title: str = "Murder Holes and Transverse Gate Defense",
    summary: str = "Engineering overhead apertures to drop heavy stones onto siege crews.",
    body: str = (
        "When enemy forces breach outer wooden gates, they enter an enclosed vaulted passageway "
        "before the inner portcullis. Overhead ceiling slots allow defenders to drop heavy stones."
    ),
    author: str = "Captain Vane",
    era_tier: int = 1,
    tags: list[str] | None = None,
    mechanical_effects: dict[str, float] | None = None,
    supersedes: list[str] | None = None,
    distinct_from: list[str] | None = None,
) -> dict[str, Any]:
    """Factory helper returning a validated KnowledgeEntry dictionary."""
    data = {
        "entry_id": entry_id,
        "subject": subject,
        "target_section": target_section,
        "fact_key": fact_key,
        "title": title,
        "summary": summary,
        "body": body,
        "author": author,
        "author_type": "MORTAL",
        "era_tier": era_tier,
        "tags": tags or ["fortification", "gate_defense"],
        "prerequisites": [],
        "mechanical_effects": mechanical_effects or {"defense_bonus": 0.15},
        "supersedes": supersedes or [],
        "distinct_from": distinct_from or [],
    }
    # Validate against schema
    KnowledgeEntry.model_validate(data)
    return data


def make_world_library_entry(
    entry_id: str = "lib_sample_001",
    topic: str = "TACTICS",
    title: str = "Phalanx Tactics",
    summary: str = "Interlocking pavise shield formations.",
    author_id: str = "palace_general",
    author_proficiency: float = 0.9,
    skill_bonus: float = 0.10,
    created_tick: int = 0,
    mechanical_effects: dict[str, float] | None = None,
    body: str = "Form line, interlock shields, hold advance.",
    **kwargs: Any,
) -> WorldLibraryEntry:
    """Factory helper creating a WorldLibraryEntry instance."""
    return WorldLibraryEntry(
        entry_id=entry_id,
        topic=topic,
        title=title,
        summary=summary,
        author_id=author_id,
        author_proficiency=author_proficiency,
        skill_bonus=skill_bonus,
        created_tick=created_tick,
        mechanical_effects=mechanical_effects or {"defense": 0.25},
        body=body,
        **kwargs,
    )
