"""
sim_core/bridge/godot_ws_bridge.py
WebSocket server bridge implementing WorldAdapter for Godot 4.7.2 client rendering,
Orbital God Map binary streaming, and discrete JSON divine event synchronization.
Follows ARCHITECTURE.md Section 4 and GODOT_CLIENT_AND_ASSETS_SPEC.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from sim_core.bridge.base import WorldAdapter
from sim_core.schemas import (
    CommitProposal,
    FatalityRecord,
    Vec3,
    WorldLibraryEntry,
)

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine

logger = logging.getLogger(__name__)

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8765
MAX_JSON_FRAME_BYTES: Final[int] = 65536  # 64 KB limit
SLAB_SIZE: Final[int] = 2048

# Race and stage mappings for binary stream (<f4)
RACE_TO_FLOAT: Final[dict[str, float]] = {
    "HUMAN": 0.0,
    "ELF": 1.0,
    "DRAGON": 2.0,
    "BEASTHUMAN": 3.0,
    "DEMON": 4.0,
}
FLOAT_TO_RACE: Final[dict[int, str]] = {
    0: "HUMAN",
    1: "ELF",
    2: "DRAGON",
    3: "BEASTHUMAN",
    4: "DEMON",
}

STAGE_TO_FLOAT: Final[dict[str, float]] = {
    "INFANT": 0.0,
    "CHILD": 1.0,
    "ADULT": 2.0,
    "ELDER": 3.0,
}
FLOAT_TO_STAGE: Final[dict[int, str]] = {
    0: "INFANT",
    1: "CHILD",
    2: "ADULT",
    3: "ELDER",
}

# Packed flag bits (stored as float32 in slot index 5)
FLAG_CRYING: Final[int] = 1 << 0       # 1
FLAG_IS_ORACLE: Final[int] = 1 << 1    # 2
FLAG_TRUE_DRAGON: Final[int] = 1 << 2  # 4
FLAG_INJURED: Final[int] = 1 << 3      # 8
FLAG_ILLNESS: Final[int] = 1 << 4      # 16
FLAG_IN_COMBAT: Final[int] = 1 << 5    # 32
FLAG_PRAYING: Final[int] = 1 << 6      # 64


class GodotWebSocketBridge(WorldAdapter):
    """
    WebSocket IPC Bridge connecting Python core to Godot 4.7.2.
    - High-frequency outbound binary stream (PackedFloat32Array, 6 floats/agent = 24 bytes).
    - Low-frequency discrete JSON events and divine controls.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        engine: SimulationEngine | None = None,
        initial_capacity: int = SLAB_SIZE,
    ) -> None:
        self.host = host
        self.port = port
        self.engine = engine

        # Connected WebSocket clients
        self.clients: set[Any] = set()
        self.server: Any = None
        self._server_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Vectorized contiguous position and attribute buffer for binary packing
        self.capacity: int = initial_capacity
        self.positions: np.ndarray = np.zeros((self.capacity, 6), dtype="<f4")
        self.active_mask: np.ndarray = np.zeros(self.capacity, dtype=bool)
        self.slot_to_agent_id: dict[int, str] = {}
        self.agent_id_to_slot: dict[str, int] = {}
        self.cli: Any = None

    def get_book_state_payload(self) -> dict[str, Any]:
        """Packs world_library and divine_codex state + pending proposals."""
        gov = self.engine.governance_engine if self.engine else None
        if not gov:
            return {
                "type": "BOOK_STATE_SYNC",
                "library_entries": [],
                "library_proposals": [],
                "codex_entries": [],
                "codex_proposals": [],
                "live_overrides": {},
            }
        return {
            "type": "BOOK_STATE_SYNC",
            "library_entries": [e.model_dump() for e in gov.library_entries.values()],
            "library_proposals": [p.model_dump() for p in gov.library_proposals.values()],
            "codex_entries": [e.model_dump() for e in gov.codex_entries.values()],
            "codex_proposals": [p.model_dump() for p in gov.codex_proposals.values()],
            "live_overrides": dict(gov.live_engine_overrides),
        }

    # =========================================================================
    # Buffer Management & Capacity Slabs
    # =========================================================================

    def _ensure_capacity(self, required_slot: int) -> None:
        """Expands contiguous float32 buffer in 2,048-slot slabs without hard cap."""
        if required_slot >= self.capacity:
            slabs_needed = ((required_slot - self.capacity) // SLAB_SIZE) + 1
            extra = slabs_needed * SLAB_SIZE
            new_capacity = self.capacity + extra
            self.positions = np.concatenate(
                [self.positions, np.zeros((extra, 6), dtype="<f4")], axis=0
            )
            self.active_mask = np.concatenate(
                [self.active_mask, np.zeros(extra, dtype=bool)], axis=0
            )
            self.capacity = new_capacity

    # =========================================================================
    # WorldAdapter Implementations
    # =========================================================================

    def spawn_agent(self, agent_id: str, slot_idx: int, metadata: dict[str, Any]) -> None:
        """Registers and materializes an agent slot in the contiguous binary buffer."""
        self._ensure_capacity(slot_idx)
        self.active_mask[slot_idx] = True
        self.slot_to_agent_id[slot_idx] = agent_id
        self.agent_id_to_slot[agent_id] = slot_idx

        race_str = metadata.get("race", "HUMAN")
        stage_str = metadata.get("stage", "INFANT")
        x = float(metadata.get("x", 0.0))
        y = float(metadata.get("y", 0.0))
        z = float(metadata.get("z", 0.0))

        flags = 0
        if metadata.get("crying", False):
            flags |= FLAG_CRYING
        if metadata.get("is_oracle", False):
            flags |= FLAG_IS_ORACLE
        if metadata.get("dragon_form") == "TRUE_DRAGON":
            flags |= FLAG_TRUE_DRAGON
        if float(metadata.get("injured", 0.0)) > 0.0:
            flags |= FLAG_INJURED
        if float(metadata.get("illness", 0.0)) > 0.0:
            flags |= FLAG_ILLNESS

        self.positions[slot_idx, 0] = x
        self.positions[slot_idx, 1] = y
        self.positions[slot_idx, 2] = z
        self.positions[slot_idx, 3] = RACE_TO_FLOAT.get(race_str, 0.0)
        self.positions[slot_idx, 4] = STAGE_TO_FLOAT.get(stage_str, 0.0)
        self.positions[slot_idx, 5] = float(flags)

    def despawn_agent(self, agent_id: str, slot_idx: int, reason: str = "DEATH") -> None:
        """Removes an agent from the active binary buffer on death or escheatment."""
        if slot_idx < self.capacity:
            self.active_mask[slot_idx] = False
            self.positions[slot_idx].fill(0.0)
        self.slot_to_agent_id.pop(slot_idx, None)
        self.agent_id_to_slot.pop(agent_id, None)

    def update_agent_position(
        self,
        slot_idx: int,
        x: float,
        y: float,
        z: float,
        yaw: float = 0.0,
        packed_flags: int = 0,
    ) -> None:
        """Fast O(1) buffer slot position mutation."""
        if slot_idx < self.capacity:
            self.positions[slot_idx, 0] = x
            self.positions[slot_idx, 1] = y
            self.positions[slot_idx, 2] = z
            if packed_flags != 0:
                self.positions[slot_idx, 5] = float(packed_flags)

    def sync_bubble(self, pooled_agents: list[dict[str, Any]]) -> None:
        """Dispatches BUBBLE_SYNC JSON event for the 60-120 pooled 3D rigs."""
        self.emit_event("BUBBLE_SYNC", {"agents": pooled_agents})

    def sync_weather_time(
        self,
        day: int,
        time_of_day: float,
        season_progress: float,
        weather: str = "CLEAR",
    ) -> None:
        """Dispatches WORLD_TIME_WEATHER JSON event for Sky3D and global shaders."""
        self.emit_event(
            "WORLD_TIME_WEATHER",
            {
                "day": day,
                "time_of_day": time_of_day,
                "season_progress": season_progress,
                "weather": weather,
            },
        )

    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Emits a discrete JSON event to all connected Godot clients."""
        msg = {"type": event_type, **payload}
        self.send_json_broadcast(msg)

    def broadcast_binary_frame(self, data: bytes) -> None:
        """Sends raw PackedFloat32Array bytes to all connected clients."""
        if not self.clients:
            return
        for client in list(self.clients):
            try:
                asyncio.create_task(client.send(data))
            except RuntimeError:
                pass

    # =========================================================================
    # High-Performance Binary Serialization (< 2.0 ms)
    # =========================================================================

    def pack_binary_frame(self) -> bytes:
        """
        Packs all active agents into contiguous little-endian float32 bytes.
        Returns N * 6 * 4 = 24 * N bytes (240 KB for 10,000 agents).
        """
        active_arr = self.positions[self.active_mask]
        return active_arr.tobytes()

    @staticmethod
    def pack_from_array(arr: np.ndarray) -> bytes:
        """Directly packs an (N, 6) float32 array into little-endian bytes."""
        if arr.dtype != np.dtype("<f4"):
            arr = arr.astype("<f4", copy=False)
        return arr.tobytes()

    @staticmethod
    def unpack_binary_frame(data: bytes) -> np.ndarray:
        """Unpacks raw little-endian bytes back into an (N, 6) float32 array."""
        if len(data) == 0:
            return np.empty((0, 6), dtype="<f4")
        return np.frombuffer(data, dtype="<f4").reshape(-1, 6)

    # =========================================================================
    # JSON Messaging Helpers
    # =========================================================================

    def send_json_broadcast(self, msg: dict[str, Any]) -> None:
        """Non-blocking broadcast of a JSON payload to all connected clients."""
        if not self.clients:
            return
        payload = json.dumps(msg)
        for client in list(self.clients):
            try:
                asyncio.create_task(client.send(payload))
            except RuntimeError:
                pass

    async def broadcast_binary_async(self, data: bytes) -> None:
        """Async broadcast of binary frames."""
        if not self.clients:
            return
        for client in list(self.clients):
            try:
                await client.send(data)
            except Exception:
                pass

    async def broadcast_json_async(self, msg: dict[str, Any]) -> None:
        """Async broadcast of JSON payloads."""
        if not self.clients:
            return
        payload = json.dumps(msg)
        for client in list(self.clients):
            try:
                await client.send(payload)
            except Exception:
                pass

    # =========================================================================
    # Inbound Message Dispatch & Authorization
    # =========================================================================

    async def handle_inbound_message(self, client: Any, raw_msg: str | bytes) -> None:
        """
        Dispatches inbound WebSocket frames from Godot:
        - Rejects frames exceeding MAX_JSON_FRAME_BYTES safely through ErrorHealer.
        - Routes GOD_* commands, Two-Book governance edits, and presence updates.
        """
        if isinstance(raw_msg, bytes):
            # Incoming binary messages from Godot are currently unexpected
            return

        if len(raw_msg) > MAX_JSON_FRAME_BYTES:
            err = ValueError(f"Frame length {len(raw_msg)} exceeds limit {MAX_JSON_FRAME_BYTES}")
            if self.engine:
                self.engine.healer.handle(
                    fault_class="WS_BRIDGE_DROP",
                    day=self.engine.current_day,
                    tick=self.engine.current_tick,
                    context={"error": str(err)},
                )
            await client.send(json.dumps({"type": "ERROR", "error": "Frame exceeds max size"}))
            return

        try:
            data = json.loads(raw_msg)
        except Exception as exc:
            if self.engine:
                self.engine.healer.handle(
                    fault_class="WS_BRIDGE_DROP",
                    day=self.engine.current_day,
                    tick=self.engine.current_tick,
                    context={"error": str(exc)},
                )
            await client.send(json.dumps({"type": "ERROR", "error": "Malformed JSON frame"}))
            return

        msg_type = data.get("type", "")

        try:
            if msg_type == "CLIENT_HANDSHAKE":
                await client.send(
                    json.dumps(
                        {
                            "type": "HANDSHAKE_ACK",
                            "status": "CONNECTED",
                            "server": "GAIA_CIVILIZATION_ENGINE",
                            "version": "3.0.0",
                        }
                    )
                )
                await client.send(json.dumps(self.get_book_state_payload()))
            elif msg_type == "REQUEST_BOOK_STATE_SYNC":
                await client.send(json.dumps(self.get_book_state_payload()))
            elif msg_type == "GOD_STATE":
                await self._handle_god_state(client, data)
            elif msg_type == "GOD_LIBRARY_EDIT":
                await self._handle_god_library_edit(client, data)
            elif msg_type == "GOD_CODEX_EDIT":
                await self._handle_god_codex_edit(client, data)
            elif msg_type == "GOD_CODEX_APPROVE":
                await self._handle_god_codex_approve(client, data)
            elif msg_type == "GOD_CODEX_REJECT":
                await self._handle_god_codex_reject(client, data)
            elif msg_type == "GOD_COMMAND":
                await self._handle_god_command(client, data)
            else:
                err = ValueError(f"Unknown message type '{msg_type}'")
                if self.engine:
                    self.engine.healer.handle(
                        fault_class="WS_BRIDGE_DROP",
                        day=self.engine.current_day,
                        tick=self.engine.current_tick,
                        context={"error": str(err)},
                    )
                await client.send(
                    json.dumps({"type": "ERROR", "error": f"Unknown message type '{msg_type}'"})
                )
        except Exception as exc:
            if self.engine:
                self.engine.healer.handle(
                    fault_class="WS_BRIDGE_DROP",
                    day=self.engine.current_day,
                    tick=self.engine.current_tick,
                    context={"error": str(exc)},
                )
            await client.send(
                json.dumps({"type": "ERROR", "error": f"Internal handler error: {exc}"})
            )

    async def _handle_god_state(self, client: Any, data: dict[str, Any]) -> None:
        """Updates God avatar coordinates, altitude, and presence state."""
        x = float(data.get("x", 0.0))
        y = float(data.get("y", 0.0))
        z = float(data.get("z", 0.0))

        if self.engine:
            self.engine.god_avatar_pos = Vec3(x=x, y=y, z=z)
            self.engine.god_presence.set_active(True, self.engine.current_tick)

        await client.send(
            json.dumps(
                {"type": "GOD_STATE_ACK", "status": "ACTIVE", "pos": {"x": x, "y": y, "z": z}}
            )
        )

    async def _handle_god_library_edit(self, client: Any, data: dict[str, Any]) -> None:
        """
        Applies direct God edit to World Library strictly in RAM.
        Zero mid-day SQLite writes.
        """
        topic = data.get("topic", "")
        volume_title = data.get("volume_title", "Divine Canonical Volume")
        author_id = data.get("author_id", "GOD")
        text_content = data.get("text_content", "")

        if not self.engine:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_LIBRARY_EDIT_RESPONSE",
                        "status": "FAILURE",
                        "reason": "Engine offline",
                    }
                )
            )
            return

        proposal = CommitProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
            tick=self.engine.current_tick,
            actor_id="GOD",
            kind="LIBRARY_ENTRY",
            bypass_god_check=True,
            payload={
                "topic": topic,
                "volume_title": volume_title,
                "author_id": author_id,
                "text_content": text_content,
            },
        )
        verdict = self.engine.world_goddess.evaluate(proposal)

        if verdict.status == "SUCCESS":
            entry = WorldLibraryEntry(
                entry_id=f"lib_{topic}",
                topic=topic,
                title=volume_title,
                summary=text_content,
                author_id=author_id,
                author_proficiency=1.0,
                created_tick=self.engine.current_tick,
            )
            self.engine.governance_engine.write_library_direct_god(entry)

        await client.send(
            json.dumps(
                {
                    "type": "GOD_LIBRARY_EDIT_RESPONSE",
                    "status": verdict.status,
                    "reason": verdict.reason,
                    "topic": topic,
                }
            )
        )
        if verdict.status == "SUCCESS":
            self.broadcast_book_state(exclude=client)

    async def _handle_god_codex_edit(self, client: Any, data: dict[str, Any]) -> None:
        """Direct God decree or live parameter override in RAM."""
        decree_id = data.get("decree_id", f"decree_{uuid.uuid4().hex[:8]}")
        text_decree = data.get("text_decree", "")
        parameter_key = data.get("parameter_key")
        parameter_val = data.get("parameter_val")

        if not self.engine:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_CODEX_EDIT_RESPONSE",
                        "status": "FAILURE",
                        "reason": "Engine offline",
                    }
                )
            )
            return

        proposal = CommitProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
            tick=self.engine.current_tick,
            actor_id="GOD",
            kind="DIVINE_CODEX_DECREE",
            bypass_god_check=True,
            payload={
                "decree_id": decree_id,
                "text_decree": text_decree,
                "parameter_key": parameter_key,
                "parameter_val": parameter_val,
            },
        )
        verdict = self.engine.world_goddess.evaluate(proposal)

        if verdict.status == "SUCCESS":
            self.engine.governance_engine.write_codex_direct_god(
                title=decree_id,
                text=text_decree,
                category="DECREE",
                current_tick=self.engine.current_tick,
                parameter_key=parameter_key,
                parameter_value=parameter_val,
            )

        await client.send(
            json.dumps(
                {
                    "type": "GOD_CODEX_EDIT_RESPONSE",
                    "status": verdict.status,
                    "reason": verdict.reason,
                    "decree_id": decree_id,
                }
            )
        )
        if verdict.status == "SUCCESS":
            self.broadcast_book_state(exclude=client)

    async def _handle_god_codex_approve(self, client: Any, data: dict[str, Any]) -> None:
        """Approves a pending Divine Codex proposal submitted by Goddess/Daughters."""
        proposal_id = data.get("proposal_id", "")

        if not self.engine:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_CODEX_APPROVE_RESPONSE",
                        "status": "FAILURE",
                        "reason": "Engine offline",
                    }
                )
            )
            return

        success, reason, _ = self.engine.governance_engine.approve_codex_proposal_by_god(
            proposal_id=proposal_id, current_tick=self.engine.current_tick
        )

        await client.send(
            json.dumps(
                {
                    "type": "GOD_CODEX_APPROVE_RESPONSE",
                    "status": "SUCCESS" if success else "FAILURE",
                    "proposal_id": proposal_id,
                    "reason": reason,
                }
            )
        )
        if success:
            self.broadcast_book_state(exclude=client)

    async def _handle_god_codex_reject(self, client: Any, data: dict[str, Any]) -> None:
        """Rejects a pending Divine Codex proposal submitted by Goddess/Daughters."""
        proposal_id = data.get("proposal_id", "")

        if not self.engine:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_CODEX_REJECT_RESPONSE",
                        "status": "FAILURE",
                        "reason": "Engine offline",
                    }
                )
            )
            return

        success, reason, _ = self.engine.governance_engine.reject_codex_proposal_by_god(
            proposal_id=proposal_id, current_tick=self.engine.current_tick
        )

        await client.send(
            json.dumps(
                {
                    "type": "GOD_CODEX_REJECT_RESPONSE",
                    "status": "SUCCESS" if success else "FAILURE",
                    "proposal_id": proposal_id,
                    "reason": reason,
                }
            )
        )
        if success:
            self.broadcast_book_state(exclude=client)

    async def _handle_god_command(self, client: Any, data: dict[str, Any]) -> None:
        """Executes miscellaneous divine interventions and runtime controls."""
        raw_cmd = data.get("raw_command")
        if raw_cmd:
            if not self.cli and self.engine:
                from sim_core.god_console.cli import GodConsoleCLI

                self.cli = GodConsoleCLI(engine=self.engine)
            output_text = self.cli.execute_command(raw_cmd) if self.cli else "CLI engine offline"
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND_RESULT",
                        "command": raw_cmd,
                        "output": output_text,
                        "status": "SUCCESS",
                    }
                )
            )
            return

        cmd = data.get("command", "")
        details: dict[str, Any] = {}

        if not self.engine:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND_RESPONSE",
                        "command": cmd,
                        "status": "FAILURE",
                        "reason": "Engine offline",
                    }
                )
            )
            return

        if cmd == "speed":
            speed_val = float(data.get("speed", 1.0))
            self.engine.set_speed(speed_val)
            details["speed"] = self.engine.speed
        elif cmd == "pause":
            self.engine.is_running = False
            details["is_running"] = False
        elif cmd == "resume":
            self.engine.is_running = True
            details["is_running"] = True
        elif cmd == "name_deity":
            slot = data.get("slot", "")
            name = data.get("name", "")
            self.engine.divine_hierarchy.bestow_name(slot, name)
            prop = CommitProposal(
                proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                tick=self.engine.current_tick,
                actor_id="GOD",
                kind="NAME_DEITY",
                bypass_god_check=True,
                payload={"slot": slot, "bestowed_name": name},
            )
            self.engine.world_goddess.evaluate(prop)
            details["slot"] = slot
            details["bestowed_name"] = name
        elif cmd == "decree":
            msg = data.get("message", "")
            entry = self.engine.ledger_pipeline.record_deity_message(
                entry_id=f"decree_{uuid.uuid4().hex[:8]}",
                day=self.engine.current_day,
                tick=self.engine.current_tick,
                category="MILESTONE",
                deity_slot=None,
                speaker_name="God",
                message=msg,
            )
            details["entry_id"] = entry.entry_id
        elif cmd == "save":
            manifest = self.engine.commit_end_of_day()
            details["day"] = manifest.day
            details["status"] = manifest.status
        elif cmd == "step":
            ticks = int(data.get("ticks", 1))
            for _ in range(ticks):
                self.engine.step_tick()
            details["current_tick"] = self.engine.current_tick
        elif cmd == "bless":
            agent_id = data.get("agent_id")
            if agent_id and agent_id in self.engine.agents:
                ag = self.engine.agents[agent_id]
                ag.health = ag.max_health
                ag.hunger = 100.0
                ag.distress = 0.0
                ag.crying = False
                ag.injured = 0.0
                ag.illness = 0.0
                details["blessed_agent_id"] = agent_id
        elif cmd == "smite":
            agent_id = data.get("agent_id")
            if agent_id and agent_id in self.engine.agents:
                ag = self.engine.agents[agent_id]
                ag.alive = False
                self.despawn_agent(agent_id, ag.slot_idx, reason="SMITTEN")
                fatality = FatalityRecord(
                    agent_id=ag.agent_id,
                    display_name=ag.display_name,
                    race=ag.race,
                    sub_lineage=ag.sub_lineage,
                    secondary_heritage_race=ag.secondary_heritage_race,
                    age_ticks=ag.age_ticks,
                    stage_at_death=ag.stage,
                    cause="DIVINE_SMITE",
                    season=self.engine.current_season,
                    death_day=self.engine.current_day,
                    death_tick=self.engine.current_tick,
                )
                self.engine.judiciary.record_fatality(fatality)
                details["smitten_agent_id"] = agent_id
        else:
            await client.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND_RESPONSE",
                        "command": cmd,
                        "status": "FAILURE",
                        "reason": f"Unknown command '{cmd}'",
                    }
                )
            )
            return

        await client.send(
            json.dumps(
                {
                    "type": "GOD_COMMAND_RESPONSE",
                    "command": cmd,
                    "status": "SUCCESS",
                    "details": details,
                }
            )
        )

    # =========================================================================
    # Server Lifecycle & Connection Handling
    # =========================================================================

    def broadcast_book_state(self, exclude: Any = None) -> None:
        """Broadcasts BOOK_STATE_SYNC to connected clients."""
        payload = self.get_book_state_payload()
        msg = json.dumps(payload)
        for c in list(self.clients):
            if c != exclude:
                try:
                    asyncio.create_task(c.send(msg))
                except Exception:
                    pass

    async def _client_handler(self, websocket: Any) -> None:
        """Handles single WebSocket connection lifecycle."""
        self.clients.add(websocket)
        if self.engine:
            self.engine.god_presence.set_active(True, self.engine.current_tick)

        try:
            async for message in websocket:
                await self.handle_inbound_message(websocket, message)
        except Exception as exc:
            # Route socket drops or communication failures to ErrorHealer
            if self.engine:
                self.engine.healer.handle(
                    fault_class="WS_BRIDGE_DROP",
                    day=self.engine.current_day,
                    tick=self.engine.current_tick,
                    context={"error": str(exc)},
                )
        finally:
            self.clients.discard(websocket)
            if not self.clients and self.engine:
                self.engine.god_presence.set_active(False)

    async def start_server_async(self) -> None:
        """Starts the WebSocket server listening on configured host/port."""
        try:
            from websockets.asyncio.server import serve as ws_serve
        except ImportError:
            from websockets.server import serve as ws_serve  # type: ignore

        self.server = await ws_serve(self._client_handler, self.host, self.port)

    async def stop_server_async(self) -> None:
        """Closes server and disconnects active clients cleanly."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        self.clients.clear()
        if self.engine:
            self.engine.god_presence.set_active(False)
