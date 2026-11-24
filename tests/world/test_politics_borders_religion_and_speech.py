# tests/world/test_politics_borders_religion_and_speech.py
from __future__ import annotations

from pathlib import Path
from typing import cast

from sim_core.brains.personality import PersonalityVector
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import (
    AgentRecord,
    DeitySlot,
    SettlementRecord,
    Vec3,
    WorldLibraryEntry,
)
from sim_core.society.borders import BorderManager
from sim_core.society.politics import PoliticalEngine, Polity
from sim_core.society.religion import (
    ReligionManager,
    get_agent_devotion,
    set_agent_devotion,
)


def test_territorial_borders_appeals_and_neutral_free_cities() -> None:
    """
    Verifies territorial borders & appeals:
    - Village appealing for TOWN succeeds when criteria met and fails on border overlap.
    - Multi-racial City (>=2 races at >=15%) wins NEUTRAL_FREE_CITY (war_exempt = True).
    - Neutral Free City is barred from declaring offensive war.
    """
    bm = BorderManager()
    pe = PoliticalEngine()

    parcels_a = [f"{x}_{z}" for x in range(4) for z in range(4)]
    bm.register_settlement_border("village_a", parcels_a)

    parcels_b_overlapping = [f"{x}_{z}" for x in range(2, 6) for z in range(2, 6)]
    ok, reason = bm.evaluate_settlement_appeal(
        settlement_id="village_b",
        appeal_kind="TIER_UPGRADE",
        current_tier="VILLAGE",
        requested_tier="TOWN",
        living_pop=60,
        claimed_parcels=parcels_b_overlapping,
        treasury_credits=500.0,
    )
    assert not ok
    assert "overlaps" in reason

    parcels_b_clean = [f"{x}_{z}" for x in range(10, 14) for z in range(10, 14)]
    ok, reason = bm.evaluate_settlement_appeal(
        settlement_id="village_b",
        appeal_kind="TIER_UPGRADE",
        current_tier="VILLAGE",
        requested_tier="TOWN",
        living_pop=60,
        claimed_parcels=parcels_b_clean,
        treasury_credits=500.0,
    )
    assert ok
    assert "TOWN approved" in reason

    demographics_multiracial = {"HUMAN": 120, "ELF": 105, "DRAGON": 75}
    total_pop = sum(demographics_multiracial.values())

    ok, reason = bm.evaluate_settlement_appeal(
        settlement_id="city_crossroads",
        appeal_kind="NEUTRAL_FREE_CITY",
        current_tier="CITY",
        requested_tier=None,
        living_pop=total_pop,
        claimed_parcels=[],
        treasury_credits=2000.0,
        demographics=demographics_multiracial,
    )
    assert ok
    assert "Neutral Free City approved" in reason

    free_city = Polity(
        settlement_id="city_crossroads",
        name="Crossroads Free City",
        tier="CITY",
        is_neutral_free_city=True,
    )
    pe.register_polity(free_city)

    rival_nation = Polity(
        settlement_id="nation_iron",
        name="Iron Empire",
        tier="NATION",
    )
    pe.register_polity(rival_nation)

    ok, msg = pe.declare_war("city_crossroads", "nation_iron")
    assert not ok
    assert "Neutral Free Cities cannot declare offensive war" in msg


def test_polities_and_borders(tmp_path: Path) -> None:
    """Verifies all 5 Ring 1 cities and emergent villages are registered."""
    engine = SimulationEngine(
        db_path=tmp_path / "civ_borders.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    expected_cities = {"sylvanor", "aurelia", "fenris_hold", "malakor", "drakonis_spire"}
    assert set(engine.political_engine.polities.keys()) == expected_cities

    all_city_parcels: set[str] = set()
    for cid in expected_cities:
        p = engine.political_engine.polities[cid]
        assert p.tier == "CITY"
        assert cid in engine.border_mgr.settlement_borders
        city_border = engine.border_mgr.settlement_borders[cid]
        assert len(city_border) >= 48
        assert all_city_parcels.isdisjoint(city_border)
        all_city_parcels.update(city_border)

    new_village = SettlementRecord(
        settlement_id="village_frontier_99",
        name="Frontier Hold",
        tier="VILLAGE",
        founder_id="founder_1",
        center_pos=Vec3(x=1800.0, y=14.0, z=1800.0),
        treasury_credits=0.0,
        founded_tick=50,
    )
    ok = engine.border_mgr.register_settlement(new_village)
    assert ok is True
    assert "village_frontier_99" in engine.border_mgr.settlement_borders


def test_dynamic_faith_intent_scaled_gains_and_inactivity_decay() -> None:
    """Verifies prayer intents, direct-to-God prohibition, inactivity decay, and altar."""
    rm = ReligionManager()

    agent = AgentRecord(
        agent_id="mortal_1",
        slot_idx=0,
        display_name="Devout John",
        dynasty_surname="Faithful",
        gender="BOY",
        stage="ADULT",
        traits={"faith_devotion": 0.20},
    )
    ok, reason, _ = rm.pray(
        agent,
        target_deity_slot=cast(DeitySlot, "GOD"),
        intent="EARNEST_VOLUNTARY",
        current_tick=10,
    )
    assert not ok
    assert "FORBIDDEN" in reason

    agent_earnest = AgentRecord(
        agent_id="mortal_2",
        slot_idx=1,
        display_name="Mary",
        dynasty_surname="Grace",
        gender="GIRL",
        stage="ADULT",
        traits={"faith_devotion": 0.20},
    )
    agent_obligation = AgentRecord(
        agent_id="mortal_3",
        slot_idx=2,
        display_name="Luke",
        dynasty_surname="Duty",
        gender="BOY",
        stage="ADULT",
        traits={"faith_devotion": 0.20},
    )

    rm.pray(agent_earnest, "gm_human", "EARNEST_VOLUNTARY", current_tick=10)
    rm.pray(agent_obligation, "gm_human", "PARENT_DIRECTED", current_tick=10)
    assert agent_earnest.traits["faith_devotion"] > agent_obligation.traits["faith_devotion"]

    agent_earnest.last_prayer_tick = 100
    decay_tick = 100 + (2 * TICKS_PER_GAME_DAY) + 1000

    old_faith = agent_earnest.traits["faith_devotion"]
    rm.apply_inactivity_decay(agent_earnest, current_tick=decay_tick)
    assert agent_earnest.traits["faith_devotion"] < old_faith

    congregation: list[AgentRecord] = []
    for i in range(10):
        congregation.append(
            AgentRecord(
                agent_id=f"worshipper_{i}",
                slot_idx=i,
                display_name=f"Worshipper_{i}",
                dynasty_surname="Congregant",
                gender="BOY" if i % 2 == 0 else "GIRL",
                stage="ADULT" if i > 0 else "ELDER",
                traits={"faith_devotion": 0.50 + (i * 0.02)},
                is_oracle=(i == 7),
            )
        )

    head = rm.select_prayer_head(congregation)
    assert head.agent_id == "worshipper_7"
    assert head.is_oracle is True

    altar_msg = rm.assemble_congregational_prayer(
        participants=congregation,
        target_deity_slot="gm_human",
        altar_name="Cathedral of the Sun",
        current_tick=5000,
        prayer_text="Bless our harvests with divine light.",
    )
    assert altar_msg["mortal_count"] == 10
    assert altar_msg["prayer_head_name"] == "Worshipper_7"
    assert altar_msg["prayer_head_rank"] == "ORACLE"


def test_devotion_unification_and_cli_religions_command(tmp_path: Path) -> None:
    """Verifies get/set_agent_devotion synchronization and cli 'religions' command."""
    agent = AgentRecord(
        agent_id="a_dev_test",
        slot_idx=0,
        display_name="DevTester",
        dynasty_surname="Faith",
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        personality=PersonalityVector(devotion=0.2),
    )

    set_agent_devotion(agent, 0.72)
    assert agent.personality is not None
    assert abs(agent.personality.devotion - 0.72) < 1e-6
    assert abs(agent.traits["faith_devotion"] - 0.72) < 1e-6
    assert abs(get_agent_devotion(agent) - 0.72) < 1e-6

    engine = SimulationEngine(
        db_path=tmp_path / "civ_cli.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    cli = RichGodConsole(engine=engine)
    out = cli.execute_command("religions")
    assert "World Goddess" in out or "Faith" in out or "Religions" in out


def test_semantic_speech_acts_and_mechanical_consequences(engine: SimulationEngine) -> None:
    """Verifies SHARE_BOOK_LORE, REPORT_CRIME, and WARN_PRICE_SPIKE mechanical outcomes."""
    speech = engine.speech_acts

    mentor = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=50.0, y=24.0, z=50.0)
    )
    apprentice = engine.spawn_agent(
        race="HUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=52.0, y=24.0, z=50.0)
    )

    book = WorldLibraryEntry(
        entry_id="lib_agr_crop_rotation",
        topic="AGRICULTURE",
        title="Principles of Crop Rotation",
        summary="Triennial rotation increases barley yield.",
        author_id="Founder",
        author_proficiency=1.0,
        skill_bonus=0.15,
        mechanical_effects={"farming": 0.15},
        created_tick=1,
    )
    engine.governance_engine.library_entries[book.entry_id] = book
    mentor.known_books.append(book.entry_id)

    speech.emit_speech_act(
        speaker=mentor,
        act_type="SHARE_BOOK_LORE",
        topic=book.entry_id,
        listener=apprentice,
    )
    assert book.entry_id in apprentice.known_books
    assert apprentice.active_mechanical_effects.get("farming", 0.0) >= 0.15

    guard = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=53.0, y=24.0, z=50.0)
    )
    guard.profession = "CITY_GUARD"

    speech.emit_speech_act(
        speaker=mentor,
        act_type="REPORT_CRIME",
        topic="THEFT",
        listener=guard,
    )
    assert guard.activity_state == "INTERCEPT_CRIME"

    speech.emit_speech_act(
        speaker=mentor,
        act_type="WARN_PRICE_SPIKE",
        topic="GRAIN",
        listener=apprentice,
    )
    mems = engine.memory_rag.get_recent_memories(apprentice.agent_id)
    assert any("Heard from" in m.summary for m in mems)


def test_speech_acts_crime_deduplication_and_prayer_call(engine: SimulationEngine) -> None:
    """Verifies that 5 guards hearing REPORT_CRIME file 1 case, and PRAYER_CALL updates faith."""
    victim = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    victim.pos = Vec3(x=0.0, y=0.0, z=0.0)

    guards = []
    for i in range(5):
        g = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
        g.role = "CITY_GUARD"
        g.profession = "CITY_GUARD"
        g.pos = Vec3(x=1.0 + i, y=0.0, z=1.0)
        guards.append(g)

    initial_cases = len(engine.judiciary.cases)

    engine.speech_acts.emit_speech_act(
        speaker=victim,
        act_type="REPORT_CRIME",
        topic="THEFT",
        listener=None,
        tick=engine.current_tick,
    )

    new_cases = len(engine.judiciary.cases) - initial_cases
    assert new_cases == 1

    devout = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    devout.pos = Vec3(x=10.0, y=0.0, z=10.0)
    listener = engine.spawn_agent(race="ELF", gender="BOY", stage="ADULT")
    listener.pos = Vec3(x=12.0, y=0.0, z=10.0)
    set_agent_devotion(listener, 0.3)

    engine.speech_acts.emit_speech_act(
        speaker=devout,
        act_type="PRAYER_CALL",
        topic="FAITH",
        listener=listener,
        tick=engine.current_tick,
    )
    assert get_agent_devotion(listener) > 0.3
