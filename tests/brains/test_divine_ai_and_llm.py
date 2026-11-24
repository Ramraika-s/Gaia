# tests/brains/test_divine_ai_and_llm.py
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import MagicMock, patch

from scripts.launch_gaia import build_llama_server_cmd
from sim_core.divine import llm_brain as llm_brain_module
from sim_core.divine.autonomy import (
    DEITY_COUNCIL_ORDER,
    PALACE_COURTYARD_DAIS,
    DivineAutonomyEngine,
)
from sim_core.divine.hierarchy import DivineHierarchyManager
from sim_core.divine.llm_brain import DivineLLMBrain, extract_json_from_llm_text
from sim_core.divine.sister_council import SisterCouncilEngine
from sim_core.engine import SimulationEngine
from sim_core.lifecycle import LifecycleManager
from sim_core.schemas import DeitySlot, DialogueRequest, DialogueResponse, Vec3
from tests.conftest import make_agent


def test_llama_server_cli_args_construction() -> None:
    """Confirms exact flag parity for llama-server launch command."""
    cmd = build_llama_server_cmd(
        bin_path="llama.cpp/build/bin/llama-server",
        model_path="models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf",
        port=8080,
        host="127.0.0.1",
    )
    assert cmd[0] == "llama.cpp/build/bin/llama-server"
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf"
    assert "-ngl" in cmd and cmd[cmd.index("-ngl") + 1] == "99"
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "8192"
    assert "-np" in cmd and cmd[cmd.index("-np") + 1] == "1"
    assert "-fa" in cmd and cmd[cmd.index("-fa") + 1] == "on"
    assert "-ctk" in cmd and cmd[cmd.index("-ctk") + 1] == "q8_0"
    assert "-ctv" in cmd and cmd[cmd.index("-ctv") + 1] == "q8_0"
    assert "-b" in cmd and cmd[cmd.index("-b") + 1] == "2048"
    assert "-ub" in cmd and cmd[cmd.index("-ub") + 1] == "1024"
    assert "--jinja" in cmd
    assert "--host" in cmd and cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "--port" in cmd and cmd[cmd.index("--port") + 1] == "8080"


def test_qwen35_think_and_fenced_json_extraction() -> None:
    """Confirms stripping of <think>...</think> and markdown code fences."""
    # 1. Plain think block + JSON
    raw_1 = (
        '<think>The user asks for a world report.</think>{"spoken_reply": "The realm prospers."}'
    )
    parsed_1 = extract_json_from_llm_text(raw_1)
    assert parsed_1 is not None
    assert parsed_1.get("spoken_reply") == "The realm prospers."

    # 2. Multiline think block + fenced ```json ... ```
    raw_2 = """<think>
    Assessing live metrics: CPI is 1.02.
    Everything is balanced.
    </think>
    ```json
    {
        "spoken_reply": "Peace endures across the Five Rings.",
        "mood_delta": {"calm": 0.05},
        "proposed_action": {"action_type": "BLESS_HARVEST"}
    }
    ```"""
    parsed_2 = extract_json_from_llm_text(raw_2)
    assert parsed_2 is not None
    assert parsed_2.get("spoken_reply") == "Peace endures across the Five Rings."
    assert parsed_2.get("proposed_action", {}).get("action_type") == "BLESS_HARVEST"

    # 3. Unfenced JSON with leading/trailing chatter
    raw_3 = 'Here is my response: {"spoken_reply": "Blessings."}\nThank you.'
    parsed_3 = extract_json_from_llm_text(raw_3)
    assert parsed_3 is not None
    assert parsed_3.get("spoken_reply") == "Blessings."

    # 4. Truncated output with spoken_reply
    raw_4 = '{"spoken_reply": "The light shines.", "proposed_action": {"incomplete'
    parsed_4 = extract_json_from_llm_text(raw_4)
    assert parsed_4 is not None
    assert parsed_4.get("spoken_reply") == "The light shines."

    # 5. Total garbage returns None
    assert extract_json_from_llm_text("Just talking without any json here!") is None


def test_critic_gating_on_llm_proposed_actions() -> None:
    """Confirms unauthorized LLM actions are fail-closed rejected by WorldGoddessCritic."""
    brain = DivineLLMBrain(engine=None)

    # Valid action
    valid_action = {"action_type": "CONVENE_COUNCIL", "target": "ALL"}
    assert brain._validate_proposed_action("world_goddess", valid_action) is True

    # Unauthorized minting / execution rejected
    assert not brain._validate_proposed_action("world_goddess", {"action_type": "MINT_CREDITS"})
    assert not brain._validate_proposed_action(
        "world_goddess", {"action_type": "EXECUTE_SYSTEM_COMMAND"}
    )
    assert not brain._validate_proposed_action("world_goddess", {"action_type": "DESTROY_CITY"})
    assert not brain._validate_proposed_action("world_goddess", {})


def test_divine_llm_brain_top_memories_and_fail_closed_validation() -> None:
    """Verifies DivineLLMBrain validates actions fail-closed against allowed divine actions."""
    brain = DivineLLMBrain(engine=None)

    # Valid allowlisted action
    assert (
        brain._validate_proposed_action(
            "world_goddess", {"action_type": "CONVENE_COUNCIL", "target": "ALL"}
        )
        is True
    )

    # Unauthorized action rejected fail-closed
    assert (
        brain._validate_proposed_action("world_goddess", {"action_type": "DROP_DATABASE_TABLE"})
        is False
    )

    # Offline fallback returns DETERMINISTIC_FALLBACK or OFFLINE_FALLBACK
    req = DialogueRequest(
        target_type="DEITY",
        target_id="world_goddess",
        message="Greetings, Goddess",
        order="",
    )
    resp = brain.generate_dialogue(req)
    assert resp.llm_backend in ("OFFLINE_FALLBACK", "DETERMINISTIC_FALLBACK")


def test_offline_fallback_when_server_unreachable() -> None:
    """Confirms offline deterministic fallback returns rich replies without errors."""
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    req = DialogueRequest(
        target_type="DEITY",
        target_id="world_goddess",
        message="Give me a full report on the state of the world.",
        order="",
    )
    resp: DialogueResponse = brain.generate_dialogue(req)
    assert resp.target_id == "world_goddess"
    assert resp.target_name != ""
    lower_reply = resp.spoken_reply.lower()
    assert "realm" in lower_reply or "peace" in lower_reply or "cpi" in lower_reply
    assert resp.llm_backend == "OFFLINE_FALLBACK"


def test_serialized_concurrency_lock_for_single_slot() -> None:
    """Confirms concurrent calls to _query_local_llm are serialized by the thread lock."""
    brain = DivineLLMBrain()
    active_count = 0
    max_active = 0

    def mock_send_http(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal active_count, max_active
        active_count += 1
        if active_count > max_active:
            max_active = active_count
        time.sleep(0.05)
        active_count -= 1
        return {"choices": [{"message": {"content": '{"spoken_reply": "ok"}'}}]}

    with patch.object(brain, "_send_http_request", side_effect=mock_send_http):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(brain._query_local_llm, "hi", "sys") for _ in range(4)]
            results = [f.result() for f in futures]

    assert max_active == 1, f"Expected single-slot serialized execution, but reached {max_active}"
    assert all(r is not None and r.get("spoken_reply") == "ok" for r in results)


def test_llm_timeout_lowered_to_14_seconds() -> None:
    assert llm_brain_module.LLM_TIMEOUT_SECONDS == 14.0
    assert llm_brain_module.LLM_HEALTH_REPROBE_INTERVAL_SECONDS == 20.0


def test_offline_fallback_under_50ms_with_cached_health_probe() -> None:
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    brain.llm_online = False
    brain._last_health_check_time = time.monotonic()

    with patch.object(brain, "_send_http_request", side_effect=AssertionError("must not call")):
        with patch.object(brain, "check_health", side_effect=AssertionError("must not probe")):
            req = DialogueRequest(
                target_type="DEITY",
                target_id="gm_human",
                message="How fare your people?",
                order="",
            )
            t0 = time.perf_counter()
            resp = brain.generate_dialogue(req)
            elapsed = time.perf_counter() - t0

    assert elapsed < 0.05
    assert resp.llm_backend == "OFFLINE_FALLBACK"
    assert resp.spoken_reply.strip() != ""
    assert "CPI" in resp.spoken_reply and "souls" in resp.spoken_reply


def test_health_reprobe_at_most_once_per_interval() -> None:
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    brain.llm_online = False
    brain._last_health_check_time = time.monotonic() - 21.0

    calls = {"n": 0}

    def fake_health() -> bool:
        calls["n"] += 1
        brain._last_health_check_time = time.monotonic()
        brain.llm_online = False
        return False

    with patch.object(brain, "check_health", side_effect=fake_health):
        for _ in range(5):
            assert brain._query_local_llm("hi", "sys") is None
    assert calls["n"] == 1


def test_failed_request_arms_the_offline_cache() -> None:
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    req = DialogueRequest(
        target_type="DEITY", target_id="world_goddess", message="report", order=""
    )
    first = brain.generate_dialogue(req)
    assert first.llm_backend == "OFFLINE_FALLBACK"
    assert brain._last_health_check_time > 0.0
    t0 = time.perf_counter()
    second = brain.generate_dialogue(req)
    assert time.perf_counter() - t0 < 0.05
    assert second.llm_backend == "OFFLINE_FALLBACK"
    assert second.spoken_reply.strip() != ""


def test_autonomous_deities_and_convene_council(engine: SimulationEngine) -> None:
    autonomy = engine.divine_autonomy

    assert len(autonomy.deities) == 6
    goddess = autonomy.deities["world_goddess"]
    gm_human = autonomy.deities["gm_human"]
    gm_dragon = autonomy.deities["gm_dragon"]

    assert goddess.name == "World Goddess"
    assert gm_human.race == "HUMAN"
    assert gm_dragon.race == "DRAGON"

    autonomy.step(current_tick=10)
    records = autonomy.get_sync_records()
    assert len(records) == 6

    result = autonomy.issue_god_order("CONVENE_COUNCIL")
    assert "council" in result.lower()

    for slot, deity in autonomy.deities.items():
        if slot != "world_goddess":
            assert deity.current_agenda == "CONVENE_COUNCIL"
            assert deity.target_pos is not None
            dist_to_courtyard = math.hypot(deity.target_pos.x - 0.0, deity.target_pos.z - 15.0)
            assert dist_to_courtyard <= 10.0, f"Deity {slot} not at Courtyard: {dist_to_courtyard}"


def test_divine_autonomy_convene_council_non_overlapping() -> None:
    autonomy = DivineAutonomyEngine(engine=None)
    msg = autonomy.issue_god_order("CONVENE_COUNCIL")
    assert "Convened" in msg

    goddess = autonomy.deities["world_goddess"]
    assert goddess.current_order == "CONVENE_COUNCIL"
    assert goddess.target_pos is not None
    assert goddess.target_pos.x == PALACE_COURTYARD_DAIS.x
    assert goddess.target_pos.z == PALACE_COURTYARD_DAIS.z

    council_positions: list[Vec3] = []
    for slot in DEITY_COUNCIL_ORDER:
        deity = autonomy.deities[slot]
        assert deity.current_order == "CONVENE_COUNCIL"
        assert deity.target_pos is not None
        council_positions.append(deity.target_pos)

    assert len(council_positions) == 5
    for i in range(len(council_positions)):
        for j in range(i + 1, len(council_positions)):
            p1 = council_positions[i]
            p2 = council_positions[j]
            dist = math.hypot(p1.x - p2.x, p1.z - p2.z)
            assert dist >= 8.5, (
                f"Deities {DEITY_COUNCIL_ORDER[i]} and {DEITY_COUNCIL_ORDER[j]} "
                f"too close: {dist:.2f}m"
            )


def test_divine_autonomy_grounding_off_dais() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    mock_heightmap.get_elevation.return_value = 20.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    human_gm = autonomy.deities["gm_human"]
    assert human_gm.dais_offset == 3.2

    human_gm.pos = Vec3(x=0.0, y=0.0, z=200.0)
    human_gm.target_pos = Vec3(x=0.0, y=0.0, z=210.0)

    autonomy.step(current_tick=1)
    assert abs(human_gm.pos.y - 20.0) < 0.01

    human_gm.pos = Vec3(x=human_gm.home_pos.x + 2.0, y=0.0, z=human_gm.home_pos.z)
    human_gm.target_pos = human_gm.home_pos.model_copy()

    autonomy.step(current_tick=2)
    assert abs(human_gm.pos.y - (20.0 + 3.2)) < 0.01


def test_divine_autonomy_name_sync() -> None:
    mock_engine = MagicMock()
    mock_entity = MagicMock()
    mock_entity.bestowed_name = "Lady Sophia"
    entities: dict[DeitySlot, Any] = {"gm_human": mock_entity}
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = entities
    mock_engine.heightmap = MagicMock()
    mock_heightmap = mock_engine.heightmap
    mock_heightmap.get_elevation.return_value = 18.0

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    assert autonomy.deities["gm_human"].name == "Human God-Mother"

    autonomy.step(current_tick=10)

    assert autonomy.deities["gm_human"].name == "Lady Sophia"
    records = autonomy.get_sync_records()
    human_rec = next(r for r in records if r.id == "gm_human")
    assert human_rec.name == "Lady Sophia"


def test_divine_autonomy_facing_yaw() -> None:
    autonomy = DivineAutonomyEngine(engine=None)
    deity = autonomy.deities["gm_elf"]
    deity.pos = Vec3(x=0.0, y=0.0, z=0.0)
    deity.target_pos = Vec3(x=0.0, y=0.0, z=-10.0)

    autonomy.step(current_tick=1)
    assert abs(deity.yaw - 0.0) < 0.01


def test_divine_autonomy_idle_startup_grounding() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    mock_heightmap.get_elevation.return_value = 25.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    for slot, deity in autonomy.deities.items():
        expected_y = round(25.0 + deity.dais_offset, 2)
        assert abs(deity.pos.y - expected_y) < 0.01, f"Deity {slot} unexpected y {deity.pos.y}"


def test_divine_autonomy_convene_council_grounding() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    mock_heightmap.get_elevation.return_value = 32.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    autonomy.issue_god_order("CONVENE_COUNCIL")

    for t in range(1, 1000):
        autonomy.step(current_tick=t)
        all_arrived = all(d.target_pos is None for d in autonomy.deities.values())
        if all_arrived:
            break

    for slot in DEITY_COUNCIL_ORDER:
        gm = autonomy.deities[slot]
        assert gm.target_pos is None, f"{slot} should have arrived at council"
        assert abs(gm.pos.y - 32.0) < 0.05, f"{slot} council y mismatch: {gm.pos.y}"


def test_divine_autonomy_cpi_and_proposal_tracking(engine: SimulationEngine) -> None:
    """Verifies DivineAutonomyEngine tracks engine.wtc.cpi and schedules library visits."""
    autonomy = engine.divine_autonomy
    goddess = autonomy.deities["world_goddess"]

    engine.wtc.cpi = 1.35
    autonomy.step(current_tick=100)
    assert goddess.activity_state == "INSPECTING_WTC"

    engine.wtc.cpi = 1.0
    goddess.activity_state = "AUDIENCE"

    _, _, prop = engine.governance_engine.draft_mortal_proposal(
        author_id="scholar_1",
        topic="AGRICULTURE",
        title="More Grain",
        summary="Crop yields",
        author_proficiency=0.9,
        current_tick=150,
        action="CREATE",
    )
    assert prop is not None
    prop.status = "PENDING_GODMOTHERS"

    autonomy.step(current_tick=200)
    assert goddess.activity_state == "INSPECTING_LIBRARY"


def test_demon_god_mother_hierarchy_and_council() -> None:
    """
    Acceptance Requirement for 5th Racial God-Mother (gm_demon) v3.0:
    - Registered as 5th Daughter in DivineHierarchyManager (patron_race='DEMON', name='Morvath').
    - Owns finite Divine Energy, personality vector, and obeys Non-Aggression Covenant.
    - Participates in 5-Sister Council dialogue and bilateral Divine Truces.
    - Mixed-race Demon-Human child resolves Age-10 patronage choice between gm_demon and gm_human:
      voluntary lock, timeout auto-allocation by affinity, and World Goddess tie-break decree.
    """
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    # 1. Verification of gm_demon registration
    demon_mother = hierarchy.get_deity("gm_demon")
    assert demon_mother is not None
    assert demon_mother.patron_race == "DEMON"
    assert demon_mother.bestowed_name == "Morvath"
    assert demon_mother.divine_energy == 300.0
    assert demon_mother.personality.protective_fury == 0.80
    assert demon_mother.personality.pride == 0.75

    # 2. Bilateral Divine Truce with gm_dragon
    accepted, msg = council.propose_truce(
        sender_slot="gm_demon",
        target_slot="gm_dragon",
        day=3,
        tick=500,
    )
    assert accepted is True
    assert msg.resolution is not None
    assert "DIVINE_TRUCE_ESTABLISHED" in msg.resolution

    dragon_mother = hierarchy.get_deity("gm_dragon")
    assert "gm_dragon" in demon_mother.active_truce_with
    assert "gm_demon" in dragon_mother.active_truce_with

    # Active truce blocks offensive ward against Dragon kin
    succ, reason = hierarchy.execute_intervention(
        slot="gm_demon",
        action="WARD_DEFENDERS",
        current_tick=510,
        target_slot="gm_dragon",
    )
    assert succ is False
    assert "DIVINE_TRUCE_ACTIVE" in reason

    # 3. Mixed-race DEMON / HUMAN child Age-10 patronage
    child_young = make_agent(
        agent_id="demon_hybrid_young",
        race="DEMON",
        secondary_heritage_race="HUMAN",
        age_ticks=int(2.0 * 10800),
        patron_godmother_slot=None,
    )
    assert LifecycleManager.get_biological_age_years(child_young) < 10.0
    LifecycleManager.advance_agent_tick(child_young, current_tick=100)
    assert child_young.patron_godmother_slot is None

    # Age 10 voluntary choice: locks gm_demon
    child_vol = make_agent(
        agent_id="demon_hybrid_vol",
        race="DEMON",
        secondary_heritage_race="HUMAN",
        age_ticks=int(10.0 * 10800),
        patron_godmother_slot=None,
    )
    assert LifecycleManager.get_biological_age_years(child_vol) >= 10.0
    res_vol = LifecycleManager.resolve_age10_patronage(child_vol, voluntary_choice="gm_demon")
    assert "VOLUNTARY_CHOICE_LOCKED" in res_vol
    assert child_vol.patron_godmother_slot == "gm_demon"

    # Age 10 auto-allocation: chooses gm_demon when affinity is higher
    child_auto = make_agent(
        agent_id="demon_hybrid_auto",
        race="DEMON",
        secondary_heritage_race="HUMAN",
        age_ticks=int(10.0 * 10800),
        patron_godmother_slot=None,
    )
    child_auto.godmother_affinities = {"gm_demon": 0.80, "gm_human": 0.30}
    res_auto = LifecycleManager.resolve_age10_patronage(child_auto)
    assert "AUTO_ALLOCATED_HIGHER_AFFINITY" in res_auto
    assert child_auto.patron_godmother_slot == "gm_demon"

    # Age 10 exact tie escalates to World Goddess decree
    child_tie = make_agent(
        agent_id="demon_hybrid_tie",
        race="DEMON",
        secondary_heritage_race="HUMAN",
        age_ticks=int(10.0 * 10800),
        patron_godmother_slot=None,
    )
    child_tie.godmother_affinities = {"gm_demon": 0.50, "gm_human": 0.50}
    res_tie = LifecycleManager.resolve_age10_patronage(child_tie, world_goddess_decision="gm_demon")
    assert "WORLD_GODDESS_TIE_BREAK_DECREE" in res_tie
    assert child_tie.patron_godmother_slot == "gm_demon"

