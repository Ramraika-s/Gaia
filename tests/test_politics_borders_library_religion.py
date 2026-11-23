"""
tests/test_politics_borders_library_religion.py
Acceptance tests for Phase 3B:
1. Two-Book Governance: World Library (world_library) mortal & divine scholarship.
2. Two-Book Governance: Divine Codex (divine_codex) Option B split write authority.
3. Territorial Borders: 5-tier appeals, non-overlapping borders, and Neutral Free Cities.
4. Dynamic Religion & Altars: Intent-scaled prayer, inactivity decay, and Prayer Head.
"""

from __future__ import annotations

import json
from typing import cast

from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import (
    AgentRecord,
    CommitProposal,
    DeitySlot,
    WorldLibraryEntry,
)
from sim_core.society.borders import BorderManager
from sim_core.society.library import (
    EXPIRY_TICKS,
    OBJECTION_WINDOW_TICKS,
    TwoBookGovernanceEngine,
)
from sim_core.society.politics import PoliticalEngine, Polity
from sim_core.society.religion import ReligionManager

# =============================================================================
# 1. World Library Governance (world_library) Acceptance Tests
# =============================================================================


def test_world_library_mortal_proposal_lifecycle_and_objection_window():
    """
    Tests mortal scholarship lifecycle:
    1. Mortal submits proposal.
    2. Passes Mortal Elders (> 50%).
    3. Moves to PENDING_GODMOTHERS.
    4. First Daughter approves -> enters 1-day OBJECTION_WINDOW.
    5. After 1 day elapses with < 3 objections -> COMMITS to world_library.
    """
    engine = TwoBookGovernanceEngine()

    # 1. Draft proposal
    ok, msg, prop = engine.draft_mortal_proposal(
        author_id="scholar_erik",
        topic="Metalsmithing",
        title="Dwarven Alloys",
        summary="Forging methods for high-durability plows.",
        author_proficiency=0.85,
        current_tick=100,
        action="CREATE",
    )
    assert ok and prop is not None
    assert prop.status == "OPEN"

    # 2. Vote by Elders (2 of 3 vote APPROVE -> >50%)
    ok, msg = engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=3
    )
    assert ok and prop.status == "OPEN"

    ok, msg = engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_2", vote="APPROVE", total_appointed_elders=3
    )
    assert ok and prop.status == "PENDING_GODMOTHERS"

    # 3. First Daughter approves -> starts 1-day objection window
    ok, msg = engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_human", vote="APPROVE", current_tick=200
    )
    assert ok and prop.status == "OBJECTION_WINDOW"
    assert prop.first_approval_tick == 200

    # 4. Advance time past 1 day (OBJECTION_WINDOW_TICKS) with only 1 objection (gm_elf)
    engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_elf", vote="OBJECT", current_tick=300
    )
    assert prop.status == "OBJECTION_WINDOW"

    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=200 + OBJECTION_WINDOW_TICKS + 1
    )
    assert status == "APPROVED_AND_COMMITTED"
    assert prop.status == "APPROVED"
    assert len(engine.library_entries) == 1
    committed_entry = list(engine.library_entries.values())[0]
    assert committed_entry.title == "Dwarven Alloys"


def test_world_library_daughter_objection_block_and_appeal():
    """
    Verifies that >= 3/4 Daughters objecting within 1 day blocks the proposal
    and allows appeal to the World Goddess or God.
    """
    engine = TwoBookGovernanceEngine()

    _, _, prop = engine.draft_mortal_proposal(
        author_id="heretic_bob",
        topic="DarkArts",
        title="Necromancy Basics",
        summary="Raising fallen units.",
        author_proficiency=0.9,
        current_tick=10,
        action="CREATE",
    )
    assert prop is not None

    # Elders approve (1 of 1)
    engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    # 1 Daughter approves, but 3 Daughters object (>50% objections)
    engine.cast_godmother_vote(prop.proposal_id, "gm_human", "APPROVE", current_tick=20)
    engine.cast_godmother_vote(prop.proposal_id, "gm_elf", "OBJECT", current_tick=25)
    engine.cast_godmother_vote(prop.proposal_id, "gm_dragon", "OBJECT", current_tick=30)
    ok, msg = engine.cast_godmother_vote(
        prop.proposal_id, "gm_beasthuman", "OBJECT", current_tick=35
    )

    assert ok and msg == "BLOCKED_BY_DAUGHTERS"
    assert prop.status == "BLOCKED_BY_DAUGHTERS"

    # Attempting to commit via lifecycle advance fails
    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=20 + OBJECTION_WINDOW_TICKS + 100
    )
    assert status == "BLOCKED_BY_DAUGHTERS"

    # Appeal to World Goddess
    ok, msg = engine.appeal_blocked_proposal(prop.proposal_id, "WORLD_GODDESS")
    assert ok and prop.appeal_target == "WORLD_GODDESS"

    # Goddess upholds appeal -> COMMITTED
    ok, msg = engine.resolve_appeal_world_goddess(prop.proposal_id, approved=True, current_tick=60)
    assert ok and prop.status == "APPROVED"
    assert len(engine.library_entries) == 1


def test_world_library_expiry_after_30_days():
    """Verifies that a proposal receiving 0 God-Mother approvals expires after 30 game days."""
    engine = TwoBookGovernanceEngine()

    _, _, prop = engine.draft_mortal_proposal(
        author_id="forgotten_author",
        topic="Trivia",
        title="Unread Lore",
        summary="Obscure notes.",
        author_proficiency=0.75,
        current_tick=0,
        action="CREATE",
    )
    assert prop is not None
    engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    # 29 days pass -> still pending
    status = engine.advance_proposal_lifecycle(prop.proposal_id, current_tick=EXPIRY_TICKS - 1)
    assert status == "PENDING_GODMOTHERS"

    # 30 days pass -> EXPIRED
    status = engine.advance_proposal_lifecycle(prop.proposal_id, current_tick=EXPIRY_TICKS + 1)
    assert status == "EXPIRED"
    assert prop.status == "EXPIRED"


def test_world_library_divine_direct_edits():
    """
    Verifies divine writing authority:
    - God direct edit succeeds.
    - Goddess + >= 1 Daughter succeeds.
    - 3/4 Daughters alone succeeds.
    - 2/4 Daughters alone fails.
    """
    engine = TwoBookGovernanceEngine()

    # 1. God direct edit
    e_god = WorldLibraryEntry(
        entry_id="entry_god_1",
        topic="Cosmology",
        title="Origin of the World",
        summary="Decreed by God.",
        author_id="GOD",
        author_proficiency=1.0,
        is_scripture=True,
        created_tick=1,
    )
    ok, msg = engine.write_library_direct_god(e_god)
    assert ok and "entry_god_1" in engine.library_entries

    # 2. Goddess + 1 Daughter succeeds
    e_goddess = WorldLibraryEntry(
        entry_id="entry_goddess_1",
        topic="Morals",
        title="Virtue of Harmony",
        summary="Wisdom of the Mother.",
        author_id="world_goddess",
        author_proficiency=1.0,
        created_tick=2,
    )
    ok, msg = engine.write_library_goddess_with_daughters(
        e_goddess, daughter_approvals=["gm_human"]
    )
    assert ok and "entry_goddess_1" in engine.library_entries

    # 3. 2/5 Daughters alone FAILS (< 3 required)
    e_daughters = WorldLibraryEntry(
        entry_id="entry_daughters_1",
        topic="Biology",
        title="Beast & Dragon Physiology",
        summary="Sisters joint study.",
        author_id="gm_dragon",
        author_proficiency=0.9,
        created_tick=3,
    )
    ok, msg = engine.write_library_daughters_alone(
        e_daughters, daughter_approvals=["gm_dragon", "gm_beasthuman"]
    )
    assert not ok and "REJECTED" in msg

    # 4. 3/5 Daughters alone SUCCEEDS (>= 3 of 5)
    ok, msg = engine.write_library_daughters_alone(
        e_daughters, daughter_approvals=["gm_dragon", "gm_beasthuman", "gm_demon"]
    )
    assert ok and "entry_daughters_1" in engine.library_entries


# =============================================================================
# 2. Divine Rules Book (divine_codex) Option B Acceptance Tests
# =============================================================================


def test_divine_codex_option_b_split_write_authority():
    """
    Verifies Divine Codex Option B:
    - God sole direct authority for text decrees and parameter overrides.
    - Goddess + 3/4 Daughters can write non-mechanical text decrees.
    - Parameter overrides by Goddess/Daughters cannot be written directly;
      must be proposed to God (by Goddess alone or 4/4 Daughters unanimous).
    - Mortals and incomplete Daughter coalitions strictly blocked.
    """
    engine = TwoBookGovernanceEngine()
    critic = WorldGoddessCritic()

    # 1. World Goddess + 3/4 Daughters writes non-mechanical text decree
    ok, msg, entry = engine.write_codex_text_decree_goddess_and_daughters(
        title="Sanctity of Sacred Groves",
        text="No timber shall be felled within 3 chunks of high altars.",
        daughter_approvals=["gm_elf", "gm_human", "gm_beasthuman"],
        current_tick=100,
    )
    assert ok and entry is not None
    assert entry.category == "DECREE"

    # Critic RBAC verification
    prop_decree = CommitProposal(
        proposal_id="prop_dec_1",
        kind="DIVINE_CODEX_DECREE",
        actor_id="world_goddess",
        tick=100,
        payload={
            "author_slot": "world_goddess",
            "supporting_daughter_slots": ["gm_elf", "gm_human", "gm_beasthuman"],
            "category": "DECREE",
        },
    )
    verdict = critic.evaluate(prop_decree)
    assert verdict.status == "SUCCESS"

    # 2. Direct parameter override attempt by Goddess + Daughters is BLOCKED
    prop_override_illegal = CommitProposal(
        proposal_id="prop_ovr_bad",
        kind="DIVINE_CODEX_DECREE",
        actor_id="world_goddess",
        tick=101,
        payload={
            "author_slot": "world_goddess",
            "supporting_daughter_slots": ["gm_elf", "gm_human", "gm_beasthuman", "gm_dragon"],
            "category": "PARAMETER_OVERRIDE",
            "parameter_key": "DIVINE_TRUCE_DURATION_TICKS",
            "parameter_value_json": json.dumps(15000),
        },
    )
    verdict_bad = critic.evaluate(prop_override_illegal)
    assert verdict_bad.status == "FAILURE"
    assert "Option B" in verdict_bad.reason

    # 3. Goddess submits parameter proposal to God
    ok, msg, codex_prop = engine.submit_parameter_override_proposal(
        title="Extend Divine Truce",
        text="Increase truce duration to 15,000 ticks during Holy festivals.",
        parameter_key="DIVINE_TRUCE_DURATION_TICKS",
        parameter_value=15000,
        proposer_slot="world_goddess",
        co_sponsors=[],
        current_tick=102,
    )
    assert ok and codex_prop is not None
    assert codex_prop.status == "PENDING_GOD"

    # God approves proposal -> parameter override committed & live engine updated!
    ok, msg, approved_entry = engine.approve_codex_proposal_by_god(
        codex_prop.proposal_id, current_tick=105
    )
    assert ok and approved_entry is not None
    assert engine.live_engine_overrides["DIVINE_TRUCE_DURATION_TICKS"] == 15000

    # 4. 5/5 Daughters unanimous proposal to God succeeds
    ok, msg, daug_prop = engine.submit_parameter_override_proposal(
        title="Non-Aggression Penalty Boost",
        text="Double divine energy penalty for civilian smites.",
        parameter_key="COVENANT_PENALTY_MULTIPLIER",
        parameter_value=2.0,
        proposer_slot="gm_human",
        co_sponsors=["gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"],
        current_tick=110,
    )
    assert ok and daug_prop is not None
    assert daug_prop.status == "PENDING_GOD"

    # 4/5 Daughters proposal without Goddess FAILS submission
    ok_fail, msg_fail, _ = engine.submit_parameter_override_proposal(
        title="Invalid Co-sponsor Count",
        text="Only 4 sisters total.",
        parameter_key="COVENANT_PENALTY_MULTIPLIER",
        parameter_value=2.0,
        proposer_slot="gm_human",
        co_sponsors=["gm_elf", "gm_dragon", "gm_beasthuman"],  # Only 4 total, not 5!
        current_tick=111,
    )
    assert not ok_fail
    assert "unanimously" in msg_fail

    # 5. God direct write of decree and parameter override (bypass_god_check=True)
    ok, msg, god_entry = engine.write_codex_direct_god(
        title="Supreme Divine Mandate",
        text="Max reality bubble rigs set to 150.",
        category="PARAMETER_OVERRIDE",
        parameter_key="REALITY_BUBBLE_MAX_RIGS",
        parameter_value=150,
        current_tick=120,
    )
    assert ok
    assert engine.live_engine_overrides["REALITY_BUBBLE_MAX_RIGS"] == 150

    # 6. Mortal attempt strictly blocked
    prop_mortal = CommitProposal(
        proposal_id="prop_mortal_codex",
        kind="DIVINE_CODEX_DECREE",
        actor_id="mortal_peasant_1",
        tick=130,
        payload={"author_slot": "mortal_peasant_1", "category": "DECREE"},
    )
    verdict_mortal = critic.evaluate(prop_mortal)
    assert verdict_mortal.status == "FAILURE"


# =============================================================================
# 3. Territorial Borders & Neutral Free Cities Acceptance Tests
# =============================================================================


def test_territorial_borders_appeals_and_neutral_free_cities():
    """
    Verifies territorial borders & appeals:
    - Village appealing for TOWN succeeds when criteria met and fails on border overlap.
    - Multi-racial City (>=2 races at >=15%) wins NEUTRAL_FREE_CITY (war_exempt = True).
    - Neutral Free City is barred from declaring offensive war.
    """
    bm = BorderManager()
    pe = PoliticalEngine()

    # 1. Register existing settlement "village_a" on parcels 0..15
    parcels_a = [f"{x}_{z}" for x in range(4) for z in range(4)]
    bm.register_settlement_border("village_a", parcels_a)

    # 2. Village B appeals for TOWN upgrade
    # Candidate parcels overlapping with Village A should FAIL
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

    # Non-overlapping parcels succeed
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

    # 3. Multi-racial City appeals for NEUTRAL_FREE_CITY
    # City with 40% Human, 35% Elf, 25% Dragon (3 races >= 15%)
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

    # Register as Polity and verify war declaration prohibition
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

    # Offensive war declaration by Neutral Free City must be REJECTED
    ok, msg = pe.declare_war("city_crossroads", "nation_iron")
    assert not ok
    assert "Neutral Free Cities cannot declare offensive war" in msg


# =============================================================================
# 4. Dynamic Faith & Congregational Altars Acceptance Tests
# =============================================================================


def test_dynamic_faith_intent_scaled_gains_and_inactivity_decay():
    """
    Verifies religious dynamics:
    - Earnest prayer yields higher faith devotion than Obligation.
    - Mortals cannot pray directly to God.
    - Inactivity > 2 game days decays faith_devotion.
    - Congregational altar with 10 mortals produces 1 unified message led by Prayer Head.
    """
    rm = ReligionManager()

    # 1. Direct prayer to God must be FORBIDDEN
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
        target_deity_slot=cast(DeitySlot, "GOD"),  # type: ignore[arg-type]
        intent="EARNEST_VOLUNTARY",
        current_tick=10,
    )
    assert not ok
    assert "FORBIDDEN" in reason

    # 2. Earnest prayer gain > Obligation gain
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

    # 3. Inactivity decay after > 2 game days (2 * TICKS_PER_GAME_DAY)
    agent_earnest.last_prayer_tick = 100
    decay_tick = 100 + (2 * TICKS_PER_GAME_DAY) + 1000

    old_faith = agent_earnest.traits["faith_devotion"]
    rm.apply_inactivity_decay(agent_earnest, current_tick=decay_tick)
    assert agent_earnest.traits["faith_devotion"] < old_faith

    # 4. Congregational Altar Prayer with 10 mortals
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
                is_oracle=(i == 7),  # Worshipper 7 is an Oracle!
            )
        )

    # Oracle must be elected as the Prayer Head
    head = rm.select_prayer_head(congregation)
    assert head.agent_id == "worshipper_7"
    assert head.is_oracle is True

    # Assembled prayer emits ONE unified congregational message
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
