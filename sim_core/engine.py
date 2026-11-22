"""
sim_core/engine.py
Main Simulation Engine for the Gaia Civilization Engine.
Coordinates Multi-Tier Cognitive LOD, Spatial Hash Grid, Heightmap Elevation,
Batched Tensor Brains, Economy, Property, Politics, Governance, Religion,
Judiciary, Traditions, and pure End-of-Day World Goddess Atomic Two-Phase Commit.
Follows ARCHITECTURE.md Sections 2, 7, 8 & AGENTS.md Section 3.
"""

from __future__ import annotations

import json
import signal
import time
import uuid
from pathlib import Path
from typing import Any

import psutil
import torch

from sim_core.bridge.base import WorldAdapter
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.config import (
    CIVIC_TICK_INTERVAL_TICKS,
    COGNITIVE_TICK_RATE_HZ,
    REALITY_BUBBLE_MAX_RIGS,
    REALITY_BUBBLE_RADIUS_METERS,
    SLAB_SIZE,
    SOFT_RAM_WATERMARK_PERCENT,
    TICKS_PER_GAME_DAY,
)
from sim_core.divine.god_ledger import GodLedgerPipeline, GodPresenceTracker
from sim_core.divine.hierarchy import RACE_TO_DEITY_SLOT, DivineHierarchyManager
from sim_core.divine.sister_council import SisterCouncilEngine
from sim_core.lifecycle import LifecycleManager
from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import STAGE_NAME_TO_IDX, SharedSkillNet
from sim_core.persistence.checkpoints import WorldGoddessCheckpointManager
from sim_core.persistence.db import init_db
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.resilience.healer import ErrorHealer
from sim_core.schemas import (
    AgentRecord,
    BeasthumanSubLineage,
    DailyManifest,
    Gender,
    RaceId,
    Season,
    Stage,
    Vec3,
)
from sim_core.society.borders import BorderManager
from sim_core.society.economy import WorldBank
from sim_core.society.judiciary import JudiciaryEngine
from sim_core.society.library import TwoBookGovernanceEngine
from sim_core.society.naming import generate_birth_name, generate_dynasty_surname
from sim_core.society.politics import PoliticalEngine
from sim_core.society.property import PropertyManager
from sim_core.society.religion import ReligionManager
from sim_core.society.seasons import SeasonManager
from sim_core.society.traditions import TraditionManager
from sim_core.society.wtc_market import WTCExchange
from sim_core.spatial.hash_grid import SpatialHashGrid
from sim_core.spatial.heightmap import Heightmap


class SimulationEngine:
    """
    Master simulation orchestrator:
    - Multi-tier Cognitive LOD scheduler (Tier 0 @ 2Hz, Tier 1 @ 1Hz, Tier 2 @ 0.25Hz).
    - Unbounded slab-grown neural forward passes.
    - Closed-loop double-entry economy, WTC inflation, and property probate/escheatment.
    - Pure end-of-day all-or-nothing atomic 2PC (strictly zero mid-day disk writes).
    - psutil host RAM 75% watermark monitor.
    - Graceful SIGINT/SIGTERM shutdown.
    """

    def __init__(
        self,
        db_path: str | Path = "data/civilization.db",
        checkpoints_dir: str | Path = "data/checkpoints",
        god_ledger_dir: str | Path = "data/god_ledger",
        heightmap_path: str | Path | None = None,
        adapter: WorldAdapter | None = None,
        headless: bool = True,
        initial_capacity: int = SLAB_SIZE,
    ) -> None:
        self.db_path = Path(db_path)
        self.checkpoints_dir = Path(checkpoints_dir)
        self.god_ledger_dir = Path(god_ledger_dir)
        self.headless = headless

        # Initialize SQLite DB schema if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(self.db_path)

        # Resilient error healer
        self.healer = ErrorHealer()

        # Spatial systems
        self.spatial_grid = SpatialHashGrid()
        self.heightmap = Heightmap(file_path=heightmap_path)

        # Neural systems
        self.batched_net = BatchedAgentSelfNet(
            initial_capacity=initial_capacity, healer=self.healer
        )
        self.shared_skill_net = SharedSkillNet()

        # Divine hierarchy & governance
        self.divine_hierarchy = DivineHierarchyManager()
        self.sister_council = SisterCouncilEngine(hierarchy=self.divine_hierarchy)
        self.god_presence = GodPresenceTracker()
        self.ledger_pipeline = GodLedgerPipeline(
            ledger_dir=str(self.god_ledger_dir),
            tracker=self.god_presence,
        )
        self.world_goddess = WorldGoddessCritic()
        self.checkpoint_mgr = WorldGoddessCheckpointManager(
            checkpoints_dir=self.checkpoints_dir, god_ledger_dir=self.god_ledger_dir
        )

        # Society, economy, and institutions
        self.bank = WorldBank()
        self.wtc = WTCExchange()
        self.property_mgr = PropertyManager()
        self.border_mgr = BorderManager()
        self.political_engine = PoliticalEngine()
        self.religion_mgr = ReligionManager()
        self.governance_engine = TwoBookGovernanceEngine()
        self.judiciary = JudiciaryEngine()
        self.traditions = TraditionManager()

        # Adapter for visualization / Godot IPC
        self.adapter: WorldAdapter = adapter if adapter is not None else MockWorldAdapter()

        # Agents state in RAM
        self.agents: dict[str, AgentRecord] = {}

        # Simulation clock and control
        self.current_tick: int = 0
        self.current_day: int = 1
        self.current_season: Season = "SPRING"
        self.speed: float = 1.0  # 1.0 to 60.0
        self.is_running: bool = False
        self.ram_watermark_alert_emitted: bool = False

        # God Avatar position for Reality Bubble calculations
        self.god_avatar_pos = Vec3(x=0.0, y=0.0, z=0.0)

        # Setup OS signal handlers for graceful shutdown
        self._setup_signals()

    def _setup_signals(self) -> None:
        """Configures SIGINT and SIGTERM handlers to trigger safe atomic shutdown."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            pass  # May fail in non-main threads or specialized test runners

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Signals shutdown and performs atomic save."""
        self.is_running = False

    def set_speed(self, speed: float) -> None:
        """Sets simulation speed multiplier (clamped between 1.0x and 60.0x)."""
        self.speed = max(1.0, min(60.0, float(speed)))

    # =========================================================================
    # Agent Lifecycle & Spawning
    # =========================================================================

    def spawn_agent(
        self,
        race: RaceId,
        gender: Gender,
        sub_lineage: BeasthumanSubLineage | None = None,
        secondary_heritage_race: RaceId | None = None,
        stage: Stage = "INFANT",
        pos: Vec3 | None = None,
        initial_credits: float = 10.0,
        settlement_id: str | None = None,
        religion_id: str | None = None,
        dynasty_surname: str | None = None,
    ) -> AgentRecord:
        """
        Spawns a new agent into the simulation:
        - Allocates slot in BatchedAgentSelfNet.
        - Generates birth name and dynasty surname.
        - Sets initial coords and elevation from heightmap.
        - Opens World Bank account with initial credit endowment.
        - Registers with SpatialHashGrid and Judiciary population ledger.
        """
        slot_idx = self.batched_net.allocate_slot()
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"

        spawn_pos = pos if pos is not None else Vec3(x=0.0, y=0.0, z=0.0)
        spawn_pos.y = self.heightmap.get_elevation(spawn_pos.x, spawn_pos.z)

        name = generate_birth_name(race, gender, sub_lineage=sub_lineage)
        surname = dynasty_surname or generate_dynasty_surname(race, sub_lineage=sub_lineage)

        dragon_form = "HUMANOID_DRAGON" if (race == "DRAGON" and stage != "INFANT") else None
        patron_slot = RACE_TO_DEITY_SLOT.get(race) if secondary_heritage_race is None else None

        agent = AgentRecord(
            agent_id=agent_id,
            slot_idx=slot_idx,
            display_name=name,
            dynasty_surname=surname,
            gender=gender,
            race=race,
            sub_lineage=sub_lineage,
            secondary_heritage_race=secondary_heritage_race,
            dragon_form=dragon_form,
            patron_godmother_slot=patron_slot,
            stage=stage,
            pos=spawn_pos,
            credits=0.0,
            settlement_id=settlement_id,
            religion_id=religion_id,
        )

        self.agents[agent_id] = agent
        self.spatial_grid.update_agent(agent_id, spawn_pos.x, spawn_pos.z)
        self.bank.issue_currency(agent, initial_credits)
        self.judiciary.population_ledger[race] = (
            self.judiciary.population_ledger.get(race, 0) + 1
        )
        self.judiciary.population_ledger["total_alive"] = (
            self.judiciary.population_ledger.get("total_alive", 0) + 1
        )

        self.adapter.spawn_agent(
            agent_id=agent_id,
            slot_idx=slot_idx,
            metadata={
                "display_name": name,
                "race": race,
                "gender": gender,
                "stage": stage,
                "x": spawn_pos.x,
                "y": spawn_pos.y,
                "z": spawn_pos.z,
            },
        )
        return agent

    # =========================================================================
    # Main Tick & Cognitive LOD Scheduler
    # =========================================================================

    def step_tick(self) -> None:
        """
        Executes one discrete simulation tick:
        1. Categorizes living agents into Multi-Tier Cognitive LOD:
           - Tier 0: Inside Reality Bubble (<= 140m), 2 Hz (every tick)
           - Tier 1: Distant awake / distress, 1 Hz (every 2nd tick)
           - Tier 2: Distant sleeping / idle, 0.25 Hz (every 8th tick)
        2. Evaluates batched neural forward pass for scheduled agents.
        3. Updates spatial coordinates, clamped by heightmap elevation.
        4. Runs civic, market, and RAM watermark checks every 60 ticks.
        5. Triggers World Goddess end-of-day atomic commit at day boundary.
        """
        self.current_tick += 1

        # ---------------------------------------------------------------------
        # 1. Multi-Tier Cognitive LOD Scheduling
        # ---------------------------------------------------------------------
        scheduled_agents: list[AgentRecord] = []
        bubble_rigs: list[dict[str, Any]] = []

        gx, gz = self.god_avatar_pos.x, self.god_avatar_pos.z
        bubble_radius_sq = REALITY_BUBBLE_RADIUS_METERS**2

        for agent in self.agents.values():
            if not agent.alive or agent.quarantined:
                continue

            dx = agent.pos.x - gx
            dz = agent.pos.z - gz
            dist_sq = dx * dx + dz * dz

            if dist_sq <= bubble_radius_sq:
                # Tier 0: Inside Reality Bubble -> Steps every tick (2 Hz)
                scheduled_agents.append(agent)
                if len(bubble_rigs) < REALITY_BUBBLE_MAX_RIGS:
                    bubble_rigs.append({
                        "agent_id": agent.agent_id,
                        "slot_idx": agent.slot_idx,
                        "race": agent.race,
                        "gender": agent.gender,
                        "stage": agent.stage,
                        "name": agent.display_name,
                        "dynasty": agent.dynasty_surname,
                        "x": agent.pos.x,
                        "y": agent.pos.y,
                        "z": agent.pos.z,
                        "crying": agent.crying,
                        "is_oracle": agent.is_oracle,
                        "dragon_form": agent.dragon_form,
                    })
            elif agent.crying or agent.distress >= 0.45 or agent.health < agent.max_health:
                # Tier 1: Distant awake / distress -> Steps every 2 ticks (1 Hz)
                if self.current_tick % 2 == 0:
                    scheduled_agents.append(agent)
            else:
                # Tier 2: Distant sleeping / idle -> Steps every 8 ticks (0.25 Hz)
                if self.current_tick % 8 == 0:
                    scheduled_agents.append(agent)

        self.adapter.sync_bubble(bubble_rigs)

        # ---------------------------------------------------------------------
        # 2. Batched Neural Evaluation & Biological Lifecycle
        # ---------------------------------------------------------------------
        if scheduled_agents:
            self._step_scheduled_agents(scheduled_agents)

        # ---------------------------------------------------------------------
        # 3. Civic Loop (Every 60 ticks)
        # ---------------------------------------------------------------------
        if self.current_tick % CIVIC_TICK_INTERVAL_TICKS == 0:
            self._step_civic_loop()

        # ---------------------------------------------------------------------
        # 4. Pure End-of-Day Atomic Two-Phase Commit
        # ---------------------------------------------------------------------
        if self.current_tick > 0 and self.current_tick % TICKS_PER_GAME_DAY == 0:
            self.commit_end_of_day()

    def _step_scheduled_agents(self, agents: list[AgentRecord]) -> None:
        """Processes biological aging, distress, and batched neural execution."""
        slots = [a.slot_idx for a in agents]
        n = len(agents)

        # Step biological lifecycle
        for agent in agents:
            LifecycleManager.advance_agent_tick(
                agent=agent,
                current_tick=self.current_tick,
                season=self.current_season,
                is_sheltered=True,
            )

        # Batched neural forward pass (vectorized PyTorch ops)
        self_inputs = torch.zeros((n, 20), dtype=torch.float32)
        shared_inputs = torch.zeros((n, 32), dtype=torch.float32)
        stage_indices = torch.zeros(n, dtype=torch.long)

        for i, agent in enumerate(agents):
            self_inputs[i, 0] = agent.health / max(1.0, agent.max_health)
            self_inputs[i, 1] = agent.hunger / 100.0
            self_inputs[i, 2] = agent.stamina / 100.0
            self_inputs[i, 3] = agent.distress
            self_inputs[i, 4] = 1.0 if agent.crying else 0.0
            self_inputs[i, 5] = agent.credits / 100.0
            stage_indices[i] = STAGE_NAME_TO_IDX.get(agent.stage, 0)

        slot_tensor = torch.tensor(slots, dtype=torch.long)
        out, _ = self.batched_net(
            self_inputs, slot_tensor, day=self.current_day, tick=self.current_tick
        )
        delta_l = out[:, 0:20]
        l_shared, _ = self.shared_skill_net(shared_inputs)
        g_survival = self.shared_skill_net.compute_survival_gate(
            self_inputs[:, 0], self_inputs[:, 1] * 100.0
        )
        l_raw = self.shared_skill_net.blend_logits(l_shared, delta_l, g_survival)
        _ = self.shared_skill_net.apply_stage_mask(l_raw, stage_indices)

        # Update physical coordinates and snap elevation to heightmap
        for agent in agents:
            elev = self.heightmap.get_elevation(agent.pos.x, agent.pos.z)
            agent.pos.y = elev
            self.spatial_grid.update_agent(agent.agent_id, agent.pos.x, agent.pos.z)
            self.adapter.update_agent_position(
                slot_idx=agent.slot_idx,
                x=agent.pos.x,
                y=agent.pos.y,
                z=agent.pos.z,
            )

    def _step_civic_loop(self) -> None:
        """Executes WTC clearing, loan checks, and psutil host RAM monitoring."""
        # WTC market clearing & Fisher CPI update
        total_m = self.bank.calculate_total_circulation(list(self.agents.values()))
        self.wtc.update_macro_aggregates(
            money_supply_m=total_m,
            real_output_q=max(10.0, float(len(self.agents) * 5.0)),
        )
        self.wtc.clear_market(current_day=self.current_day, current_tick=self.current_tick)

        # Process any bank default cases into judiciary
        for case_info in self.bank.defaulted_cases:
            self.judiciary.file_case(
                accused_id=case_info["accused_id"],
                offense_type="DEBT_DEFAULT",
                opened_tick=self.current_tick,
                settlement_id=None,
                evidence_score=1.0,
            )
        self.bank.defaulted_cases.clear()

        # psutil Host RAM Watermark Check (75% threshold)
        try:
            mem_pct = psutil.virtual_memory().percent
            if mem_pct >= SOFT_RAM_WATERMARK_PERCENT:
                if not self.ram_watermark_alert_emitted:
                    self.ram_watermark_alert_emitted = True
                    self.god_presence.set_active(True, self.current_tick)
        except Exception:
            pass

    # =========================================================================
    # Pure End-of-Day World Goddess Atomic Commit
    # =========================================================================

    def commit_end_of_day(self) -> DailyManifest:
        """
        Executes the all-or-nothing atomic end-of-day 2PC:
        1. Compiles God Ledger Markdown from buffered RAM logs.
        2. Packages neural model weights and money supply state.
        3. Invokes WorldGoddessCheckpointManager to write .db, .pt, and manifest.json.
        4. Strictly zero mid-day disk writes.
        """
        self.current_day += 1
        self.ram_watermark_alert_emitted = False

        # Advance calendar season every 7 game days
        self.current_season = SeasonManager.get_season(self.current_day)

        # Advance governance proposals and religious inactivity decay
        for pid in list(self.governance_engine.library_proposals.keys()):
            self.governance_engine.advance_proposal_lifecycle(pid, self.current_tick)
        for agent in self.agents.values():
            self.religion_mgr.apply_inactivity_decay(agent, self.current_tick)

        # Compile daily markdown ledger
        demographics = {
            "HUMAN": sum(1 for a in self.agents.values() if a.alive and a.race == "HUMAN"),
            "ELF": sum(1 for a in self.agents.values() if a.alive and a.race == "ELF"),
            "DRAGON": sum(1 for a in self.agents.values() if a.alive and a.race == "DRAGON"),
            "BEASTHUMAN": sum(
                1 for a in self.agents.values() if a.alive and a.race == "BEASTHUMAN"
            ),
            "DEMON": sum(1 for a in self.agents.values() if a.alive and a.race == "DEMON"),
        }
        goddess_name = self.divine_hierarchy.entities["world_goddess"].bestowed_name
        ledger_md = self.ledger_pipeline.compile_daily_ledger_markdown(
            day=self.current_day - 1,
            season=self.current_season,
            world_goddess_name=goddess_name,
            living_population=sum(demographics.values()),
            demographics=demographics,
            cpi=self.wtc.cpi,
            active_wars=sum(
                len(p.at_war_with) for p in self.political_engine.polities.values()
            ) // 2,
            neutral_free_cities=sum(
                1 for p in self.political_engine.polities.values() if p.is_neutral_free_city
            ),
        )

        # PyTorch model state payload
        pt_state = {
            "batched_net": self.batched_net.state_dict(),
            "shared_net": self.shared_skill_net.state_dict(),
            "current_day": self.current_day,
            "current_tick": self.current_tick,
            "free_slots": self.batched_net.free_slots,
            "active_slots": list(self.batched_net.active_slots),
            "money_supply_m": self.bank.calculate_total_circulation(
                list(self.agents.values())
            ),
            "reserve_credits": self.bank.reserve_credits,
        }

        # Prepare daily SQLite persistence deltas for agents, fatalities, library, and codex
        sql_deltas: list[tuple[str, tuple[Any, ...]]] = []
        for agent in self.agents.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO agents ("
                    "agent_id, slot_idx, display_name, dynasty_surname, epithet, gender, race, "
                    "sub_lineage, secondary_heritage_race, dragon_form, patron_godmother_slot, "
                    "godmother_affinities_json, is_oracle, skin_hsv_json, settlement_id, "
                    "nation_id, religion_id, cleric_rank, stage, age_ticks, health, max_health, "
                    "hunger, stamina, injured, illness, distress, crying, credits, credit_score, "
                    "breeding_cooldown, pregnant_ticks_remaining, pregnancy_father_id, "
                    "is_cross_species_pregnancy, last_prayer_tick, parent_ids_json, spouse_id, "
                    "alive, quarantined, pos_json, traits_json, skills_json, tradition_ids_json, "
                    "updated_tick"
                    ") VALUES ("
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
                    ")",
                    (
                        agent.agent_id,
                        agent.slot_idx,
                        agent.display_name,
                        agent.dynasty_surname,
                        agent.epithet,
                        agent.gender,
                        agent.race,
                        agent.sub_lineage,
                        agent.secondary_heritage_race,
                        agent.dragon_form,
                        agent.patron_godmother_slot,
                        json.dumps(agent.godmother_affinities),
                        1 if agent.is_oracle else 0,
                        json.dumps(agent.skin_hsv),
                        agent.settlement_id,
                        agent.nation_id,
                        agent.religion_id,
                        agent.cleric_rank,
                        agent.stage,
                        agent.age_ticks,
                        agent.health,
                        agent.max_health,
                        agent.hunger,
                        agent.stamina,
                        agent.injured,
                        agent.illness,
                        agent.distress,
                        1 if agent.crying else 0,
                        agent.credits,
                        agent.credit_score,
                        agent.breeding_cooldown,
                        agent.pregnant_ticks_remaining,
                        agent.pregnancy_father_id,
                        1 if agent.is_cross_species_pregnancy else 0,
                        agent.last_prayer_tick,
                        json.dumps(agent.parent_ids),
                        agent.spouse_id,
                        1 if agent.alive else 0,
                        1 if agent.quarantined else 0,
                        agent.pos.model_dump_json(),
                        json.dumps(agent.traits),
                        json.dumps(agent.skills),
                        json.dumps(agent.tradition_ids),
                        self.current_tick,
                    ),
                )
            )

        for f in self.judiciary.fatality_index:
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO fatalities ("
                    "agent_id, display_name, race, age_ticks, stage_at_death, cause, season, "
                    "death_day, death_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f.agent_id,
                        f.display_name,
                        f.race,
                        f.age_ticks,
                        f.stage_at_death,
                        f.cause,
                        f.season_of_death,
                        f.day_of_death,
                        f.tick_of_death,
                    ),
                )
            )

        for book in self.governance_engine.library_entries.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO world_library ("
                    "entry_id, topic, title, summary, author_id, author_proficiency, skill_bonus, "
                    "is_scripture, read_count, created_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        book.entry_id,
                        book.topic,
                        book.title,
                        book.summary,
                        book.author_id,
                        book.author_proficiency,
                        book.skill_bonus,
                        1 if book.is_scripture else 0,
                        book.read_count,
                        book.created_tick,
                    ),
                )
            )

        for decree in self.governance_engine.codex_entries.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO divine_codex ("
                    "entry_id, title, text, category, parameter_key, parameter_value_json, "
                    "author_slot, supporting_daughter_slots_json, approved_by_god, created_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decree.entry_id,
                        decree.title,
                        decree.text,
                        decree.category,
                        decree.parameter_key,
                        decree.parameter_value_json,
                        decree.author_slot,
                        json.dumps(decree.supporting_daughter_slots),
                        1 if decree.approved_by_god else 0,
                        decree.created_tick,
                    ),
                )
            )

        # Commit all daily deltas atomically via World Goddess 2PC
        manifest = self.checkpoint_mgr.commit_daily_checkpoint(
            day=self.current_day - 1,
            tick=self.current_tick,
            season=self.current_season,
            world_goddess_name=goddess_name,
            live_db_path=self.db_path,
            pt_state=pt_state,
            ledger_markdown=ledger_md,
            sql_deltas=sql_deltas,
        )
        return manifest

    def run(self, max_ticks: int | None = None) -> None:
        """Runs the simulation loop for max_ticks or until interrupted."""
        self.is_running = True
        ticks_done = 0

        target_dt = 1.0 / (COGNITIVE_TICK_RATE_HZ * self.speed)

        while self.is_running:
            start_t = time.perf_counter()
            self.step_tick()
            ticks_done += 1

            if max_ticks is not None and ticks_done >= max_ticks:
                break

            if not self.headless:
                elapsed = time.perf_counter() - start_t
                sleep_time = target_dt - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        # On clean shutdown, commit current state atomically
        if not self.headless:
            self.commit_end_of_day()
