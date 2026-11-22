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
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge  # noqa: E402
from sim_core.config import CIVIC_TICK_INTERVAL_TICKS, TICKS_PER_GAME_DAY  # noqa: E402
from sim_core.engine import SimulationEngine  # noqa: E402
from sim_core.god_console.cli import RichGodConsole  # noqa: E402
from sim_core.schemas import Gender, RaceId, Vec3  # noqa: E402


def check_port_open(host: str, port: int) -> bool:
    """Checks if a TCP port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False


def spawn_initial_population(engine: SimulationEngine, num_agents: int) -> None:
    """Populates world across 5 biomes, 5 races, 2 genders, and Beasthuman sub-lineages."""
    races: list[RaceId] = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
    genders: list[Gender] = ["BOY", "GIRL"]
    beasthuman_sublineages = ["CAT_KIN", "WOLF_KIN", "DWARF", "BARBARIAN"]

    biome_centers = [
        (-1800.0, 2000.0),   # Human plains
        (2200.0, 2000.0),    # Elf highlands
        (2500.0, -2500.0),   # Dragon peaks
        (-2500.0, -2500.0),  # Beasthuman taiga
        (-3500.0, 500.0),    # Demon crags
    ]

    print(f"[*] Spawning {num_agents} initial agents across 5 races & biomes...")
    for i in range(num_agents):
        race_idx = i % 5
        race = races[race_idx]
        gender = genders[i % 2]
        sub_lineage = beasthuman_sublineages[i % 4] if race == "BEASTHUMAN" else None

        cx, cz = biome_centers[race_idx]
        dist = 50.0 + (i % 40) * 12.0
        x = cx + dist * 0.7
        z = cz + dist * 0.7
        pos_vec = Vec3(x=x, y=0.0, z=z)

        engine.spawn_agent(
            race=race,
            gender=gender,
            sub_lineage=sub_lineage,
            stage="ADULT",
            pos=pos_vec,
            initial_credits=20.0,
        )

    print(f"[+] Spawned {len(engine.agents)} living mortals.")


class GaiaLauncher:
    """Coordinates lifecycle of SimulationEngine, GodotWebSocketBridge, and Godot 3D client."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.stop_event = asyncio.Event()
        self.godot_proc: subprocess.Popen[bytes] | None = None
        self.engine: SimulationEngine | None = None
        self.bridge: GodotWebSocketBridge | None = None
        self.cli: RichGodConsole | None = None

    async def run(self) -> None:
        print("=" * 70)
        print("✦ GAIA CIVILIZATION ENGINE: ONE-COMMAND LAUNCHER ✦")
        print(f"Agents: {self.args.agents} | Speed: {self.args.speed}x | Port: {self.args.port}")
        print(f"Headless Mode: {self.args.headless}")
        print("=" * 70)

        # 1. Initialize Bridge & Engine
        capacity = max(2048, self.args.agents + 512)
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

        self.cli = RichGodConsole(engine=self.engine)
        self.bridge.cli = self.cli

        # Spawn initial population
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
                self.godot_proc = subprocess.Popen(
                    [godot_bin, "--path", "godot_client"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"[+] Godot process launched (PID {self.godot_proc.pid}).")
            else:
                print("[!] 'godot' binary not found in PATH; running in headless mode.")

        # 4. Main Simulation Loop
        print("[*] Simulation running. Press Ctrl+C to trigger atomic save and clean shutdown.")
        self.engine.is_running = True
        tick_count = 0
        start_time = time.time()

        try:
            while not self.stop_event.is_set():
                loop_start = time.perf_counter()

                # Step engine
                self.engine.step_tick()
                tick_count += 1

                # Broadcast binary agent positions to connected Godot clients
                if self.bridge.clients:
                    payload = self.bridge.pack_binary_frame()
                    await self.bridge.broadcast_binary_async(payload)

                # Broadcast world time & weather every 2 ticks
                if tick_count % 2 == 0:
                    time_of_day = (
                        self.engine.current_tick % TICKS_PER_GAME_DAY
                    ) / TICKS_PER_GAME_DAY
                    season_progress = min(1.0, (self.engine.current_day % 120) / 120.0)
                    self.bridge.sync_weather_time(
                        day=self.engine.current_day,
                        time_of_day=time_of_day,
                        season_progress=season_progress,
                        weather="CLEAR",
                    )

                # Broadcast WTC market prices on civic ticks
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

                # Check max ticks / duration limits if specified
                if self.args.max_ticks > 0 and tick_count >= self.args.max_ticks:
                    print(f"[*] Reached target max ticks ({self.args.max_ticks}).")
                    break

                now = time.time()
                if (
                    self.args.duration_seconds > 0
                    and (now - start_time) >= self.args.duration_seconds
                ):
                    print(f"[*] Reached target duration ({self.args.duration_seconds}s).")
                    break

                # Check if Godot client closed
                if self.godot_proc and self.godot_proc.poll() is not None:
                    print("[*] Godot client window closed by user. Initiating clean shutdown...")
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
        "--checkpoints-dir", type=str, default="data/checkpoints", help="Daily checkpoints path"
    )
    parser.add_argument(
        "--god-ledger-dir", type=str, default="data/god_ledger", help="Daily God Ledger path"
    )
    parser.add_argument(
        "--heightmap-path", type=str, default="data/world_heightmap.npy", help="Heightmap path"
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
