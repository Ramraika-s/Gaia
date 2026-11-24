"""
tests/test_aa_step2_dialogue_and_bubble.py
AA Visual Overhaul Step 2 regression tests:
1. BUBBLE_SYNC payload never contains None for string fields (fixes Godot MortalActor crash).
2. DIALOGUE_REQUEST dispatch never blocks GOD_STATE / GOD_COMMAND on the WebSocket loop.
3. DivineLLMBrain fails over to grounded OFFLINE_FALLBACK in < 50 ms (cached health probe).
4. SimulationEngine boots at golden morning 08:30.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.divine import llm_brain as llm_brain_module
from sim_core.divine.llm_brain import DivineLLMBrain
from sim_core.engine import SimulationEngine
from sim_core.schemas import DialogueRequest, DialogueResponse, Vec3

STRING_FIELDS = ("dynasty", "dragon_form", "speech_text", "role", "profession", "name")


@pytest.fixture
def engine(tmp_path: Path) -> SimulationEngine:
    return SimulationEngine(
        db_path=tmp_path / "aa_step2.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )


# ---------------------------------------------------------------------------
# 1. BUBBLE_SYNC null-safety
# ---------------------------------------------------------------------------


def test_bubble_sync_never_contains_none_strings(engine: SimulationEngine) -> None:
    adult = engine.spawn_agent("HUMAN", "BOY", stage="ADULT", pos=Vec3(x=1.0, y=0.0, z=1.0))
    dragon = engine.spawn_agent("DRAGON", "GIRL", stage="ADULT", pos=Vec3(x=2.0, y=0.0, z=2.0))
    # Force the exact bad states that used to leak JSON null into Godot.
    for agent in (adult, dragon):
        object.__setattr__(agent, "dynasty_surname", None)
        object.__setattr__(agent, "role", None)
        object.__setattr__(agent, "speech_text", None)
    # profession is consumed by the neural tiers every tick, so use the falsy-empty variant here.
    object.__setattr__(adult, "profession", "")
    object.__setattr__(dragon, "profession", "")
    object.__setattr__(adult, "dragon_form", None)
    object.__setattr__(dragon, "dragon_form", None)

    engine.step_tick()
    rigs: list[dict[str, Any]] = engine.adapter.bubble_agents  # type: ignore[attr-defined]
    assert len(rigs) >= 2
    for rig in rigs:
        for key in STRING_FIELDS:
            assert rig[key] is not None, f"{key} is None in BUBBLE_SYNC"
            assert isinstance(rig[key], str)
        assert rig["role"] != "" and rig["profession"] != "" and rig["dragon_form"] != ""
        json.dumps(rig)  # must be JSON-serialisable
    assert rigs[0]["dynasty"] == ""
    assert rigs[0]["speech_text"] == ""
    assert rigs[0]["dragon_form"] == "HUMANOID_DRAGON"


# ---------------------------------------------------------------------------
# 2. Non-blocking dialogue dispatch
# ---------------------------------------------------------------------------


async def test_dialogue_request_does_not_block_god_commands(engine: SimulationEngine) -> None:
    def slow_generate(req: DialogueRequest) -> DialogueResponse:
        time.sleep(0.3)
        return DialogueResponse(
            target_id=req.target_id,
            target_name="Gaia",
            title="World Goddess",
            race="DIVINE",
            mood="calm",
            spoken_reply="Peace, My Lord.",
            action_taken="",
            llm_backend="OFFLINE_FALLBACK",
        )

    engine.divine_llm_brain = SimpleNamespace(generate_dialogue=slow_generate)  # type: ignore[assignment]
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=18791, engine=engine)
    await bridge.start_server_async()
    try:
        async with websockets.connect("ws://127.0.0.1:18791") as ws:
            t0 = time.monotonic()
            await ws.send(
                json.dumps(
                    {
                        "type": "DIALOGUE_REQUEST",
                        "dialogue_id": "slow_1",
                        "target_type": "DEITY",
                        "target_id": "world_goddess",
                        "message": "Greetings",
                        "order": "",
                    }
                )
            )
            await ws.send(json.dumps({"type": "GOD_STATE", "x": 3.0, "y": 1.0, "z": 4.0}))
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "pause", "args": {}}))

            arrivals: list[tuple[str, float]] = []
            while len(arrivals) < 3:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                arrivals.append((msg["type"], time.monotonic() - t0))

            by_type = dict(arrivals)
            assert "DIALOGUE_RESPONSE" in by_type
            assert "GOD_STATE_ACK" in by_type
            assert "GOD_COMMAND_RESPONSE" in by_type
            # GOD_STATE / GOD_COMMAND answered well before the 0.3 s LLM call finishes...
            assert by_type["GOD_STATE_ACK"] < 0.25
            assert by_type["GOD_COMMAND_RESPONSE"] < 0.25
            # ...and the dialogue reply still arrives afterwards, intact.
            assert by_type["DIALOGUE_RESPONSE"] >= 0.28
            assert arrivals[-1][0] == "DIALOGUE_RESPONSE"
        assert engine.god_avatar_pos.x == 3.0
    finally:
        await bridge.stop_server_async()
    assert not bridge._background_tasks


async def test_handle_inbound_dialogue_is_awaitable_with_flush(engine: SimulationEngine) -> None:
    """Direct callers can await handle_inbound_message then flush_background_tasks."""
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=18792, engine=engine)
    sent: list[dict[str, Any]] = []

    class FakeClient:
        async def send(self, payload: str) -> None:
            sent.append(json.loads(payload))

    msg = json.dumps(
        {
            "type": "DIALOGUE_REQUEST",
            "target_type": "DEITY",
            "target_id": "world_goddess",
            "message": "Give me a report on the world.",
        }
    )
    await bridge.handle_inbound_message(FakeClient(), msg)
    await bridge.flush_background_tasks()
    assert [m["type"] for m in sent] == ["DIALOGUE_RESPONSE"]
    assert sent[0]["spoken_reply"].strip() != ""
    assert not bridge._background_tasks


async def test_disconnect_cancels_inflight_dialogue(engine: SimulationEngine) -> None:
    def very_slow(req: DialogueRequest) -> DialogueResponse:
        time.sleep(0.2)
        return DialogueResponse(
            target_id=req.target_id,
            target_name="X",
            title="T",
            race="DIVINE",
            mood="calm",
            spoken_reply="late",
            action_taken="",
        )

    engine.divine_llm_brain = SimpleNamespace(generate_dialogue=very_slow)  # type: ignore[assignment]
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=18793, engine=engine)
    await bridge.start_server_async()
    try:
        async with websockets.connect("ws://127.0.0.1:18793") as ws:
            await ws.send(
                json.dumps(
                    {"type": "DIALOGUE_REQUEST", "target_type": "DEITY", "target_id": "gm_elf"}
                )
            )
            await asyncio.sleep(0.05)
            assert bridge._background_tasks
        await asyncio.sleep(0.4)
        assert not bridge._background_tasks
    finally:
        await bridge.stop_server_async()


# ---------------------------------------------------------------------------
# 3. LLM fast failover
# ---------------------------------------------------------------------------


def test_llm_timeout_lowered_to_14_seconds() -> None:
    assert llm_brain_module.LLM_TIMEOUT_SECONDS == 14.0
    assert llm_brain_module.LLM_HEALTH_REPROBE_INTERVAL_SECONDS == 20.0


def test_offline_fallback_under_50ms_with_cached_health_probe() -> None:
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    brain.llm_online = False
    brain._last_health_check_time = time.monotonic()  # probed just now -> cached verdict

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
    # Grounded in live telemetry (population count, CPI, petitions)
    assert "CPI" in resp.spoken_reply and "souls" in resp.spoken_reply


def test_health_reprobe_at_most_once_per_interval() -> None:
    brain = DivineLLMBrain(llm_url="http://127.0.0.1:59999/v1/chat/completions")
    brain.llm_online = False
    brain._last_health_check_time = time.monotonic() - 21.0  # interval elapsed

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
    first = brain.generate_dialogue(req)  # first call really tries (connection refused)
    assert first.llm_backend == "OFFLINE_FALLBACK"
    assert brain._last_health_check_time > 0.0
    t0 = time.perf_counter()
    second = brain.generate_dialogue(req)
    assert time.perf_counter() - t0 < 0.05
    assert second.llm_backend == "OFFLINE_FALLBACK"
    assert second.spoken_reply.strip() != ""


# ---------------------------------------------------------------------------
# 4. Golden morning boot
# ---------------------------------------------------------------------------


def test_engine_boots_at_golden_morning(engine: SimulationEngine) -> None:
    assert engine.day_start_hour == 8.5
    engine.step_tick()
    engine.step_tick()  # sync_weather_time fires on even ticks
    wt = engine.adapter.weather_time  # type: ignore[attr-defined]
    expected = (2 / float(TICKS_PER_GAME_DAY)) * 24.0 + 8.5
    assert wt["time_of_day"] == pytest.approx(expected, abs=1e-6)
    assert 8.5 <= wt["time_of_day"] < 8.6
