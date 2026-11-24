#!/usr/bin/env python3
"""
scripts/launch_gaia.py
One-Command Launcher for the Gaia Persistent AI Civilization Simulation.
Boots the 5-race SimulationEngine + GodotWebSocketBridge,
waits until WebSocket server accepts connections, launches Godot 4.7.2 client
(unless --headless), and executes graceful SIGINT/SIGTERM shutdown with an
atomic World Goddess end-of-day checkpoint.

Usage:
  uv run python scripts/launch_gaia.py [--agents 1500] [--headless] [--port 8765] [--speed 1.0]
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge  # noqa: E402
from sim_core.config import CIVIC_TICK_INTERVAL_TICKS  # noqa: E402
from sim_core.engine import SimulationEngine  # noqa: E402
from sim_core.god_console.cli import RichGodConsole  # noqa: E402
from sim_core.races import BeasthumanSubLineage  # noqa: E402
from sim_core.schemas import AgentRole, Gender, RaceId, Vec3  # noqa: E402
from sim_core.society.wtc_market import WTCExchange  # noqa: E402


def check_port_open(host: str, port: int) -> bool:
    """Checks if a TCP port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False


def check_llm_health(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Checks if llama-server /health endpoint responds with HTTP 200."""
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GaiaLauncher"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def build_llama_server_cmd(
    bin_path: str = "llama.cpp/build/bin/llama-server",
    model_path: str = "models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf",
    port: int = 8080,
    host: str = "127.0.0.1",
) -> list[str]:
    """Constructs the exact command list to launch llama-server with Qwen3.5."""
    return [
        bin_path,
        "-m",
        model_path,
        "-ngl",
        "99",
        "-c",
        "8192",
        "-np",
        "1",
        "-fa",
        "on",
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "-b",
        "2048",
        "-ub",
        "1024",
        "--jinja",
        "--host",
        host,
        "--port",
        str(port),
    ]


def spawn_initial_population(engine: SimulationEngine, num_agents: int) -> None:
    """Populates world across 5 biomes, 5 races, 2 genders, and Beasthuman sub-lineages."""
    races: list[RaceId] = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
    genders: list[Gender] = ["BOY", "GIRL"]
    beasthuman_sublineages: list[BeasthumanSubLineage] = [
        "CAT_KIN",
        "WOLF_KIN",
        "DWARF",
        "BARBARIAN",
    ]

    print("[*] Spawning Palace Knight Battalion (24 elite guards) on Acropolis...")
    engine.palace_security.spawn_knight_battalion(engine.agents, count=24)

    # Mixed-race cohort around Outer Imperial Plaza (r = 140m .. 340m)
    plaza_cohort_size = min(180, max(50, num_agents // 5))
    roles: list[AgentRole] = [
        "CITIZEN",
        "FARMER",
        "MERCHANT",
        "BLACKSMITH",
        "BUILDER",
        "SCHOLAR",
        "CLERIC",
        "HUNTER",
    ]
    print(
        f"[*] Spawning {plaza_cohort_size} diversified citizens & scholars in Imperial Plaza..."
    )

    for j in range(plaza_cohort_size):
        race = races[j % 5]
        gender = genders[j % 2]
        sub_lineage = beasthuman_sublineages[j % 4] if race == "BEASTHUMAN" else None
        role = roles[j % len(roles)]

        angle = (j / float(plaza_cohort_size)) * 2.0 * math.pi
        radius = 150.0 + (j % 18) * 10.0  # 150m to 320m
        px = radius * math.cos(angle)
        pz = radius * math.sin(angle)
        pos_vec = Vec3(x=px, y=0.0, z=pz)

        title = role.replace("_", " ").title()
        initial_cr = 60.0 if role in ("MERCHANT", "BLACKSMITH") else 35.0

        engine.spawn_agent(
            race=race,
            gender=gender,
            sub_lineage=sub_lineage,
            stage="ADULT",
            pos=pos_vec,
            role=role,
            title=title,
            initial_credits=initial_cr,
        )

    # 5 Ring 1 Cities: Spawn City Guard garrisons & residential populations
    print("[*] Spawning City Guard garrisons & Ring 1 racial city populations...")
    guards_per_city = 10
    total_guards = len(engine.city_layout.cities) * guards_per_city

    for cid in engine.city_layout.cities:
        engine.city_layout.spawn_city_guard_garrison(engine.agents, cid, count=guards_per_city)

    remaining = max(0, num_agents - plaza_cohort_size - 24 - total_guards)
    num_cities = len(engine.city_layout.cities)
    agents_per_city = remaining // num_cities if num_cities > 0 else 0
    remainder = remaining % num_cities if num_cities > 0 else 0

    other_races_map: dict[RaceId, list[RaceId]] = {
        "HUMAN": ["ELF", "DRAGON", "BEASTHUMAN", "DEMON"],
        "ELF": ["HUMAN", "DRAGON", "BEASTHUMAN", "DEMON"],
        "DRAGON": ["HUMAN", "ELF", "BEASTHUMAN", "DEMON"],
        "BEASTHUMAN": ["HUMAN", "ELF", "DRAGON", "DEMON"],
        "DEMON": ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN"],
    }

    for c_idx, (cid, city) in enumerate(engine.city_layout.cities.items()):
        native_race = city.native_race
        other_pool = other_races_map[native_race]
        city_buildings = [
            b
            for b in engine.city_layout.buildings.values()
            if b.city_id == cid
            and not b.for_sale
            and b.building_type not in ("GODMOTHER_PALACE", "CITY_GATE")
        ]
        bld_assign_idx = 0
        city_agent_count = agents_per_city + (1 if c_idx < remainder else 0)

        for i in range(city_agent_count):
            # 80-85% native race, 15-20% other races
            is_native = (i % 6) != 0  # 5 out of 6 = ~83.3%
            agent_race = native_race if is_native else other_pool[i % len(other_pool)]
            gender = genders[i % 2]
            sub_lineage = beasthuman_sublineages[i % 4] if agent_race == "BEASTHUMAN" else None
            role = roles[i % len(roles)]

            # Spawn within city living radius (r = 50m .. 210m)
            angle = (i * 0.45) % (2.0 * math.pi)
            dist = 50.0 + ((i * 13) % 150)
            px = city.center_x + dist * math.cos(angle)
            pz = city.center_z + dist * math.sin(angle)
            py = engine.city_layout._get_elevation(px, pz, city.elevation_y)

            title = role.replace("_", " ").title()
            initial_cr = (
                50.0 if role in ("MERCHANT", "BLACKSMITH") else (30.0 if is_native else 40.0)
            )

            agent = engine.spawn_agent(
                race=agent_race,
                gender=gender,
                sub_lineage=sub_lineage,
                stage="ADULT",
                pos=Vec3(x=round(px, 2), y=round(py, 2), z=round(pz, 2)),
                role=role,
                title=title,
                settlement_id=cid,
                initial_credits=initial_cr,
            )

            # Assign seed house if available
            if is_native and bld_assign_idx < len(city_buildings):
                target_bld = city_buildings[bld_assign_idx]
                target_bld.owner_id = agent.agent_id
                target_bld.owner_name = agent.display_name
                target_bld.for_sale = False
                agent.home_building_id = target_bld.building_id
                parcel_id = f"{target_bld.parcel_x}_{target_bld.parcel_z}"
                parcel = engine.property_mgr.parcels.get(parcel_id)
                if parcel:
                    parcel.owner_id = agent.agent_id
                    parcel.owner_type = "AGENT"
                    parcel.for_sale_price = None
                bld_assign_idx += 1

    # Convert leftover placeholder seed owners to clean unowned for-sale homes
    for bld in engine.city_layout.buildings.values():
        if bld.building_type in ("GODMOTHER_PALACE", "CITY_GATE", "WALL_SEGMENT"):
            continue
        if bld.owner_id and (
            bld.owner_id.startswith("citizen_") or bld.owner_id not in engine.agents
        ):
            bld.for_sale = True
            bld.owner_id = None
            bld.owner_name = None
            parcel_id = f"{bld.parcel_x}_{bld.parcel_z}"
            parcel = engine.property_mgr.parcels.get(parcel_id)
            if parcel:
                parcel.owner_id = None
                parcel.owner_type = "UNCLAIMED"
                parcel.for_sale_price = bld.sale_price

    # Calibrate WTC macro baseline to initial circulating money supply and population output
    initial_m = engine.bank.calculate_total_circulation(list(engine.agents.values()))
    initial_q = WTCExchange.estimate_real_output_q(len(engine.agents))
    engine.wtc.calibrate_baseline(initial_m, initial_q)
    print(
        f"[+] Calibrated WTC macro baseline: M0={initial_m:.1f}, Q0={initial_q:.1f}, "
        f"CPI={engine.wtc.cpi:.3f}"
    )

    print(f"[+] Spawned {len(engine.agents)} total living mortals, city guards & palace knights.")


class GaiaLauncher:
    """Coordinates lifecycle of SimulationEngine, GodotWebSocketBridge, and Godot 3D client."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.stop_event = asyncio.Event()
        self.godot_proc: subprocess.Popen[bytes] | None = None
        self.llm_proc: subprocess.Popen[Any] | None = None
        self.spawned_llm_proc: bool = False
        self.llm_online: bool = False
        self._llm_log_file: Any = None
        self._godot_log_file: Any = None
        self.engine: SimulationEngine | None = None
        self.bridge: GodotWebSocketBridge | None = None
        self.cli: RichGodConsole | None = None

    async def run(self) -> None:
        # 0. Manage Local llama-server Lifecycle
        should_enable_llm = self.args.llm
        if should_enable_llm is None:
            # Auto-detect: enabled if binary and model exist on disk
            should_enable_llm = os.path.exists(self.args.llm_bin) and os.path.exists(
                self.args.llm_model
            )

        if should_enable_llm:
            if await asyncio.to_thread(check_llm_health, host="127.0.0.1", port=self.args.llm_port):
                print(f"[+] Reusing existing healthy llama-server on port {self.args.llm_port}.")
                self.llm_online = True
                self.spawned_llm_proc = False
            else:
                if os.path.exists(self.args.llm_bin) and os.path.exists(self.args.llm_model):
                    log_dir = REPO_ROOT / "data" / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    log_file_path = log_dir / "llama_server.log"
                    self._llm_log_file = open(log_file_path, "a", buffering=1, encoding="utf-8")
                    llm_cmd = build_llama_server_cmd(
                        bin_path=self.args.llm_bin,
                        model_path=self.args.llm_model,
                        port=self.args.llm_port,
                        host="127.0.0.1",
                    )
                    print(f"[*] Spawning local llama-server on port {self.args.llm_port}...")
                    print(f"    Binary: {self.args.llm_bin}")
                    print(f"    Model:  {self.args.llm_model}")
                    print("    Logs:   data/logs/llama_server.log")
                    self.llm_proc = subprocess.Popen(
                        llm_cmd,
                        stdout=self._llm_log_file,
                        stderr=subprocess.STDOUT,
                        cwd=str(REPO_ROOT),
                    )
                    self.spawned_llm_proc = True
                    print(
                        f"[+] llama-server spawned (PID {self.llm_proc.pid}). "
                        "Waiting for /health..."
                    )

                    poll_start = time.time()
                    while (time.time() - poll_start) < 45.0:
                        if self.llm_proc.poll() is not None:
                            print(
                                f"[!] Warning: llama-server process exited unexpectedly "
                                f"(code {self.llm_proc.returncode})."
                            )
                            break
                        if await asyncio.to_thread(
                            check_llm_health, host="127.0.0.1", port=self.args.llm_port
                        ):
                            self.llm_online = True
                            break
                        await asyncio.sleep(0.5)

                    if self.llm_online:
                        elapsed = time.time() - poll_start
                        print(f"[+] Local llama-server is healthy and ready ({elapsed:.1f}s)!")
                    else:
                        print(
                            "[!] Warning: llama-server timed out waiting for /health; "
                            "continuing in offline fallback mode."
                        )
                else:
                    print(
                        f"[!] llama-server binary ({self.args.llm_bin}) or model "
                        f"({self.args.llm_model}) missing; running in offline fallback mode."
                    )
        else:
            print("[*] Local LLM disabled; running in offline fallback mode.")

        backend_str = (
            f"LIVE (Huihui-Qwen3.5-4B on port {self.args.llm_port})"
            if self.llm_online
            else "OFFLINE_FALLBACK"
        )
        print("=" * 70)
        print("✦ GAIA CIVILIZATION ENGINE: ONE-COMMAND LAUNCHER ✦")
        print(f"Agents: {self.args.agents} | Speed: {self.args.speed}x | Port: {self.args.port}")
        print(f"Headless Mode: {self.args.headless} | Divine LLM Brain: {backend_str}")
        print("=" * 70)

        # 1. Initialize Bridge & Engine
        capacity = max(2048, self.args.agents + 512)
        if self.args.fresh:
            db_p = Path(self.args.db_path)
            if db_p.exists():
                db_p.unlink()
            for ext in ("-wal", "-shm"):
                wal_p = db_p.with_name(db_p.name + ext)
                if wal_p.exists():
                    wal_p.unlink()
            cp_p = Path(self.args.checkpoints_dir)
            if cp_p.exists():
                shutil.rmtree(cp_p)
            gl_p = Path(self.args.god_ledger_dir)
            if gl_p.exists():
                shutil.rmtree(gl_p)

        self.bridge = GodotWebSocketBridge(
            host=self.args.host,
            port=self.args.port,
            initial_capacity=capacity,
        )

        heightmap_path = (
            Path(self.args.heightmap_path) if os.path.exists(self.args.heightmap_path) else None
        )
        self.engine = SimulationEngine(
            db_path=self.args.db_path,
            checkpoints_dir=self.args.checkpoints_dir,
            god_ledger_dir=self.args.god_ledger_dir,
            heightmap_path=heightmap_path,
            adapter=self.bridge,
            headless=self.args.headless,
            initial_capacity=capacity,
        )
        self.engine.speed = self.args.speed
        self.bridge.engine = self.engine

        # Wire LLM config into DivineLLMBrain
        llm_url = f"http://127.0.0.1:{self.args.llm_port}/v1/chat/completions"
        self.engine.divine_llm_brain.llm_url = llm_url
        self.engine.divine_llm_brain.model_name = self.args.llm_model
        self.engine.divine_llm_brain.active_model_name = "Huihui-Qwen3.5-4B"
        self.engine.divine_llm_brain.llm_online = self.llm_online

        self.cli = RichGodConsole(engine=self.engine)
        self.bridge.cli = self.cli

        # Checkpoint restore vs. fresh population spawn
        if not self.args.fresh and self.engine.has_verified_checkpoint():
            day, manifest, status_msg = self.engine.restore_from_checkpoint()
            print(
                f"[+] Restored persisted civilization: Day {day} ({status_msg}) — "
                f"{len(self.engine.agents)} agents"
            )
        else:
            spawn_initial_population(self.engine, self.args.agents)

        # 2. Start WebSocket Bridge server
        print(f"[*] Starting WebSocket server at ws://{self.args.host}:{self.args.port}...")
        await self.bridge.start_server_async()

        # Wait until port accepts connections
        attempts = 0
        while not check_port_open(self.args.host, self.args.port) and attempts < 20:
            await asyncio.sleep(0.1)
            attempts += 1

        if not check_port_open(self.args.host, self.args.port):
            print(f"[!] Warning: Port {self.args.port} not yet responding, continuing...")
        else:
            print(f"[+] WebSocket server ready on port {self.args.port}.")

        # 3. Launch Godot Client (unless headless)
        if not self.args.headless:
            godot_bin = shutil.which("godot")
            if godot_bin:
                print(f"[*] Launching Godot 4.7.2 3D client ({godot_bin})...")
                log_dir = REPO_ROOT / "data" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                godot_log_path = log_dir / "godot_client.log"
                self._godot_log_file = open(godot_log_path, "a", buffering=1, encoding="utf-8")
                self.godot_proc = subprocess.Popen(
                    [godot_bin, "--path", "godot_client"],
                    stdout=self._godot_log_file,
                    stderr=subprocess.STDOUT,
                )
                print(
                    f"[+] Godot process launched (PID {self.godot_proc.pid}). "
                    "Logs: data/logs/godot_client.log"
                )
            else:
                print("[!] 'godot' binary not found in PATH; running in headless mode.")

        # 4. Main Simulation Loop
        print("[*] Simulation running. Press Ctrl+C to trigger atomic save and clean shutdown.")
        self.engine.is_running = True
        tick_count = 0
        start_time = time.time()

        try:
            while not self.stop_event.is_set():
                # Check if Godot client closed
                if self.godot_proc and self.godot_proc.poll() is not None:
                    print("[*] Godot client window closed by user. Initiating clean shutdown...")
                    break

                # Check max duration limits if specified (evaluated even when paused)
                now = time.time()
                if (
                    self.args.duration_seconds > 0
                    and (now - start_time) >= self.args.duration_seconds
                ):
                    print(f"[*] Reached target duration ({self.args.duration_seconds}s).")
                    break

                # Respect Pause state: keep event loop responsive without advancing ticks
                if not self.engine.is_running:
                    await asyncio.sleep(0.05)
                    continue

                loop_start = time.perf_counter()

                # Step engine
                self.engine.step_tick()
                tick_count += 1

                # Broadcast binary agent positions to connected Godot clients
                if self.bridge.clients:
                    payload = self.bridge.pack_binary_frame()
                    await self.bridge.broadcast_binary_async(payload)

                # Broadcast WTC and Courthouse board updates on civic ticks
                if tick_count % CIVIC_TICK_INTERVAL_TICKS == 0:
                    self.bridge.emit_event(
                        "SIGN_UPDATE",
                        {
                            "board": "WTC",
                            "cpi": self.engine.wtc.cpi,
                            "money_supply": self.engine.bank.calculate_total_circulation(
                                list(self.engine.agents.values())
                            ),
                            "commodities": {
                                c: p for c, p in self.engine.wtc.current_prices.items()
                            },
                        },
                    )
                    active_cases = len(self.engine.judiciary.get_open_cases())
                    convictions = sum(
                        len(records) for records in self.engine.judiciary.criminal_records.values()
                    )
                    polities_count = len(self.engine.political_engine.polities)
                    self.bridge.emit_event(
                        "SIGN_UPDATE",
                        {
                            "board": "COURTHOUSE",
                            "active_cases": active_cases,
                            "convictions": convictions,
                            "polities_count": polities_count,
                            "status": "Court in Order",
                        },
                    )

                # Check max ticks if specified
                if self.args.max_ticks > 0 and tick_count >= self.args.max_ticks:
                    print(f"[*] Reached target max ticks ({self.args.max_ticks}).")
                    break

                # Sleep to match target speed (default 2 Hz = 0.5s / speed)
                base_interval = 0.5 / max(0.1, self.engine.speed)
                elapsed = time.perf_counter() - loop_start
                sleep_time = max(0.001, base_interval - elapsed)
                await asyncio.sleep(sleep_time)

        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n[*] Shutdown signal received.")
        finally:
            await self._shutdown(tick_count)

    async def _shutdown(self, tick_count: int) -> None:
        """Executes graceful shutdown and atomic World Goddess save."""
        print("[*] Executing graceful shutdown sequence...")

        # Terminate Godot process if active
        if self.godot_proc and self.godot_proc.poll() is None:
            print("[*] Closing Godot 3D client...")
            self.godot_proc.terminate()
            try:
                self.godot_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.godot_proc.kill()
        if hasattr(self, "_godot_log_file") and self._godot_log_file:
            try:
                self._godot_log_file.close()
            except OSError as exc:
                print(f"[!] Warning: failed to close Godot log file cleanly: {exc}")

        # Stop WebSocket bridge
        if self.bridge:
            print("[*] Stopping WebSocket bridge server...")
            await self.bridge.stop_server_async()

        # Perform atomic end-of-day checkpoint via World Goddess
        if self.engine and tick_count > 0:
            print("[*] Performing World Goddess atomic Two-Phase Commit checkpoint...")
            try:
                manifest = self.engine.commit_end_of_day()
                h = manifest.pt_sha256[:12]
                print(f"[+] Atomic commit verified (Day {manifest.day}, SHA-256: {h}...)")
            except Exception as e:
                print(f"[!] Commit error: {e}")

        # Terminate spawned llama-server if active
        if self.spawned_llm_proc and self.llm_proc and self.llm_proc.poll() is None:
            print(f"[*] Terminating spawned llama-server (PID {self.llm_proc.pid})...")
            self.llm_proc.terminate()
            try:
                self.llm_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                print("[!] llama-server did not terminate within 3s; killing...")
                self.llm_proc.kill()
        if hasattr(self, "_llm_log_file") and self._llm_log_file:
            try:
                self._llm_log_file.close()
            except OSError as exc:
                print(f"[!] Warning: failed to close LLM log file cleanly: {exc}")

        print("✦ GAIA ENGINE SAFELY SHUT DOWN ✦")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaia Civilization Engine Launcher")
    parser.add_argument("--agents", type=int, default=1500, help="Initial agent population count")
    parser.add_argument("--speed", type=float, default=1.0, help="Simulation speed (1x..60x)")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port for Godot bridge")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="WebSocket host address")
    parser.add_argument("--headless", action="store_true", help="Run headlessly without Godot")
    parser.add_argument("--max-ticks", type=int, default=0, help="Stop after N ticks (0=inf)")
    parser.add_argument("--duration-seconds", type=float, default=0.0, help="Stop after N s")
    parser.add_argument("--db-path", type=str, default="data/civilization.db", help="DB path")
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Force a fresh Day 1 world instead of restoring existing checkpoints",
    )
    parser.add_argument(
        "--checkpoints-dir", type=str, default="data/checkpoints", help="Daily checkpoints path"
    )
    parser.add_argument(
        "--god-ledger-dir", type=str, default="data/god_ledger", help="Daily God Ledger path"
    )
    parser.add_argument(
        "--heightmap-path", type=str, default="data/world_heightmap.npy", help="Heightmap path"
    )
    parser.add_argument(
        "--llm",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable local llama.cpp server for divine LLM brain (auto-detected if omitted)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf",
        help="Path to GGUF model for local llama-server",
    )
    parser.add_argument(
        "--llm-port",
        type=int,
        default=8080,
        help="Port for local llama-server (default: 8080)",
    )
    parser.add_argument(
        "--llm-bin",
        type=str,
        default="llama.cpp/build/bin/llama-server",
        help="Path to llama-server binary",
    )

    args = parser.parse_args()
    launcher = GaiaLauncher(args)

    # Set up signal handlers for clean SIGINT / SIGTERM
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal():
        launcher.stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(launcher.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
