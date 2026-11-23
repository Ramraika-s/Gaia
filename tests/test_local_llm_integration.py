# tests/test_local_llm_integration.py
# Offline / Unit verification for Sprint 5.5:
# 1. llama-server exact CLI argument list construction
# 2. Qwen3.5 <think>...</think> + markdown fenced JSON extraction
# 3. Critic gating of LLM proposed actions
# 4. Graceful offline fallback on connection error
# 5. Serialized single-slot (-np 1) thread-safe execution

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch

from scripts.launch_gaia import build_llama_server_cmd
from sim_core.divine.llm_brain import DivineLLMBrain, extract_json_from_llm_text
from sim_core.schemas import DialogueRequest, DialogueResponse


def test_llama_server_cli_args_construction():
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


def test_qwen35_think_and_fenced_json_extraction():
    """Confirms stripping of <think>...</think> and markdown code fences."""
    # 1. Plain think block + JSON
    raw_1 = (
        "<think>The user asks for a world report.</think>"
        '{"spoken_reply": "The realm prospers."}'
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


def test_critic_gating_on_llm_proposed_actions():
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


def test_offline_fallback_when_server_unreachable():
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


def test_serialized_concurrency_lock_for_single_slot():
    """Confirms concurrent calls to _query_local_llm are serialized by the thread lock."""
    brain = DivineLLMBrain()
    active_count = 0
    max_active = 0

    def mock_send_http(*args: Any, **kwargs: Any):
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
