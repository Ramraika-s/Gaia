"""
sim_core/divine/autonomy.py
Autonomous Divine Agenda Engine for World Goddess & 5 Racial God-Mothers.
Follows Gaia v4.0 Sprint 5 specifications:
- Live (x, y, z, yaw, speed, activity_state, target_pos, speech_text) updated every tick.
- World Goddess: Audience Hall, Courtyard stroll, World Library on pending proposals,
  WTC on CPI spikes, and 5-Sister Council sessions.
- 5 God-Mothers: Govern Ring 1 Palaces, patrol city avenues, travel via Imperial Highways
  to Grand Divine Palace Courtyard for 5-Sister Council sessions.
- Direct God Orders: FOLLOW_GOD, PATROL_PLAZA, RETURN_PALACE, CONVENE_COUNCIL.
- Streams DeitySyncRecord array for WebSocket DEITY_SYNC.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from sim_core.schemas import DeitySlot, DeitySyncRecord, Vec3

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine

# Home positions and titles for the 6 Deities
DEITY_SPECS: dict[DeitySlot, dict[str, Any]] = {
    "world_goddess": {
        "name": "World Goddess",
        "title": "Cosmic Matriarch & Global Adjudicator",
        "race": "DIVINE",
        "home": Vec3(x=0.0, y=32.0, z=-15.0),
        "courtyard": Vec3(x=0.0, y=32.0, z=15.0),
        "dais_offset": 1.2,
    },
    "gm_human": {
        "name": "Human God-Mother",
        "title": "Protector of Mankind & Balance",
        "race": "HUMAN",
        "home": Vec3(x=355.37, y=18.0, z=1091.71),
        "city_id": "aurelia",
        "dais_offset": 3.2,
    },
    "gm_elf": {
        "name": "Elf God-Mother",
        "title": "Sylvan Matron & Living Harmony",
        "race": "ELF",
        "home": Vec3(x=1150.0, y=28.0, z=-2.0),
        "city_id": "sylvanor",
        "dais_offset": 3.2,
    },
    "gm_dragon": {
        "name": "Dragon God-Mother",
        "title": "Draconic Empress & Primordial Flame",
        "race": "DRAGON",
        "home": Vec3(x=355.37, y=68.0, z=-1095.71),
        "city_id": "drakonis_spire",
        "dais_offset": 3.2,
    },
    "gm_beasthuman": {
        "name": "Beasthuman God-Mother",
        "title": "Wild Pack Guardian & Primal Strength",
        "race": "BEASTHUMAN",
        "home": Vec3(x=-930.36, y=24.0, z=673.95),
        "city_id": "fenris_hold",
        "dais_offset": 3.2,
    },
    "gm_demon": {
        "name": "Demon God-Mother",
        "title": "Infernal Sovereign & Abyssal Mistress",
        "race": "DEMON",
        "home": Vec3(x=-930.36, y=42.0, z=-677.95),
        "city_id": "malakor",
        "dais_offset": 3.2,
    },
}

PALACE_COURTYARD_DAIS = Vec3(x=0.0, y=32.0, z=15.0)


class AutonomousDeity:
    """Live state for an autonomous deity in the world."""

    def __init__(self, slot: DeitySlot, spec: dict[str, Any]) -> None:
        self.slot: DeitySlot = slot
        self.name: str = spec["name"]
        self.title: str = spec["title"]
        self.race: str = spec["race"]
        self.home_pos: Vec3 = spec["home"].model_copy()
        self.pos: Vec3 = spec["home"].model_copy()
        self.yaw: float = 0.0
        self.speed: float = 0.0
        self.activity_state: str = "AUDIENCE" if slot == "world_goddess" else "GOVERNING"
        self.target_pos: Vec3 | None = None
        self.speech_text: str = ""
        self.speech_ticks_remaining: int = 0
        self.current_order: str | None = None
        self.current_agenda: str = "AUDIENCE" if slot == "world_goddess" else "GOVERNING"
        self.dais_offset: float = float(spec.get("dais_offset", 1.2))

    def set_speech(self, text: str, duration_ticks: int = 12) -> None:
        self.speech_text = text
        self.speech_ticks_remaining = duration_ticks

    def step_speech(self) -> None:
        if self.speech_ticks_remaining > 0:
            self.speech_ticks_remaining -= 1
            if self.speech_ticks_remaining <= 0:
                self.speech_text = ""

    def to_sync_record(self) -> DeitySyncRecord:
        return DeitySyncRecord(
            id=self.slot,
            name=self.name,
            title=self.title,
            race=self.race,
            x=round(self.pos.x, 2),
            y=round(self.pos.y, 2),
            z=round(self.pos.z, 2),
            yaw=round(self.yaw, 3),
            speed=round(self.speed, 2),
            activity=self.activity_state,
            speech_text=self.speech_text,
        )


class DivineAutonomyEngine:
    """
    Simulates the movement, daily agendas, and council travels of all 6 Deities.
    """

    def __init__(self, engine: SimulationEngine | None = None) -> None:
        self.engine = engine
        self.deities: dict[DeitySlot, AutonomousDeity] = {}
        for slot, spec in DEITY_SPECS.items():
            self.deities[slot] = AutonomousDeity(slot, spec)

    def issue_god_order(
        self,
        order: str,
        target_deity_slot: DeitySlot | None = None,
        target_pos: Vec3 | None = None,
    ) -> str:
        """
        Processes direct God orders:
        FOLLOW_GOD, PATROL_PLAZA, RETURN_PALACE, CONVENE_COUNCIL.
        """
        order_upper = order.upper()
        if order_upper == "CONVENE_COUNCIL":
            # Call all 5 God-Mothers to the Grand Divine Palace Courtyard
            for slot, deity in self.deities.items():
                if slot == "world_goddess":
                    deity.current_order = "CONVENE_COUNCIL"
                    deity.current_agenda = "CONVENE_COUNCIL"
                    deity.target_pos = PALACE_COURTYARD_DAIS.model_copy()
                    deity.activity_state = "CONVENING_COUNCIL"
                    deity.set_speech("By Divine Decree, I convene the 5-Sister Council!")
                else:
                    deity.current_order = "CONVENE_COUNCIL"
                    deity.current_agenda = "CONVENE_COUNCIL"
                    # Spread God-Mothers around dais
                    ang = math.pi * 0.4 * len(deity.slot)
                    deity.target_pos = Vec3(
                        x=round(PALACE_COURTYARD_DAIS.x + 8.0 * math.cos(ang), 2),
                        y=32.0,
                        z=round(PALACE_COURTYARD_DAIS.z + 8.0 * math.sin(ang), 2),
                    )
                    deity.activity_state = "TRAVELED_TO_COUNCIL"
                    deity.set_speech("I heed the summons of the Imperial Acropolis.")
            return "Convened 5-Sister Council at Grand Divine Palace Courtyard."

        target_slots = [target_deity_slot] if target_deity_slot else list(self.deities.keys())
        for s in target_slots:
            if not s or s not in self.deities:
                continue
            deity = self.deities[s]
            deity.current_order = order_upper

            if order_upper == "FOLLOW_GOD":
                if self.engine:
                    g_pos = self.engine.god_avatar_pos
                    deity.target_pos = Vec3(x=g_pos.x + 2.5, y=g_pos.y, z=g_pos.z + 2.5)
                deity.activity_state = "FOLLOWING_GOD"
                deity.set_speech("I accompany You, Lord.")

            elif order_upper == "PATROL_PLAZA":
                deity.target_pos = Vec3(x=0.0, y=24.0, z=180.0)  # Central Basin
                deity.activity_state = "PATROLLING_PLAZA"
                deity.set_speech("I shall oversee the central mortals.")

            elif order_upper == "RETURN_PALACE":
                deity.target_pos = deity.home_pos.model_copy()
                deity.activity_state = "RETURNING_HOME"
                deity.set_speech("Returning to the divine seat.")

        return f"Order '{order_upper}' delivered to {len(target_slots)} deities."

    def step(self, current_tick: int) -> None:
        """Updates deity agendas, movement interpolation, and speech timers."""
        goddess = self.deities.get("world_goddess")

        # 1. World Goddess Autonomous Agenda (if no active direct God order)
        if goddess and not goddess.current_order:
            # Check for pending library proposals
            has_pending_books = False
            if self.engine and hasattr(self.engine, "governance_engine"):
                has_pending_books = any(
                    p.status == "PENDING_DAUGHTERS"
                    for p in self.engine.governance_engine.library_proposals.values()
                )

            # Check WTC CPI
            cpi = 1.0
            if self.engine and hasattr(self.engine, "wtc"):
                cpi = getattr(self.engine.wtc, "fisher_cpi", 1.0)

            if has_pending_books:
                if goddess.activity_state != "INSPECTING_LIBRARY":
                    goddess.target_pos = Vec3(x=175.0, y=24.0, z=160.0)  # Library Door
                    goddess.activity_state = "INSPECTING_LIBRARY"
                    goddess.set_speech(
                        "I go to review the scholars' petitions in the World Library."
                    )
            elif cpi > 1.25:
                if goddess.activity_state != "INSPECTING_WTC":
                    goddess.target_pos = Vec3(x=-175.0, y=24.0, z=160.0)  # WTC Door
                    goddess.activity_state = "INSPECTING_WTC"
                    goddess.set_speech("The coin weakens; I shall inspect the World Trade Centre.")
            else:
                # Normal palace routine: alternate between Audience Hall and Courtyard stroll
                tick_cycle = current_tick % 600
                if tick_cycle < 350 and goddess.activity_state != "AUDIENCE":
                    goddess.target_pos = goddess.home_pos.model_copy()
                    goddess.activity_state = "AUDIENCE"
                elif tick_cycle >= 350 and goddess.activity_state != "COURTYARD_STROLL":
                    goddess.target_pos = PALACE_COURTYARD_DAIS.model_copy()
                    goddess.activity_state = "COURTYARD_STROLL"

        # 2. God-Mothers Autonomous Routine (if no active direct God order)
        for slot in ("gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"):
            gm = self.deities.get(slot)
            if not gm or gm.current_order:
                continue

            # Periodically stroll city center and gates
            tick_mod = (current_tick + hash(slot)) % 400
            if tick_mod < 250 and gm.activity_state != "GOVERNING":
                gm.target_pos = gm.home_pos.model_copy()
                gm.activity_state = "GOVERNING"
            elif tick_mod >= 250 and gm.activity_state != "CITY_PATROL":
                # Offset 35m outward from palace
                ang = math.pi * 0.4 * (tick_mod % 5)
                gm.target_pos = Vec3(
                    x=round(gm.home_pos.x + 35.0 * math.cos(ang), 2),
                    y=gm.home_pos.y,
                    z=round(gm.home_pos.z + 35.0 * math.sin(ang), 2),
                )
                gm.activity_state = "CITY_PATROL"

        # 3. Dynamic Movement Stepping
        for deity in self.deities.values():
            deity.step_speech()

            # If following God Avatar, update target dynamically
            if deity.current_order == "FOLLOW_GOD" and self.engine:
                g_pos = self.engine.god_avatar_pos
                deity.target_pos = Vec3(x=g_pos.x + 2.5, y=g_pos.y, z=g_pos.z + 2.5)

            if deity.target_pos is not None:
                dx = deity.target_pos.x - deity.pos.x
                dz = deity.target_pos.z - deity.pos.z
                dist = math.hypot(dx, dz)

                if dist < 1.5:
                    # Arrived at destination
                    deity.pos.x = deity.target_pos.x
                    deity.pos.z = deity.target_pos.z
                    deity.speed = 0.0
                    deity.target_pos = None
                    if deity.current_order in ("RETURN_PALACE", "PATROL_PLAZA"):
                        deity.current_order = None
                else:
                    move_speed = 3.5  # meters per second
                    dt = 0.5  # 2 Hz simulation tick
                    step = min(dist, move_speed * dt)
                    deity.pos.x += (dx / dist) * step
                    deity.pos.z += (dz / dist) * step
                    deity.yaw = round(math.atan2(dx, dz), 3)
                    deity.speed = move_speed

                # Ground elevation look-up
                if self.engine and hasattr(self.engine, "heightmap"):
                    try:
                        elev = self.engine.heightmap.get_elevation(deity.pos.x, deity.pos.z)
                        deity.pos.y = elev + deity.dais_offset
                    except Exception:
                        pass
            else:
                deity.speed = 0.0

    def get_sync_records(self) -> list[DeitySyncRecord]:
        return [d.to_sync_record() for d in self.deities.values()]
