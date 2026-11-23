#!/usr/bin/env python3
"""
scripts/verify_live_qwen.py
One-off live smoke test verifying real Qwen3.5-4B GGUF inference via llama-server:
1. Spawns llama-server on port 8089 with Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf.
2. Waits until /health endpoint responds.
3. Sends 1 real RAG-grounded World Goddess DIALOGUE_REQUEST through DivineLLMBrain.
4. Measures and prints response text, latency in ms, and llm_backend tag.
5. Shuts down llama-server cleanly and confirms zero leftover processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.launch_gaia import build_llama_server_cmd, check_llm_health  # noqa: E402
from sim_core.divine.llm_brain import DivineLLMBrain  # noqa: E402
from sim_core.schemas import DialogueRequest  # noqa: E402

PORT = 8089
MODEL_PATH = "models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf"
BIN_PATH = "llama.cpp/build/bin/llama-server"


def main() -> int:
    print("=" * 70)
    print("✦ REAL LIVE LOCAL-LLM SMOKE TEST: QWEN3.5-4B + LLAMA-SERVER ✦")
    print(f"Model:  {MODEL_PATH}")
    print(f"Binary: {BIN_PATH}")
    print(f"Port:   {PORT}")
    print("=" * 70)

    if not os.path.exists(MODEL_PATH) or not os.path.exists(BIN_PATH):
        print("[!] Error: Model or binary missing on disk.")
        return 1

    # Ensure data/logs directory
    log_dir = REPO_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / "llama_server_smoke.log"

    cmd = build_llama_server_cmd(
        bin_path=BIN_PATH,
        model_path=MODEL_PATH,
        port=PORT,
        host="127.0.0.1",
    )

    print(f"[*] Starting llama-server on port {PORT}...")
    log_file = open(log_file_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
    )

    try:
        # Wait for /health
        print("[*] Waiting for /health readiness (up to 45s)...")
        start_wait = time.time()
        is_ready = False
        while (time.time() - start_wait) < 45.0:
            if proc.poll() is not None:
                print(f"[!] llama-server exited prematurely with code {proc.returncode}!")
                break
            if check_llm_health("127.0.0.1", PORT):
                is_ready = True
                break
            time.sleep(0.5)

        if not is_ready:
            print("[!] Timed out waiting for llama-server /health!")
            return 1

        ready_time = time.time() - start_wait
        print(f"[+] llama-server is READY on port {PORT} ({ready_time:.2f}s)!")

        # Send 1 real RAG-grounded dialogue request
        brain = DivineLLMBrain(
            llm_url=f"http://127.0.0.1:{PORT}/v1/chat/completions",
            model_name=MODEL_PATH,
            active_model_name="Huihui-Qwen3.5-4B",
        )

        req = DialogueRequest(
            target_type="DEITY",
            target_id="world_goddess",
            message="What is the state of our five mortal nations and the divine balance?",
            order="",
        )

        print("[*] Dispatching real DIALOGUE_REQUEST to Qwen3.5...")
        t0 = time.perf_counter()
        resp = brain.generate_dialogue(req)
        latency_ms = (time.perf_counter() - t0) * 1000

        print("-" * 70)
        print(f"Target:       {resp.target_name} ({resp.target_id})")
        print(f"Backend:      {resp.llm_backend}")
        print(f"Latency:      {latency_ms:.2f} ms")
        print(f"Mood:         {resp.mood}")
        print(f"Spoken Reply: \"{resp.spoken_reply}\"")
        if resp.action_taken:
            print(f"Action Taken: {resp.action_taken}")
        print("-" * 70)

        # Assertions
        if not resp.spoken_reply:
            print("[!] Error: Received empty spoken_reply from model!")
            return 1
        if "LIVE" not in resp.llm_backend:
            print(f"[!] Warning: Response did not indicate LIVE backend: {resp.llm_backend}")
            return 1

        print("✦ LIVE LOCAL-LLM SMOKE TEST PASSED SUCCESSFULLY ✦")
        return 0

    finally:
        print("[*] Shutting down llama-server...")
        log_file.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=4.0)
            except subprocess.TimeoutExpired:
                print("[!] Force killing llama-server...")
                proc.kill()
                proc.wait(timeout=2.0)
        print("[+] llama-server terminated.")
        # Confirm zero leftover processes
        check_p = subprocess.run(["pgrep", "-f", "llama-server"], capture_output=True, text=True)
        if check_p.stdout.strip():
            print(f"[!] Warning: Found leftover llama-server processes: {check_p.stdout.strip()}")
        else:
            print("[+] Verified zero leftover llama-server processes on system.")


if __name__ == "__main__":
    sys.exit(main())
