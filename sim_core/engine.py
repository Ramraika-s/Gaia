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
from typing import Any, Literal

import psutil

from sim_core.brains.consolidation import SleepCycleConsolidator
from sim_core.brains.hierarchical_brain import HierarchicalBrain
from sim_core.brains.memory_rag import MemoryRAGIndex
from sim_core.brains.personality import MoodState, generate_personality_vector
from sim_core.brains.profession_nets import PROFESSIONS
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
from sim_core.divine.autonomy import DivineAutonomyEngine
from sim_core.divine.god_ledger import GodLedgerPipeline, GodPresenceTracker
from sim_core.divine.hierarchy import RACE_TO_DEITY_SLOT, DivineHierarchyManager
from sim_core.divine.llm_brain import DivineLLMBrain
from sim_core.divine.sister_council import SisterCouncilEngine
from sim_core.lifecycle import LifecycleManager
from sim_core.neural.shared_net import SharedSkillNet
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
    WorldLibraryEntry,
)
from sim_core.society.borders import BorderManager
from sim_core.society.economy import WorldBank
from sim_core.society.gear_economy import GearEconomyEngine
from sim_core.society.housing_market import HousingMarketEngine
from sim_core.society.judiciary import JudiciaryEngine
from sim_core.society.library import TwoBookGovernanceEngine
from sim_core.society.morality import MoralityEngine
from sim_core.society.naming import generate_birth_name, generate_dynasty_surname
from sim_core.society.politics import PoliticalEngine
from sim_core.society.property import PropertyManager
from sim_core.society.religion import ReligionManager
from sim_core.society.seasons import SeasonManager
from sim_core.society.speech_acts import SpeechActEngine
from sim_core.society.traditions import TraditionManager
from sim_core.society.wtc_market import WTCExchange
from sim_core.spatial.hash_grid import SpatialHashGrid
from sim_core.spatial.heightmap import Heightmap
from sim_core.spatial.navigation import NavigationEngine
from sim_core.world.city_layout import CityLayoutEngine
from sim_core.world.palace_security import PalaceSecurityEngine
from sim_core.world.regional_weather import RegionalWeatherEngine


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

        # 4-Pillar Cognitive Core (Sprint 4)
        self.hierarchical_brain = HierarchicalBrain(
            initial_capacity=initial_capacity, healer=self.healer
        )
        self.batched_net = self.hierarchical_brain.tier3_self
        self.shared_skill_net = SharedSkillNet()
        self.memory_rag = MemoryRAGIndex()
        self.sleep_consolidator = SleepCycleConsolidator(healer=self.healer)

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
        self.morality = MoralityEngine()
        self.traditions = TraditionManager()
        self.weather_engine = RegionalWeatherEngine()

        # Adapter for visualization / Godot IPC
        self.adapter: WorldAdapter = adapter if adapter is not None else MockWorldAdapter()

        # Palace security and Twin Dragon gate
        self.palace_security = PalaceSecurityEngine(engine=self)

        # 5 Ring 1 Gated Racial Cities & building layout
        self.city_layout = CityLayoutEngine(engine=self)

        # Autonomous Housing Market & Ring 2 Frontier Pioneers (Sprint 6)
        self.housing_market = HousingMarketEngine(engine=self)

        # Modular Outfits, Accessories & Tools Economy (Sprint 6)
        self.gear_economy = GearEconomyEngine(engine=self)

        # Spatial awareness, navigation, and speech acts (Sprint 5)
        self.navigation = NavigationEngine(heightmap=self.heightmap)
        self.speech_acts = SpeechActEngine(engine=self)
        self.divine_autonomy = DivineAutonomyEngine(engine=self)
        self.divine_llm_brain = DivineLLMBrain(engine=self)

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
        role: Literal[
            "CITIZEN", "PALACE_KNIGHT", "SCHOLAR", "MERCHANT", "FARMER", "CLERIC", "CITY_GUARD"
        ] = "CITIZEN",
        title: str | None = None,
        agent_id: str | None = None,
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
        agent_id = agent_id or f"agent_{uuid.uuid4().hex[:12]}"

        spawn_pos = pos if pos is not None else Vec3(x=0.0, y=0.0, z=0.0)
        spawn_pos.y = self.heightmap.get_elevation(spawn_pos.x, spawn_pos.z)

        name = generate_birth_name(race, gender, sub_lineage=sub_lineage)
        surname = dynasty_surname or generate_dynasty_surname(race, sub_lineage=sub_lineage)

        dragon_form = "HUMANOID_DRAGON" if (race == "DRAGON" and stage != "INFANT") else None
        patron_slot = RACE_TO_DEITY_SLOT.get(race) if secondary_heritage_race is None else None

        personality = generate_personality_vector(race)
        mood = MoodState(calm=0.8)
        prof_role = role if role in PROFESSIONS else "CITIZEN"

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
            role=role,
            profession=prof_role,
            profession_level=1,
            profession_xp=0.0,
            hygiene=1.0,
            fatigue=0.0,
            known_books=[],
            personality=personality,
            mood=mood,
            active_mechanical_effects={},
            title=title,
            credits=0.0,
            settlement_id=settlement_id,
            religion_id=religion_id,
        )

        self.agents[agent_id] = agent
        self.spatial_grid.update_agent(agent_id, spawn_pos.x, spawn_pos.z)
        self.bank.issue_currency(agent, initial_credits)
        self.judiciary.population_ledger[race] = self.judiciary.population_ledger.get(race, 0) + 1
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

        # Step Divine Autonomy (Sprint 5)
        self.divine_autonomy.step(self.current_tick)

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
                    bubble_rigs.append(
                        {
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
                            "rotation_y": getattr(agent, "yaw", 0.0),
                            "crying": agent.crying,
                            "is_oracle": agent.is_oracle,
                            "dragon_form": agent.dragon_form,
                            "speech_text": getattr(agent, "speech_text", ""),
                            "activity_state": getattr(agent, "activity_state", "IDLE"),
                            "equipped_gear": list(getattr(agent, "equipped_gear", [])),
                            "home_building_id": getattr(agent, "home_building_id", None),
                        }
                    )
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
        # 3. Regional Weather Simulation, Time & Deity Sync (Every 2 ticks / 1 Hz)
        # ---------------------------------------------------------------------
        self.weather_engine.step(self.current_tick, self.current_season)
        if self.current_tick % 2 == 0:
            tick_in_day = self.current_tick % TICKS_PER_GAME_DAY
            time_of_day = (tick_in_day / float(TICKS_PER_GAME_DAY)) * 24.0
            season_prog = SeasonManager.get_season_progress(self.current_day, tick_in_day)
            weather_sample = self.weather_engine.sample_weather_at(
                self.god_avatar_pos.x, self.god_avatar_pos.z
            )
            self.adapter.sync_weather_time(
                day=self.current_day,
                time_of_day=time_of_day,
                season_progress=season_prog,
                weather=weather_sample["primary_weather"],
                weather_details=weather_sample,
            )
            sync_records = self.divine_autonomy.get_sync_records()
            self.adapter.sync_deities([d.model_dump() for d in sync_records])

        # ---------------------------------------------------------------------
        # 4. Civic Loop (Every 60 ticks) & Palace/City Security (Every tick)
        # ---------------------------------------------------------------------
        self.palace_security.step(self.current_tick, self.agents)
        self.city_layout.step_patrols(self.current_tick, self.agents)

        if self.current_tick % CIVIC_TICK_INTERVAL_TICKS == 0:
            self._step_civic_loop()

        # ---------------------------------------------------------------------
        # 5. Pure End-of-Day Atomic Two-Phase Commit
        # ---------------------------------------------------------------------
        if self.current_tick > 0 and self.current_tick % TICKS_PER_GAME_DAY == 0:
            self.commit_end_of_day()

    def _step_scheduled_agents(self, agents: list[AgentRecord]) -> None:
        """Processes biological aging, distress, and batched neural execution."""
        # Step biological lifecycle
        for agent in agents:
            LifecycleManager.advance_agent_tick(
                agent=agent,
                current_tick=self.current_tick,
                season=self.current_season,
                is_sheltered=True,
            )
            agent.hygiene = max(0.0, agent.hygiene - 0.0002)
            agent.fatigue = min(1.0, agent.fatigue + 0.0003)
            if agent.mood is not None:
                agent.mood.step_decay(decay_rate=0.005)

        # Vectorized 3-tier Hierarchical Cognitive Core forward pass
        self.hierarchical_brain.forward_agents(agents)

        # Utility Scheduler & Navigation Movement (Sprint 5)
        weather_at_avatar = self.weather_engine.sample_weather_at(
            self.god_avatar_pos.x, self.god_avatar_pos.z
        )
        weather_type = weather_at_avatar.get("primary_weather", "CLEAR")

        for agent in agents:
            is_infant_crying = False
            nearby_ids = self.spatial_grid.get_nearby_ids(agent.pos.x, agent.pos.z, radius=12.0)
            for nid in nearby_ids:
                other = self.agents.get(nid)
                if other and other.crying and other.stage == "INFANT":
                    is_infant_crying = True
                    break

            activity, target_pos = self.navigation.evaluate_utility_schedule(
                agent=agent,
                tick=self.current_tick,
                weather=weather_type,
                is_infant_crying_nearby=is_infant_crying,
            )
            agent.activity_state = activity
            if target_pos is not None:
                agent.pos.x, agent.pos.z, agent.yaw = self.navigation.resolve_world_movement(
                    current_x=agent.pos.x,
                    current_z=agent.pos.z,
                    target_x=target_pos.x,
                    target_z=target_pos.z,
                    speed=1.4,
                    dt=0.5,
                )

        # Crowd separation & God presence reaction (Sprint 5)
        self.navigation.apply_crowd_separation(agents, self.spatial_grid)
        self.navigation.apply_god_presence_reaction(agents, self.god_avatar_pos)

        # Semantic Speech Acts (Sprint 5)
        self.speech_acts.step(self.current_tick, agents)

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
                yaw=getattr(agent, "yaw", 0.0),
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

        # Autonomous Housing Market, Tier Upgrades & Ring 2 Frontier Pioneers
        self.housing_market.step_housing_market(self.agents, self.bank, self.current_tick)
        self.housing_market.step_frontier_pioneers(self.agents, self.bank, self.current_tick)

        # Modular Outfits, Accessories & Tools Economy
        self.gear_economy.step_gear_economy(self.agents, self.bank, self.current_tick)

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
            active_wars=sum(len(p.at_war_with) for p in self.political_engine.polities.values())
            // 2,
            neutral_free_cities=sum(
                1 for p in self.political_engine.polities.values() if p.is_neutral_free_city
            ),
        )

        # Pillar 4: Sleep-Cycle Consolidation (Mortal distillation, book-to-habit, deity drift)
        self.sleep_consolidator.consolidate_mortal_professions(
            agents=self.agents,
            profession_registry=self.hierarchical_brain.tier2_profession,
        )
        daily_events: list[dict[str, Any]] = [
            {"event_type": "WAR"}
            for _ in range(
                sum(len(p.at_war_with) for p in self.political_engine.polities.values()) // 2
            )
        ]
        if self.wtc.cpi > 1.5:
            daily_events.append({"event_type": "FAMINE", "severity": self.wtc.cpi - 1.0})
        self.sleep_consolidator.compress_deity_memories_and_drift(
            deities=self.divine_hierarchy.entities,
            daily_world_events=daily_events,
            memory_rag=self.memory_rag,
            day=self.current_day - 1,
        )

        # PyTorch model state payload
        pt_state = {
            "batched_net": self.batched_net.state_dict(),
            "shared_net": self.shared_skill_net.state_dict(),
            "hierarchical_brain": self.hierarchical_brain.state_dict(),
            "current_day": self.current_day,
            "current_tick": self.current_tick,
            "free_slots": self.batched_net.free_slots,
            "active_slots": list(self.batched_net.active_slots),
            "money_supply_m": self.bank.calculate_total_circulation(list(self.agents.values())),
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
                        f.season,
                        f.death_day,
                        f.death_tick,
                    ),
                )
            )

        for book in self.governance_engine.library_entries.values():
            tags_json = json.dumps(book.tags) if book.tags else "[]"
            effects_json = json.dumps(book.mechanical_effects) if book.mechanical_effects else "{}"
            if isinstance(book, WorldLibraryEntry):
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO world_library ("
                        "entry_id, topic, title, summary, author_id, "
                        "author_proficiency, skill_bonus, is_scripture, read_count, "
                        "created_tick, subject, section, fact_key, tags_json, "
                        "mechanical_effects_json, author_type"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                            book.subject,
                            book.section,
                            book.fact_key,
                            tags_json,
                            effects_json,
                            book.author_type,
                        ),
                    )
                )
            else:
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO world_library ("
                        "entry_id, topic, title, summary, author_id, "
                        "author_proficiency, skill_bonus, is_scripture, read_count, "
                        "created_tick, subject, section, fact_key, tags_json, "
                        "mechanical_effects_json, author_type"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            book.entry_id,
                            book.subject,
                            book.title,
                            book.summary,
                            book.author,
                            1.0,
                            0.0,
                            0,
                            0,
                            0,
                            book.subject,
                            book.target_section,
                            book.fact_key,
                            tags_json,
                            effects_json,
                            book.author_type,
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

    def buy_building(
        self,
        building_id: str,
        buyer_agent: AgentRecord,
    ) -> tuple[bool, str]:
        """Transfers ownership of a building and its deeded 16x16m parcel."""
        return self.city_layout.buy_building(building_id, buyer_agent, self.bank)

    def study_library_entry(self, agent_id: str, entry_id: str) -> tuple[bool, str]:
        """Agent studies a book from the World Library, unlocking its mechanical effects."""
        agent = self.agents.get(agent_id)
        if not agent:
            return False, f"AGENT_NOT_FOUND: {agent_id}"
        return self.memory_rag.study_library_entry(
            agent=agent,
            entry_id=entry_id,
            world_library=self.governance_engine.library_entries,
            current_day=self.current_day,
            current_tick=self.current_tick,
        )

    def teach_knowledge(
        self, mentor_id: str, apprentice_id: str, entry_id: str
    ) -> tuple[bool, str]:
        """Mentor teaches a known World Library book to an apprentice."""
        mentor = self.agents.get(mentor_id)
        apprentice = self.agents.get(apprentice_id)
        if not mentor or not apprentice:
            return False, "AGENT_NOT_FOUND"
        return self.memory_rag.teach_knowledge(
            mentor=mentor,
            apprentice=apprentice,
            entry_id=entry_id,
            world_library=self.governance_engine.library_entries,
            current_day=self.current_day,
            current_tick=self.current_tick,
        )
