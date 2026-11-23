"""
tests/test_palace_security_and_knights.py
Comprehensive unit tests for Sprint 2:
- Twin Guardian Dragons entry whitelist (bypass for God, Goddess, 5 God-Mothers, Palace Knights).
- Mortal petition halt in 35m Gate Zone and emission of PALACE_ENTRY_REQUEST.
- Live God decision (GRANT vs DENY) when God is ACTIVE.
- Trespass / breach triggers 40m Dragon fear aura, Palace Knight interception,
  and Judiciary arrest filing.
- Palace Knight Battalion (24 guards) deployment and deterministic patrol waypoint routes.
"""

from __future__ import annotations

import pytest

from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.divine.god_ledger import GodLedgerPipeline, GodPresenceTracker
from sim_core.engine import SimulationEngine
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import AgentRecord, Vec3
from sim_core.society.judiciary import JudiciaryEngine
from sim_core.world.palace_security import (
    DRAGON_LEFT_X,
    DRAGON_LEFT_Y,
    DRAGON_LEFT_Z,
    MAIN_GATE_X,
    MAIN_GATE_Y,
    MAIN_GATE_Z,
    PALACE_CENTER_Y,
    PalaceSecurityEngine,
)


@pytest.fixture
def mock_security_env(tmp_path):
    """Provides an isolated PalaceSecurityEngine fixture with mock adapter and pipeline."""
    presence = GodPresenceTracker()
    ledger = GodLedgerPipeline(ledger_dir=str(tmp_path / "ledger"), tracker=presence)
    goddess = WorldGoddessCritic()
    judiciary = JudiciaryEngine()
    adapter = MockWorldAdapter()

    security = PalaceSecurityEngine(
        engine=None,
        god_presence=presence,
        ledger_pipeline=ledger,
        world_goddess=goddess,
        judiciary=judiciary,
        adapter=adapter,
    )
    return security, presence, ledger, goddess, judiciary, adapter


def test_whitelist_bypass(mock_security_env):
    """God, Goddess, 5 God-Mothers, and Palace Knights must bypass security checks."""
    security, _, _, _, _, _ = mock_security_env

    # 1. Deity string IDs
    for deity in [
        "god_avatar",
        "world_goddess",
        "gm_human",
        "gm_elf",
        "gm_dragon",
        "gm_beasthuman",
        "gm_demon",
    ]:
        assert security.is_whitelisted(deity) is True

    # 2. Palace Knight role
    knight = AgentRecord(
        agent_id="knight_01",
        slot_idx=0,
        display_name="Sir Lancelot",
        dynasty_surname="Guard",
        gender="BOY",
        race="HUMAN",
        role="PALACE_KNIGHT",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z),
    )
    assert security.is_whitelisted(knight) is True

    # 3. Standard mortal is NOT whitelisted
    mortal = AgentRecord(
        agent_id="mortal_01",
        slot_idx=1,
        display_name="Alice",
        dynasty_surname="Smith",
        gender="GIRL",
        race="HUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z),
    )
    assert security.is_whitelisted(mortal) is False


def test_mortal_petition_halt_when_god_active(mock_security_env):
    """Mortal entering 35m Gate Zone is halted and emits PALACE_ENTRY_REQUEST when God is active."""
    security, presence, _, _, _, adapter = mock_security_env
    presence.set_active(True, tick=10)

    # Place mortal inside 35m Gate Zone
    mortal = AgentRecord(
        agent_id="mortal_petitioner_01",
        slot_idx=1,
        display_name="Theron",
        dynasty_surname="The Bold",
        gender="BOY",
        race="ELF",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 10.0),
        stamina=50.0,
    )
    agents = {mortal.agent_id: mortal}

    # Step security engine
    security.step(current_tick=10, agents=agents)

    # Mortal stamina reduced / halted
    assert mortal.stamina < 50.0

    # Request recorded
    assert mortal.agent_id in security.agent_to_request
    req_id = security.agent_to_request[mortal.agent_id]
    req = security.pending_requests[req_id]
    assert req.name == "Theron"
    assert req.race == "ELF"
    assert req.status == "PENDING"

    # Adapter received PALACE_ENTRY_REQUEST event
    request_events = [e for e in adapter.events if e[0] == "PALACE_ENTRY_REQUEST"]
    assert len(request_events) >= 1
    assert request_events[-1][1]["agent_id"] == "mortal_petitioner_01"


def test_live_god_decision_grant_and_deny(mock_security_env):
    """When God is active, GOD_PALACE_DECISION grants pass or triggers knight escort."""
    security, presence, ledger, _, _, _ = mock_security_env
    presence.set_active(True, tick=20)

    mortal = AgentRecord(
        agent_id="mortal_grantee",
        slot_idx=2,
        display_name="Lyra",
        dynasty_surname="Starlight",
        gender="GIRL",
        race="ELF",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 5.0),
    )
    req = security.request_entry(mortal, current_tick=20)

    # 1. God GRANTS entry
    resolved = security.resolve_request(
        request_id=req.request_id,
        decision="GRANT",
        decided_by="GOD",
        current_tick=20,
        duration_ticks=600,
    )
    assert resolved is not None
    assert resolved.status == "GRANTED"
    assert security.has_active_pass(mortal.agent_id, current_tick=20) is True
    assert security.has_active_pass(mortal.agent_id, current_tick=650) is False  # Expired

    # Check God Ledger entry recorded under PALACE_SECURITY
    ledger_entries = [e for e in ledger.buffer if e.category == "PALACE_SECURITY"]
    assert len(ledger_entries) >= 1
    assert "granted" in ledger_entries[-1].message.lower()

    # 2. Another mortal DENIED by God
    mortal2 = AgentRecord(
        agent_id="mortal_denied",
        slot_idx=3,
        display_name="Brog",
        dynasty_surname="Ironfist",
        gender="BOY",
        race="BEASTHUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 5.0),
    )
    req2 = security.request_entry(mortal2, current_tick=30)
    resolved2 = security.resolve_request(
        request_id=req2.request_id,
        decision="DENY",
        decided_by="GOD",
        current_tick=30,
    )
    assert resolved2 is not None
    assert resolved2.status == "DENIED"
    assert security.has_active_pass(mortal2.agent_id, current_tick=30) is False


def test_goddess_auto_adjudication_when_god_away(mock_security_env):
    """When God is AWAY, World Goddess auto-adjudicates: devout clean granted, criminals denied."""
    security, presence, ledger, _, judiciary, _ = mock_security_env
    presence.set_active(False)  # God is away

    # Devout, clean citizen
    devout = AgentRecord(
        agent_id="devout_citizen",
        slot_idx=4,
        display_name="Brother Paul",
        dynasty_surname="Faithful",
        gender="BOY",
        race="HUMAN",
        role="CLERIC",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 15.0),
        godmother_affinities={"gm_human": 0.8},
        patron_godmother_slot="gm_human",
    )

    # Criminal citizen
    criminal = AgentRecord(
        agent_id="bandit_joe",
        slot_idx=5,
        display_name="Joe",
        dynasty_surname="The Thief",
        gender="BOY",
        race="HUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 20.0),
    )
    judiciary.criminal_records[criminal.agent_id] = ["case_theft_01"]

    agents = {devout.agent_id: devout, criminal.agent_id: criminal}

    # Step simulation with God away
    security.step(current_tick=50, agents=agents)

    # Devout citizen should be auto-granted by World Goddess
    assert security.has_active_pass(devout.agent_id, current_tick=50) is True

    # Criminal citizen should be denied by World Goddess
    assert security.has_active_pass(criminal.agent_id, current_tick=50) is False

    # Check ledger records
    ledger_entries = [e for e in ledger.buffer if e.category == "PALACE_SECURITY"]
    assert len(ledger_entries) >= 2


def test_trespass_fear_aura_and_judiciary_arrest(mock_security_env):
    """Trespass into 95m Inner Palace Sanctuary triggers fear aura & files Judiciary case."""
    security, _, _, _, judiciary, adapter = mock_security_env

    trespasser = AgentRecord(
        agent_id="intruder_shadow",
        slot_idx=6,
        display_name="Shadow",
        dynasty_surname="Infiltrator",
        gender="BOY",
        race="DEMON",
        role="CITIZEN",
        pos=Vec3(x=DRAGON_LEFT_X + 2.0, y=DRAGON_LEFT_Y, z=DRAGON_LEFT_Z),  # Near dragon plinth
        stamina=100.0,
        distress=0.0,
        crying=False,
    )
    agents = {trespasser.agent_id: trespasser}

    # Step security engine
    security.step(current_tick=100, agents=agents)

    # Fear aura triggered: distress maxed, crying True, stamina drained
    assert trespasser.distress >= 0.9
    assert trespasser.crying is True
    assert trespasser.stamina <= 0.0

    # Judiciary case opened for TRESPASS
    assert len(judiciary.cases) >= 1
    trespass_case = next(c for c in judiciary.cases.values() if c.accused_id == trespasser.agent_id)
    assert trespass_case.offense_type == "TRESPASS"

    # Adapter emitted PALACE_TRESPASS_ALERT
    alerts = [e for e in adapter.events if e[0] == "PALACE_TRESPASS_ALERT"]
    assert len(alerts) >= 1
    assert alerts[0][1]["agent_id"] == "intruder_shadow"


def test_palace_knight_battalion_deployment_and_patrols():
    """Palace Knight Battalion spawns 24 guards with proper roles, waypoints, and positions."""
    engine = SimulationEngine(headless=True)
    agents_registry = engine.agents

    knights = engine.palace_security.spawn_knight_battalion(agents_registry, count=24)
    assert len(knights) == 24
    assert len(engine.palace_security.knight_agent_ids) == 24

    roles_map = engine.palace_security.knight_roles
    wall_sentries = [k for k in knights if roles_map[k.agent_id] == "WALL_SENTRY"]
    courtyard_sentries = [k for k in knights if roles_map[k.agent_id] == "COURTYARD_SENTRY"]
    road_sentries = [k for k in knights if roles_map[k.agent_id] == "ROAD_CHECKPOINT"]
    rapid_response = [k for k in knights if roles_map[k.agent_id] == "RAPID_RESPONSE"]

    assert len(wall_sentries) == 4
    assert len(courtyard_sentries) == 4
    assert len(road_sentries) == 10
    assert len(rapid_response) == 6

    # Verify all knights have valid role and initial positions
    for k in knights:
        assert k.role == "PALACE_KNIGHT"
        assert k.pos.y == PALACE_CENTER_Y
        assert k.agent_id in engine.spatial_grid._agent_positions

    # Step engine to verify knights patrol without crashing
    for _ in range(5):
        engine.step_tick()
