"""
sim_core/world/palace_security.py
Grand Divine Palace Acropolis Security, Twin Guardian Dragons & Entry Permission State Machine,
Palace Knight Battalion Patrols & Judiciary Integration.
Follows AGENTS.md Sprint 2 specifications.
"""

from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Final, Literal

from sim_core.brains.personality import MoodState, generate_personality_vector
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.schemas import (
    AgentRecord,
    PalaceDecision,
    PalaceEntryRequest,
    PalacePass,
    Vec3,
)
from sim_core.society.religion import get_agent_devotion

if TYPE_CHECKING:
    from sim_core.bridge.base import WorldAdapter
    from sim_core.divine.god_ledger import GodLedgerPipeline, GodPresenceTracker
    from sim_core.engine import SimulationEngine
    from sim_core.persistence.world_goddess import WorldGoddessCritic
    from sim_core.society.judiciary import JudiciaryEngine

# =============================================================================
# Spatial & Security Threshold Constants
# =============================================================================

PALACE_CENTER_X: Final[float] = 0.0
PALACE_CENTER_Y: Final[float] = 32.0
PALACE_CENTER_Z: Final[float] = 0.0

MAIN_GATE_X: Final[float] = 0.0
MAIN_GATE_Y: Final[float] = 32.0
MAIN_GATE_Z: Final[float] = 38.0

DRAGON_LEFT_X: Final[float] = -12.0
DRAGON_LEFT_Y: Final[float] = 32.0
DRAGON_LEFT_Z: Final[float] = 38.0

DRAGON_RIGHT_X: Final[float] = 12.0
DRAGON_RIGHT_Y: Final[float] = 32.0
DRAGON_RIGHT_Z: Final[float] = 38.0

GATE_THRESHOLD_RADIUS: Final[float] = 35.0  # Mortal petition halt radius
INNER_PALACE_RADIUS: Final[float] = 95.0  # Restricted sanctum radius
FEAR_AURA_RADIUS: Final[float] = 40.0  # Twin dragon terror aura radius
OUTER_BOUNDARY_RADIUS: Final[float] = 130.0  # Cleared escort drop-off radius

DELEGATION_TIMEOUT_TICKS: Final[int] = 30  # Auto-escalation timeout to Goddess
DEFAULT_PASS_DURATION_TICKS: Final[int] = 600  # 10 minutes game time

WHITELIST_DEITIES: Final[set[str]] = {
    "god_avatar",
    "world_goddess",
    "gm_human",
    "gm_elf",
    "gm_dragon",
    "gm_beasthuman",
    "gm_demon",
}


class PalaceSecurityEngine:
    """
    Manages security for the Grand Divine Palace Acropolis:
    - Twin Guardian Dragons flanking Main Palace Gate (x = ±12m, y = 32m, z = 38m).
    - Entry Permission State Machine:
      - BYPASS: God avatar, World Goddess, 5 God-Mothers, on-duty Palace Knights.
      - HALT_AND_REQUEST: Mortals in 35m gate zone halted; routed to God (if active) or Goddess.
      - TRESPASS / HOSTILE: 40m fear aura, Palace Knight interception, and judiciary arrest.
    - Palace Knight Battalion (20-24 guards) patrolling perimeter, courtyard, and road gates.
    """

    def __init__(
        self,
        engine: SimulationEngine | None = None,
        god_presence: GodPresenceTracker | None = None,
        ledger_pipeline: GodLedgerPipeline | None = None,
        world_goddess: WorldGoddessCritic | None = None,
        judiciary: JudiciaryEngine | None = None,
        adapter: WorldAdapter | None = None,
    ) -> None:
        self.engine = engine
        self._god_presence = god_presence
        self._ledger_pipeline = ledger_pipeline
        self._world_goddess = world_goddess
        self._judiciary = judiciary
        self._adapter = adapter

        # Passes & Petitions state
        self.active_passes: dict[str, PalacePass] = {}  # agent_id -> PalacePass
        self.pending_requests: dict[str, PalaceEntryRequest] = {}  # request_id -> request
        self.agent_to_request: dict[str, str] = {}  # agent_id -> request_id
        self.historical_requests: list[PalaceEntryRequest] = []

        # Battalion management
        self.knight_agent_ids: list[str] = []
        self.knight_roles: dict[str, str] = {}  # agent_id -> role type
        self.knight_waypoints: dict[str, list[tuple[float, float]]] = {}  # agent_id -> [(x, z)]
        self.knight_waypoint_idx: dict[str, int] = {}
        self.knight_targets: dict[str, tuple[str, str]] = {}  # knight_id -> (target_id, mode)

        # Track alerted trespassers to avoid filing duplicate judiciary cases per tick
        self.reported_trespassers: set[str] = set()

    # =========================================================================
    # Property Accessors with Fallbacks
    # =========================================================================

    @property
    def god_presence(self) -> GodPresenceTracker | None:
        if self._god_presence is not None:
            return self._god_presence
        return self.engine.god_presence if self.engine else None

    @property
    def ledger_pipeline(self) -> GodLedgerPipeline | None:
        if self._ledger_pipeline is not None:
            return self._ledger_pipeline
        return self.engine.ledger_pipeline if self.engine else None

    @property
    def world_goddess(self) -> WorldGoddessCritic | None:
        if self._world_goddess is not None:
            return self._world_goddess
        return self.engine.world_goddess if self.engine else None

    @property
    def judiciary(self) -> JudiciaryEngine | None:
        if self._judiciary is not None:
            return self._judiciary
        return self.engine.judiciary if self.engine else None

    @property
    def adapter(self) -> WorldAdapter | None:
        if self._adapter is not None:
            return self._adapter
        return self.engine.adapter if self.engine else None

    # =========================================================================
    # Whitelist & Pass Verification
    # =========================================================================

    def is_whitelisted(self, agent: AgentRecord | str) -> bool:
        """Returns True if the entity is exempt from Palace security restrictions."""
        if isinstance(agent, str):
            agent_id = agent
            if agent_id in WHITELIST_DEITIES:
                return True
            if self.engine and agent_id in self.engine.agents:
                return self.is_whitelisted(self.engine.agents[agent_id])
            return False

        if agent.agent_id in WHITELIST_DEITIES:
            return True
        if agent.role == "PALACE_KNIGHT":
            return True
        return False

    def has_active_pass(self, agent_id: str, current_tick: int) -> bool:
        """Returns True if agent currently possesses a valid, non-expired PalacePass."""
        pass_record = self.active_passes.get(agent_id)
        if pass_record is None:
            return False
        if current_tick > pass_record.expires_tick:
            # Pass has expired
            del self.active_passes[agent_id]
            return False
        return True

    # =========================================================================
    # Petition Submission & Adjudication
    # =========================================================================

    def request_entry(
        self,
        agent: AgentRecord,
        current_tick: int,
        reason: str = "Seeking Divine Audience",
    ) -> PalaceEntryRequest:
        """Generates a structured entry petition for a mortal arriving at the Gate Zone."""
        existing_req_id = self.agent_to_request.get(agent.agent_id)
        if existing_req_id and existing_req_id in self.pending_requests:
            return self.pending_requests[existing_req_id]

        crimes = 0
        if self.judiciary and agent.agent_id in self.judiciary.criminal_records:
            crimes = len(self.judiciary.criminal_records[agent.agent_id])

        # Devotion affinity combining base devotion with patron affinity cleanly
        base_devotion = get_agent_devotion(agent)
        patron_affinity = 0.5
        if (
            agent.patron_godmother_slot
            and agent.patron_godmother_slot in agent.godmother_affinities
        ):
            patron_affinity = agent.godmother_affinities[agent.patron_godmother_slot]
        elif "world_goddess" in agent.godmother_affinities:
            patron_affinity = agent.godmother_affinities["world_goddess"]
        devotion = 0.5 * base_devotion + 0.5 * patron_affinity

        req_id = f"req_{agent.agent_id}_{uuid.uuid4().hex[:6]}"
        request = PalaceEntryRequest(
            request_id=req_id,
            agent_id=agent.agent_id,
            name=agent.display_name,
            race=agent.race,
            title=agent.title,
            criminal_count=crimes,
            faith_devotion=round(devotion, 2),
            reason=reason,
            tick=current_tick,
            status="PENDING",
        )

        self.pending_requests[req_id] = request
        self.agent_to_request[agent.agent_id] = req_id

        # If God is active, broadcast immediately to Godot Divine HUD
        is_god_active = self.god_presence.is_active if self.god_presence else False
        if is_god_active and self.adapter:
            self.adapter.emit_event("PALACE_ENTRY_REQUEST", request.model_dump())

        return request

    def resolve_request(
        self,
        request_id: str,
        decision: PalaceDecision,
        decided_by: Literal["GOD", "WORLD_GODDESS"] = "GOD",
        current_tick: int = 0,
        duration_ticks: int = DEFAULT_PASS_DURATION_TICKS,
    ) -> PalaceEntryRequest | None:
        """Applies a decision (GRANT / DENY / ESCORT) to a pending petition."""
        req = self.pending_requests.pop(request_id, None)
        if not req:
            return None

        self.agent_to_request.pop(req.agent_id, None)
        day = (current_tick // TICKS_PER_GAME_DAY) + 1 if current_tick > 0 else 1
        authority_label = decided_by.replace("_", " ").title()

        if decision == "GRANT":
            req.status = "GRANTED"
            new_pass = PalacePass(
                pass_id=f"pass_{uuid.uuid4().hex[:8]}",
                agent_id=req.agent_id,
                granted_by=decided_by,
                granted_tick=current_tick,
                expires_tick=current_tick + duration_ticks,
            )
            self.active_passes[req.agent_id] = new_pass
            msg = f"{authority_label} granted palace pass to {req.name} ({req.race})."
        elif decision == "DENY":
            req.status = "DENIED"
            msg = f"{authority_label} denied palace entry to {req.name} ({req.race})."
            self._dispatch_escort(req.agent_id)
        elif decision == "ESCORT":
            req.status = "ESCORTED"
            msg = f"{authority_label} ordered knights to escort {req.name} off grounds."
            self._dispatch_escort(req.agent_id)
        else:
            req.status = "DENIED"
            msg = f"Unknown decision '{decision}' for {req.name}."

        # Record in God Ledger
        if self.ledger_pipeline:
            self.ledger_pipeline.record_deity_message(
                entry_id=f"sec_{uuid.uuid4().hex[:8]}",
                day=day,
                tick=current_tick,
                category="PALACE_SECURITY",
                deity_slot=None,
                speaker_name="World Goddess" if decided_by == "WORLD_GODDESS" else "God",
                message=msg,
            )

        # Notify adapter
        if self.adapter:
            self.adapter.emit_event(
                "PALACE_DECISION_ANNOUNCED",
                {
                    "request_id": req.request_id,
                    "agent_id": req.agent_id,
                    "name": req.name,
                    "decision": decision,
                    "decided_by": decided_by,
                    "tick": current_tick,
                },
            )

        self.historical_requests.append(req)
        return req

    def _auto_adjudicate_goddess(self, req: PalaceEntryRequest, current_tick: int) -> None:
        """
        World Goddess autonomous evaluation:
        Grants pass to devout clean citizens; denies and escorts criminals or low devotion.
        """
        if req.criminal_count == 0 and req.faith_devotion >= 0.40:
            self.resolve_request(
                request_id=req.request_id,
                decision="GRANT",
                decided_by="WORLD_GODDESS",
                current_tick=current_tick,
            )
        else:
            self.resolve_request(
                request_id=req.request_id,
                decision="DENY",
                decided_by="WORLD_GODDESS",
                current_tick=current_tick,
            )

    # =========================================================================
    # Knight Battalion Deployment & Patrol Routing
    # =========================================================================

    def spawn_knight_battalion(
        self,
        agents_registry: dict[str, AgentRecord],
        count: int = 24,
    ) -> list[AgentRecord]:
        """
        Spawns the 20-24 Palace Knights at the Acropolis Imperial Barracks
        (x = -48.0, y = 32.0, z = 12.0) with deterministic patrol routes.
        """
        knights: list[AgentRecord] = []
        barracks_x = -48.0
        barracks_z = 12.0

        for i in range(count):
            knight_id = f"knight_acropolis_{i + 1:02d}"
            name = f"Knight Commander {i + 1}" if i == 0 else f"Palace Knight {i + 1}"
            slot_idx = 1000 + i

            # Assign specific tactical roles
            if i < 4:
                role_type = "WALL_SENTRY"
                waypoints = [
                    (65.0, 0.0),
                    (0.0, 65.0),
                    (-65.0, 0.0),
                    (0.0, -65.0),
                ]
            elif i < 8:
                role_type = "COURTYARD_SENTRY"
                waypoints = [
                    (25.0, 15.0),
                    (-25.0, 15.0),
                    (-25.0, -20.0),
                    (25.0, -20.0),
                ]
            elif i < 18:
                role_type = "ROAD_CHECKPOINT"
                # 5 roads: 0°, 72°, 144°, 216°, 288° at radius 42m
                road_idx = (i - 8) // 2
                angle = math.radians(road_idx * 72.0)
                cx = 42.0 * math.cos(angle)
                cz = 42.0 * math.sin(angle)
                offset = 4.0 if (i % 2 == 0) else -4.0
                waypoints = [
                    (cx + offset, cz),
                    (cx - offset, cz),
                ]
            else:
                role_type = "RAPID_RESPONSE"
                waypoints = [
                    (barracks_x + 3.0, barracks_z + 3.0),
                    (barracks_x - 3.0, barracks_z - 3.0),
                ]

            pos_x = waypoints[0][0]
            pos_z = waypoints[0][1]

            if self.engine:
                pos_vec = Vec3(x=pos_x, y=PALACE_CENTER_Y, z=pos_z)
                knight = self.engine.spawn_agent(
                    race="HUMAN",
                    gender="BOY" if i % 2 == 0 else "GIRL",
                    stage="ADULT",
                    pos=pos_vec,
                    initial_credits=200.0,
                    role="PALACE_KNIGHT",
                    title="Palace Knight",
                    dynasty_surname="Imperial Guard",
                    agent_id=knight_id,
                )
                knight.pos.y = PALACE_CENTER_Y
                knight.display_name = name
                knight.epithet = "The Vigilant"
                knight.health = 100.0
                knight.max_health = 100.0
                knight.hunger = 100.0
                knight.stamina = 100.0
            else:
                slot_idx = 1000 + i
                knight = AgentRecord(
                    agent_id=knight_id,
                    slot_idx=slot_idx,
                    display_name=name,
                    dynasty_surname="Imperial Guard",
                    epithet="The Vigilant",
                    gender="BOY" if i % 2 == 0 else "GIRL",
                    race="HUMAN",
                    stage="ADULT",
                    role="PALACE_KNIGHT",
                    profession="KNIGHT",
                    title="Palace Knight",
                    health=100.0,
                    max_health=100.0,
                    hunger=100.0,
                    stamina=100.0,
                    credits=200.0,
                    pos=Vec3(x=pos_x, y=PALACE_CENTER_Y, z=pos_z),
                    personality=generate_personality_vector("HUMAN"),
                    mood=MoodState(calm=0.8),
                )
                agents_registry[knight_id] = knight

            self.knight_agent_ids.append(knight_id)
            self.knight_roles[knight_id] = role_type
            self.knight_waypoints[knight_id] = waypoints
            self.knight_waypoint_idx[knight_id] = 0
            knights.append(knight)

        return knights

    def rebuild_knight_roster(self, agents_registry: dict[str, AgentRecord]) -> None:
        """Reconstructs Palace Knight rosters and patrol waypoints from living agents on restore."""
        self.knight_agent_ids.clear()
        self.knight_roles.clear()
        self.knight_waypoints.clear()
        self.knight_waypoint_idx.clear()
        self.knight_targets.clear()
        self.reported_trespassers.clear()

        barracks_x = -48.0
        barracks_z = 12.0

        knights = [
            ag for ag in agents_registry.values()
            if ag.alive and ag.role == "PALACE_KNIGHT"
        ]
        knights.sort(key=lambda a: a.agent_id)

        for i, knight in enumerate(knights):
            knight_id = knight.agent_id
            self.knight_agent_ids.append(knight_id)

            if i < 4:
                role_type = "WALL_SENTRY"
                waypoints = [
                    (65.0, 0.0),
                    (0.0, 65.0),
                    (-65.0, 0.0),
                    (0.0, -65.0),
                ]
            elif i < 8:
                role_type = "COURTYARD_SENTRY"
                waypoints = [
                    (25.0, 15.0),
                    (-25.0, 15.0),
                    (-25.0, -20.0),
                    (25.0, -20.0),
                ]
            elif i < 18:
                role_type = "ROAD_CHECKPOINT"
                road_idx = (i - 8) // 2
                angle = math.radians(road_idx * 72.0)
                cx = 42.0 * math.cos(angle)
                cz = 42.0 * math.sin(angle)
                offset = 4.0 if (i % 2 == 0) else -4.0
                waypoints = [
                    (cx + offset, cz),
                    (cx - offset, cz),
                ]
            else:
                role_type = "RAPID_RESPONSE"
                waypoints = [
                    (barracks_x + 3.0, barracks_z + 3.0),
                    (barracks_x - 3.0, barracks_z - 3.0),
                ]

            self.knight_roles[knight_id] = role_type
            self.knight_waypoints[knight_id] = waypoints
            self.knight_waypoint_idx[knight_id] = 0

    def _dispatch_escort(self, target_agent_id: str) -> None:
        """Assigns the nearest available Palace Knight to escort an agent out."""
        for tid, _ in self.knight_targets.values():
            if tid == target_agent_id:
                return

        best_knight_id: str | None = None
        for kid in self.knight_agent_ids:
            if kid not in self.knight_targets:
                best_knight_id = kid
                break

        if not best_knight_id and self.knight_agent_ids:
            best_knight_id = self.knight_agent_ids[-1]

        if best_knight_id:
            self.knight_targets[best_knight_id] = (target_agent_id, "ESCORT")

    def _dispatch_intercept(self, target_agent_id: str) -> None:
        """Assigns the nearest available Palace Knight to intercept a hostile/trespasser."""
        for tid, _ in self.knight_targets.values():
            if tid == target_agent_id:
                return

        for kid in self.knight_agent_ids:
            if kid not in self.knight_targets:
                self.knight_targets[kid] = (target_agent_id, "INTERCEPT")
                return

        if self.knight_agent_ids:
            self.knight_targets[self.knight_agent_ids[0]] = (target_agent_id, "INTERCEPT")

    # =========================================================================
    # Simulation Step & Real-time State Machine
    # =========================================================================

    def step(self, current_tick: int, agents: dict[str, AgentRecord]) -> None:
        """
        Executes security monitoring per simulation tick:
        1. Prunes expired PalacePass entries.
        2. Monitors mortals entering 35m Gate Zone & 95m Inner Palace Sanctuary.
        3. Halts unverified mortals & dispatches requests.
        4. Applies Dragon fear aura, judiciary trespass filing & Knight interception on breach.
        5. Ticks Palace Knight patrol movements and escort maneuvers.
        """
        # 1. Prune expired passes
        expired_ids = [
            aid for aid, p in self.active_passes.items() if current_tick > p.expires_tick
        ]
        for aid in expired_ids:
            del self.active_passes[aid]

        is_god_active = self.god_presence.is_active if self.god_presence else False

        # 2. Check pending request timeouts (auto-adjudicate by Goddess when God is away)
        for req in list(self.pending_requests.values()):
            if not is_god_active or (current_tick - req.tick >= DELEGATION_TIMEOUT_TICKS):
                self._auto_adjudicate_goddess(req, current_tick)

        # 3. Monitor agents around Gate (35m) and Inner Palace (95m)
        for agent in agents.values():
            if self.is_whitelisted(agent):
                continue

            dist_gate = math.hypot(agent.pos.x - MAIN_GATE_X, agent.pos.z - MAIN_GATE_Z)
            dist_center = math.hypot(agent.pos.x - PALACE_CENTER_X, agent.pos.z - PALACE_CENTER_Z)

            has_pass = self.has_active_pass(agent.agent_id, current_tick)

            # --- Gate Threshold Zone (35m) ---
            if dist_gate <= GATE_THRESHOLD_RADIUS and not has_pass:
                # Halt mortal movement
                agent.stamina = max(0.0, agent.stamina - 5.0)

                # Check if request already open
                if agent.agent_id not in self.agent_to_request:
                    req = self.request_entry(agent, current_tick)
                    if not is_god_active:
                        self._auto_adjudicate_goddess(req, current_tick)

            # --- Inner Palace Sanctuary (95m) Breach / Trespass ---
            if dist_center <= INNER_PALACE_RADIUS and not has_pass:
                # Trigger Dragon Fear Aura
                dist_dragon_left = math.hypot(
                    agent.pos.x - DRAGON_LEFT_X, agent.pos.z - DRAGON_LEFT_Z
                )
                dist_dragon_right = math.hypot(
                    agent.pos.x - DRAGON_RIGHT_X, agent.pos.z - DRAGON_RIGHT_Z
                )

                if (
                    dist_dragon_left <= FEAR_AURA_RADIUS
                    or dist_dragon_right <= FEAR_AURA_RADIUS
                    or dist_center <= 50.0
                ):
                    agent.distress = 1.0
                    agent.crying = True
                    agent.stamina = 0.0

                # Intercept with Palace Knights
                self._dispatch_intercept(agent.agent_id)

                # File judiciary case once per trespass incident
                if agent.agent_id not in self.reported_trespassers:
                    self.reported_trespassers.add(agent.agent_id)
                    if self.judiciary:
                        self.judiciary.file_case(
                            accused_id=agent.agent_id,
                            offense_type="TRESPASS",
                            opened_tick=current_tick,
                            settlement_id="acropolis_palace",
                            evidence_score=1.0,
                        )

                    if self.adapter:
                        self.adapter.emit_event(
                            "PALACE_TRESPASS_ALERT",
                            {
                                "agent_id": agent.agent_id,
                                "name": agent.display_name,
                                "pos": {"x": agent.pos.x, "y": agent.pos.y, "z": agent.pos.z},
                                "tick": current_tick,
                            },
                        )

                # Physically push back unauthorized intruder toward outer boundary
                dir_x = agent.pos.x - PALACE_CENTER_X
                dir_z = agent.pos.z - PALACE_CENTER_Z
                length = math.hypot(dir_x, dir_z)
                if length > 0.001:
                    agent.pos.x += (dir_x / length) * 1.5
                    agent.pos.z += (dir_z / length) * 1.5

        # 4. Tick Palace Knight Battalion movement
        self._step_knights(agents)

    def _step_knights(self, agents: dict[str, AgentRecord]) -> None:
        """Updates knight positions along patrol paths or toward intercept/escort targets."""
        for knight_id in self.knight_agent_ids:
            knight = agents.get(knight_id)
            if not knight:
                continue

            # Check if knight has active target
            if knight_id in self.knight_targets:
                target_id, mode = self.knight_targets[knight_id]
                target = agents.get(target_id)
                if not target or not target.alive:
                    del self.knight_targets[knight_id]
                    self.reported_trespassers.discard(target_id)
                    continue

                dist_to_center = math.hypot(
                    target.pos.x - PALACE_CENTER_X, target.pos.z - PALACE_CENTER_Z
                )
                if dist_to_center >= OUTER_BOUNDARY_RADIUS:
                    # Target has been cleared beyond outer perimeter
                    del self.knight_targets[knight_id]
                    self.reported_trespassers.discard(target_id)
                    continue

                dx = target.pos.x - knight.pos.x
                dz = target.pos.z - knight.pos.z
                dist = math.hypot(dx, dz)

                if mode == "INTERCEPT":
                    # Move directly toward target
                    if dist > 2.0:
                        knight.pos.x += (dx / dist) * 1.2
                        knight.pos.z += (dz / dist) * 1.2
                        knight.yaw = round(math.atan2(-dx, -dz), 4)
                    else:
                        # Subdued/intercepted: deplete stamina and transition to ESCORT
                        target.stamina = 0.0
                        self.knight_targets[knight_id] = (target_id, "ESCORT")
                elif mode == "ESCORT":
                    # Shepherd target away from palace towards outer boundary
                    push_x = target.pos.x - PALACE_CENTER_X
                    push_z = target.pos.z - PALACE_CENTER_Z
                    p_len = math.hypot(push_x, push_z)
                    if p_len > 0.001:
                        target.pos.x += (push_x / p_len) * 1.0
                        target.pos.z += (push_z / p_len) * 1.0
                        target.yaw = round(math.atan2(-push_x, -push_z), 4)
                        knight.pos.x = target.pos.x - (push_x / p_len) * 2.0
                        knight.pos.z = target.pos.z - (push_z / p_len) * 2.0
                        knight.yaw = round(math.atan2(-push_x, -push_z), 4)

                        if self.engine:
                            if hasattr(self.engine, "heightmap") and self.engine.heightmap:
                                try:
                                    target.pos.y = self.engine.heightmap.get_elevation(
                                        target.pos.x, target.pos.z
                                    )
                                except (AttributeError, TypeError, IndexError):
                                    target.pos.y = PALACE_CENTER_Y
                            if hasattr(self.engine, "spatial_grid") and self.engine.spatial_grid:
                                self.engine.spatial_grid.update_agent(
                                    target_id, target.pos.x, target.pos.z
                                )

                    # Check if pushed beyond outer boundary during this step
                    new_dist = math.hypot(
                        target.pos.x - PALACE_CENTER_X, target.pos.z - PALACE_CENTER_Z
                    )
                    if new_dist >= OUTER_BOUNDARY_RADIUS:
                        del self.knight_targets[knight_id]
                        self.reported_trespassers.discard(target_id)

                if self.engine:
                    if hasattr(self.engine, "heightmap") and self.engine.heightmap:
                        try:
                            knight.pos.y = self.engine.heightmap.get_elevation(
                                knight.pos.x, knight.pos.z
                            )
                        except (AttributeError, TypeError, IndexError):
                            knight.pos.y = PALACE_CENTER_Y
                    if hasattr(self.engine, "spatial_grid") and self.engine.spatial_grid:
                        self.engine.spatial_grid.update_agent(knight_id, knight.pos.x, knight.pos.z)
                    if hasattr(self.engine, "adapter") and self.engine.adapter:
                        self.engine.adapter.update_agent_position(
                            slot_idx=knight.slot_idx,
                            x=knight.pos.x,
                            y=knight.pos.y,
                            z=knight.pos.z,
                            yaw=knight.yaw,
                        )
                continue

            # Normal cyclical patrol waypoint routing
            waypoints = self.knight_waypoints.get(knight_id)
            if not waypoints:
                continue

            curr_idx = self.knight_waypoint_idx.get(knight_id, 0)
            target_pt = waypoints[curr_idx]

            dx = target_pt[0] - knight.pos.x
            dz = target_pt[1] - knight.pos.z
            dist = math.hypot(dx, dz)

            if dist < 1.5:
                # Advance to next waypoint
                next_idx = (curr_idx + 1) % len(waypoints)
                self.knight_waypoint_idx[knight_id] = next_idx
            else:
                speed = 0.6
                knight.pos.x += (dx / dist) * speed
                knight.pos.z += (dz / dist) * speed

            if self.engine:
                if hasattr(self.engine, "heightmap") and self.engine.heightmap:
                    try:
                        knight.pos.y = self.engine.heightmap.get_elevation(
                            knight.pos.x, knight.pos.z
                        )
                    except (AttributeError, TypeError, IndexError):
                        knight.pos.y = PALACE_CENTER_Y
                if hasattr(self.engine, "spatial_grid") and self.engine.spatial_grid:
                    self.engine.spatial_grid.update_agent(knight_id, knight.pos.x, knight.pos.z)
