"""
sim_core/brains/action_bridge.py
Live Cognitive Action Bridge & Real Rollout Collection.
Connects 3-Tier Hierarchical Cognitive Core forward inference to concrete world actions
and buffers top-practitioner transitions for nightly sleep consolidation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch

from sim_core.brains.profession_nets import ProfessionNetRegistry
from sim_core.lifecycle import LifecycleManager
from sim_core.society.religion import ReligionManager
from sim_core.society.seasons import SeasonManager

if TYPE_CHECKING:
    from sim_core.schemas import AgentRecord


@dataclass
class ProfessionTransition:
    """Recorded high-reward transition for Lv. 6+ practitioners."""

    features: list[float]  # 28-dim packed features
    level: float
    action_idx: int
    reward: float


class ProfessionRolloutBuffer:
    """
    Bounded transition buffer per profession (max 512 transitions each).
    Collected from top practitioners during active daylight simulation
    and consumed by SleepCycleConsolidator at end-of-day.
    """

    def __init__(self, max_size_per_prof: int = 512) -> None:
        self.max_size_per_prof = max_size_per_prof
        self.buffers: dict[str, list[ProfessionTransition]] = {}

    def add(
        self,
        profession: str,
        features: list[float],
        level: float,
        action_idx: int,
        reward: float,
    ) -> None:
        prof = profession.upper()
        buf = self.buffers.setdefault(prof, [])
        if len(buf) >= self.max_size_per_prof:
            buf.pop(0)
        buf.append(
            ProfessionTransition(
                features=features,
                level=level,
                action_idx=action_idx,
                reward=reward,
            )
        )

    def get_rollouts(self, profession: str) -> list[ProfessionTransition]:
        return list(self.buffers.get(profession.upper(), []))

    def size(self, profession: str) -> int:
        return len(self.buffers.get(profession.upper(), []))

    def clear(self, profession: str | None = None) -> None:
        if profession:
            self.buffers.pop(profession.upper(), None)
        else:
            self.buffers.clear()


class CognitiveActionExecutor:
    """
    Executes concrete simulation state updates based on winning policy actions
    selected by HierarchicalBrain.forward_agents(agents).
    """

    def __init__(
        self,
        engine: Any = None,
        rollout_buffer: ProfessionRolloutBuffer | None = None,
    ) -> None:
        self.engine = engine
        self.rollout_buffer = rollout_buffer or ProfessionRolloutBuffer()

    def execute_actions(
        self,
        agents: list[AgentRecord],
        masked_logits: torch.Tensor,
        values: torch.Tensor,
    ) -> list[int]:
        """
        Consumes (masked_logits, values) from HierarchicalBrain, selects the winning
        action (argmax), applies physical state updates, and buffers rollouts.
        Returns the selected action index per agent.
        """
        N = len(agents)
        if N == 0:
            return []

        # Argmax over valid actions (masked actions have -1e9)
        argmax_list = torch.argmax(masked_logits, dim=-1).tolist()
        if isinstance(argmax_list, int):
            winning_actions: list[int] = [int(argmax_list)]
        else:
            winning_actions: list[int] = [int(a) for a in argmax_list]

        for i, agent in enumerate(agents):
            if not getattr(agent, "alive", True):
                continue

            action_idx = winning_actions[i]
            reward = 0.0

            # -----------------------------------------------------------------
            # 0: REST / SLEEP
            # -----------------------------------------------------------------
            if action_idx == 0:
                agent.fatigue = max(0.0, agent.fatigue - 0.04)
                agent.stamina = min(100.0, agent.stamina + 4.0)
                reward = 0.6 if agent.fatigue > 0.3 else 0.2

            # -----------------------------------------------------------------
            # 1: EAT / DRINK
            # -----------------------------------------------------------------
            elif action_idx == 1:
                # DEF-T1-02: Close telepathic-home loophole and dead zones
                is_near_home = False
                if (
                    agent.home_building_id
                    and self.engine
                    and hasattr(self.engine, "city_layout")
                    and agent.home_building_id in self.engine.city_layout.buildings
                ):
                    hb = self.engine.city_layout.buildings[agent.home_building_id]
                    if math.hypot(agent.pos.x - hb.x, agent.pos.z - hb.z) <= 25.0:
                        is_near_home = True

                in_acropolis = math.hypot(agent.pos.x, agent.pos.z) <= 360.0

                in_ring1_city = False
                if self.engine and hasattr(self.engine, "city_layout"):
                    for c in self.engine.city_layout.cities.values():
                        if (
                            math.hypot(agent.pos.x - c.center_x, agent.pos.z - c.center_z)
                            <= 240.0
                        ):
                            in_ring1_city = True
                            break

                can_buy_food = (
                    (is_near_home or in_acropolis or in_ring1_city)
                    and agent.credits >= 0.10
                )

                bought = False
                if can_buy_food and self.engine and hasattr(self.engine, "bank"):
                    ok, _ = self.engine.bank.transfer_credits(
                        agent, self.engine.bank, 0.10, memo="FOOD_PURCHASE"
                    )
                    if ok:
                        bought = True
                        if agent.hunger < 95.0:
                            agent.hunger = min(100.0, agent.hunger + 12.0)
                            reward = 0.8
                        else:
                            reward = 0.1

                if not bought:
                    # Wilderness or broke: forage
                    if agent.stamina >= 5.0:
                        agent.stamina -= 5.0
                        season_mult = 1.0
                        if self.engine and hasattr(self.engine, "current_season"):
                            season_mult = SeasonManager.get_wild_food_multiplier(
                                self.engine.current_season
                            )
                        agent.hunger = min(100.0, agent.hunger + 4.0 * season_mult)
                        reward = 0.5
                    else:
                        reward = 0.0

            # -----------------------------------------------------------------
            # 2: GROOM / HYGIENE
            # -----------------------------------------------------------------
            elif action_idx == 2:
                agent.hygiene = min(1.0, agent.hygiene + 0.08)
                reward = 0.5 if agent.hygiene < 0.6 else 0.1

            # -----------------------------------------------------------------
            # 5: COMFORT_CHILD / CARE
            # -----------------------------------------------------------------
            elif action_idx == 5:
                # Seek crying infant/child within 4.0m
                crying_child = self._find_nearby_crying_child(agent, radius=4.0)
                if crying_child is not None:
                    dist = math.hypot(
                        agent.pos.x - crying_child.pos.x,
                        agent.pos.z - crying_child.pos.z,
                    )
                    LifecycleManager.soothe_or_comfort_child(agent, crying_child, dist)
                    reward = 1.0

            # -----------------------------------------------------------------
            # 6: STUDY_BOOK / LIBRARY
            # -----------------------------------------------------------------
            elif action_idx == 6:
                studied = self._attempt_study_book(agent)
                if studied:
                    reward = 1.0

            # -----------------------------------------------------------------
            # 7: CRAFT/WORK, 8: TRADE/MARKET, 10: CONFRONT/DEFEND
            # -----------------------------------------------------------------
            elif action_idx in (7, 8, 10):
                eff = getattr(agent, "active_mechanical_effects", {})
                yield_eff = (
                    eff.get("yield_mult", 0.0)
                    + eff.get("crop_yield_bonus", 0.0)
                    + eff.get("craft_speed_bonus", 0.0)
                    + eff.get("smelting_yield_bonus", 0.0)
                )
                res_eff = eff.get("research_rate", 0.0) + eff.get("judicial_accuracy", 0.0)
                eff_mult = max(0.2, min(3.0, 1.0 + yield_eff + res_eff))

                xp_gain = 1.5 * eff_mult
                if agent.profession_level >= 10:
                    agent.profession_xp = min(1000.0, agent.profession_xp + xp_gain)
                else:
                    agent.profession_xp += xp_gain
                    while (
                        agent.profession_level < 10
                        and agent.profession_xp >= agent.profession_level * 100.0
                    ):
                        agent.profession_level += 1
                    if agent.profession_level >= 10:
                        agent.profession_xp = min(1000.0, agent.profession_xp)

                reward = 0.9

            # -----------------------------------------------------------------
            # 9: PRAY / ALTAR
            # -----------------------------------------------------------------
            elif action_idx == 9:
                deity_slot = getattr(agent, "patron_godmother_slot", None) or "world_goddess"
                cur_tick = getattr(self.engine, "current_tick", 0) if self.engine else 0
                success, _, energy_gen = ReligionManager.pray(
                    agent, deity_slot, "EARNEST_VOLUNTARY", cur_tick
                )
                if success and self.engine and hasattr(self.engine, "divine_hierarchy"):
                    self.engine.divine_hierarchy.add_divine_energy(deity_slot, energy_gen)
                reward = 0.8

            # Default positive reward for other valid actions (3: EVADE, 4: FORAGE, etc.)
            else:
                reward = 0.3

            # Record high-reward trajectories for top practitioners (Lv. 6+)
            if agent.profession_level >= 6 and reward >= 0.5:
                base_features = [0.1] * 20
                base_features[0] = agent.hunger / 100.0
                base_features[1] = agent.stamina / 100.0
                base_features[2] = agent.hygiene
                base_features[3] = agent.fatigue

                features_28d = ProfessionNetRegistry.pack_profession_features(
                    base_living_features=base_features,
                    level=agent.profession_level,
                    xp=agent.profession_xp,
                    active_mechanical_effects=getattr(agent, "active_mechanical_effects", {}),
                )
                self.rollout_buffer.add(
                    profession=agent.profession,
                    features=features_28d,
                    level=float(agent.profession_level),
                    action_idx=action_idx,
                    reward=reward,
                )

        return winning_actions

    def _find_nearby_crying_child(
        self,
        agent: AgentRecord,
        radius: float = 4.0,
    ) -> AgentRecord | None:
        """Finds any crying INFANT or CHILD within radius meters."""
        if not self.engine:
            return None

        if hasattr(self.engine, "spatial_grid"):
            nearby_ids = self.engine.spatial_grid.get_nearby_ids(
                agent.pos.x, agent.pos.z, radius=radius
            )
            for nid in nearby_ids:
                if nid == agent.agent_id:
                    continue
                cand = self.engine.agents.get(nid)
                if cand and cand.alive and cand.crying and cand.stage in ("INFANT", "CHILD"):
                    return cand
        elif hasattr(self.engine, "agents"):
            for cand in self.engine.agents.values():
                if cand.agent_id == agent.agent_id:
                    continue
                if cand.alive and cand.crying and cand.stage in ("INFANT", "CHILD"):
                    d = math.hypot(agent.pos.x - cand.pos.x, agent.pos.z - cand.pos.z)
                    if d <= radius:
                        return cand

        return None

    def _attempt_study_book(self, agent: AgentRecord) -> bool:
        """Attempts to study an unread book from the World Library."""
        if not self.engine or not hasattr(self.engine, "governance_engine"):
            return False

        # DEF-T1-01: Proximity check. Must be within 35.0m of World Library
        # or on parcel with has_library == True
        dist_acropolis = min(
            math.hypot(agent.pos.x - 180.0, agent.pos.z - 180.0),
            math.hypot(agent.pos.x - 175.0, agent.pos.z - 160.0),
        )
        near_library = dist_acropolis <= 35.0

        if not near_library and hasattr(self.engine, "property_mgr") and self.engine.property_mgr:
            cx = int(math.floor(agent.pos.x / 16.0))
            cz = int(math.floor(agent.pos.z / 16.0))
            parcel = self.engine.property_mgr.get_parcel(cx, cz)
            if parcel and getattr(parcel, "has_library", False):
                near_library = True

        if not near_library:
            return False

        gov = getattr(self.engine, "governance_engine", None)
        rag = getattr(self.engine, "memory_rag", None)
        if not gov or not rag:
            return False

        lib_entries = getattr(gov, "library_entries", {})
        if not lib_entries:
            return False

        known = set(getattr(agent, "known_books", []))
        for entry_id in lib_entries:
            if entry_id not in known:
                day = getattr(self.engine, "current_day", 1)
                tick = getattr(self.engine, "current_tick", 0)
                ok, _ = rag.study_library_entry(agent, entry_id, lib_entries, day, tick)
                if ok:
                    if agent.profession_level >= 10:
                        agent.profession_xp = min(1000.0, agent.profession_xp + 3.0)
                    else:
                        agent.profession_xp += 3.0
                        while (
                            agent.profession_level < 10
                            and agent.profession_xp >= agent.profession_level * 100.0
                        ):
                            agent.profession_level += 1
                        if agent.profession_level >= 10:
                            agent.profession_xp = min(1000.0, agent.profession_xp)
                    return True

        return False
