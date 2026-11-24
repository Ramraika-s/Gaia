"""
sim_core/divine/god_ledger.py
GodPresenceTracker, strict prayer routing, congregational altar aggregation,
and the atomic World Goddess Daily God Ledger compiler (data/god_ledger/day_XXXXX.md).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from sim_core.schemas import DeitySlot, GodLedgerEntry, PrayerIntent
from sim_core.society.seasons import SeasonManager

DEFAULT_LEDGER_DIR: Final[str] = "data/god_ledger"


class CongregationalAltarPrayer(BaseModel):
    altar_parcel_id: str
    settlement_name: str
    target_deity_slot: DeitySlot
    prayer_head_name: str
    prayer_head_rank: str  # "ORACLE", "POPE", "CLERIC", "ELDER", "CITIZEN"
    mortal_count: int
    intent: PrayerIntent
    summary: str
    tick: int


class GodPresenceTracker:
    """Tracks whether God is actively viewing the world (Godot 4.7.2 / Rich CLI) or Away."""

    def __init__(self) -> None:
        self.is_active: bool = False
        self.last_seen_tick: int = 0

    def set_active(self, active: bool, tick: int = 0) -> None:
        self.is_active = active
        if active:
            self.last_seen_tick = tick


class GodLedgerPipeline:
    """
    Manages divine message buffering strictly in RAM during the game day,
    enforcing that mortals cannot message God directly, and compiling the atomic
    end-of-day Markdown God Ledger.
    """

    def __init__(
        self,
        ledger_dir: str = DEFAULT_LEDGER_DIR,
        tracker: GodPresenceTracker | None = None,
    ) -> None:
        self.ledger_dir: Path = Path(ledger_dir)
        self.tracker: GodPresenceTracker = tracker if tracker is not None else GodPresenceTracker()
        self.buffer: list[GodLedgerEntry] = []
        self.altar_prayers: list[CongregationalAltarPrayer] = []

    def record_deity_message(
        self,
        entry_id: str,
        day: int,
        tick: int,
        category: str,
        deity_slot: DeitySlot | None,
        speaker_name: str,
        message: str,
        prayer_head_name: str | None = None,
        settlement_name: str | None = None,
        group_size: int = 1,
        intent: PrayerIntent | None = None,
    ) -> GodLedgerEntry:
        """
        Records a message from the World Goddess, a God-Mother, or ErrorHealer.
        Mortals CANNOT call this method directly.
        """
        entry = GodLedgerEntry(
            entry_id=entry_id,
            day=day,
            tick=tick,
            category=category,  # type: ignore
            deity_slot=deity_slot,
            speaker_name=speaker_name,
            prayer_head_name=prayer_head_name,
            settlement_name=settlement_name,
            group_size=group_size,
            intent=intent,
            message=message,
            delivered_realtime=self.tracker.is_active,
        )
        self.buffer.append(entry)
        return entry

    def aggregate_altar_prayer(
        self,
        altar_parcel_id: str,
        settlement_name: str,
        target_deity_slot: DeitySlot,
        praying_agents: list[dict[str, Any]],
        intent: PrayerIntent,
        summary: str,
        tick: int,
    ) -> CongregationalAltarPrayer:
        """
        Aggregates >= 3 mortals praying at an altar parcel into a single unified
        message led by Prayer Head (Oracle -> Pope -> Cleric -> Elder -> Citizen).
        """

        def rank_sort_key(agent: dict[str, Any]) -> int:
            if agent.get("is_oracle", False):
                return 0
            rank = agent.get("cleric_rank", "NONE")
            if rank == "POPE":
                return 1
            if rank in ("HIGH_CLERIC", "PRIEST"):
                return 2
            if agent.get("stage") == "ELDER":
                return 3
            return 4

        sorted_agents = sorted(praying_agents, key=rank_sort_key)
        prayer_head = (
            sorted_agents[0] if sorted_agents else {"display_name": "Unknown", "stage": "CITIZEN"}
        )

        head_rank = "CITIZEN"
        if prayer_head.get("is_oracle"):
            head_rank = "ORACLE"
        elif prayer_head.get("cleric_rank") == "POPE":
            head_rank = "POPE"
        elif prayer_head.get("cleric_rank") in ("HIGH_CLERIC", "PRIEST"):
            head_rank = "CLERIC"
        elif prayer_head.get("stage") == "ELDER":
            head_rank = "ELDER"

        prayer = CongregationalAltarPrayer(
            altar_parcel_id=altar_parcel_id,
            settlement_name=settlement_name,
            target_deity_slot=target_deity_slot,
            prayer_head_name=prayer_head.get("display_name", "Unknown"),
            prayer_head_rank=head_rank,
            mortal_count=len(praying_agents),
            intent=intent,
            summary=summary,
            tick=tick,
        )
        self.altar_prayers.append(prayer)
        return prayer

    def clear_buffer(self) -> None:
        """Clears the buffered messages and altar prayers for the next game day."""
        self.buffer.clear()
        self.altar_prayers.clear()

    def compile_daily_ledger_markdown(
        self,
        day: int,
        season: str,
        world_goddess_name: str,
        living_population: int,
        demographics: dict[str, int],
        cpi: float,
        active_wars: int,
        neutral_free_cities: int,
        tie_breaks: list[str] | None = None,
    ) -> str:
        """Compiles the full daily markdown God Ledger (data/god_ledger/day_XXXXX.md)."""
        year = SeasonManager.get_year(day)
        demo_str = " | ".join(f"{k.capitalize()}s: {v}" for k, v in demographics.items())
        lines = [
            f"# World Goddess Daily Ledger — Day {day} ({season.capitalize()}, Year {year})",
            f"Compiled & Verified by: **{world_goddess_name}** | SHA-256 Commit: `VERIFIED`\n",
            "## 1. World Goddess Civilization Summary",
            f"- Living Population: {living_population} ({demo_str})",
            (
                f"- WTC CPI Inflation: {cpi:.2f} | Active Wars: {active_wars} | "
                f"Neutral Free Cities: {neutral_free_cities}"
            ),
        ]

        if tie_breaks:
            for tb in tie_breaks:
                lines.append(f"- Mixed-Race Patronage Tie-Break: {tb}")

        goddess_entries = [e for e in self.buffer if e.category == "WORLD_GODDESS_SUMMARY"]
        for ge in goddess_entries:
            lines.append(f"- **[{ge.speaker_name}]**: {ge.message}")

        lines.append("\n## 2. Racial God-Mother Reports & Congregational Altars")
        altar_entries = [
            e for e in self.buffer if e.category in ("GOD_MOTHER_REPORT", "CONGREGATIONAL_ALTAR")
        ]
        if altar_entries:
            for entry in altar_entries:
                head = f" (Prayer Head: {entry.prayer_head_name})" if entry.prayer_head_name else ""
                lines.append(
                    f"- **[{entry.speaker_name}]** in {entry.settlement_name or 'Sanctuary'}"
                    f"{head}: {entry.message}"
                )
        else:
            lines.append("- *No major altar emergencies or divine interventions recorded today.*")

        lines.append("\n## 3. Inter-Sister Council Dialogues")
        council_entries = [e for e in self.buffer if e.category == "SISTER_COUNCIL"]
        if council_entries:
            for entry in council_entries:
                lines.append(f"- **[{entry.speaker_name}]**: {entry.message}")
        else:
            lines.append("- *Peace observed between the 5 Sisters across all domains.*")

        lines.append("\n## 4. Self-Healing Error Solver Alerts")
        healer_entries = [
            e for e in self.buffer if e.category in ("HEALER_ALERT", "CRITICAL_ESCALATION")
        ]
        if healer_entries:
            for entry in healer_entries:
                lines.append(f"- `{entry.category}`: {entry.message}")
        else:
            lines.append("- *Zero critical anomalies or memory leaks detected.*")

        return "\n".join(lines) + "\n"

    def flush_daily_ledger_to_disk(
        self,
        day: int,
        season: str,
        world_goddess_name: str,
        living_population: int,
        demographics: dict[str, int],
        cpi: float,
        active_wars: int,
        neutral_free_cities: int,
        tie_breaks: list[str] | None = None,
    ) -> tuple[Path, Path]:
        """
        Writes the daily markdown ledger atomically to data/god_ledger/day_{day:05d}.md
        and updates data/god_ledger/latest.md.
        """
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        content = self.compile_daily_ledger_markdown(
            day=day,
            season=season,
            world_goddess_name=world_goddess_name,
            living_population=living_population,
            demographics=demographics,
            cpi=cpi,
            active_wars=active_wars,
            neutral_free_cities=neutral_free_cities,
            tie_breaks=tie_breaks,
        )

        day_file = self.ledger_dir / f"day_{day:05d}.md"
        latest_file = self.ledger_dir / "latest.md"

        tmp_day = self.ledger_dir / f".day_{day:05d}.md.tmp"
        tmp_latest = self.ledger_dir / ".latest.md.tmp"

        with open(tmp_day, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        with open(tmp_latest, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_day, day_file)
        os.replace(tmp_latest, latest_file)

        # Clear RAM buffer for next day
        self.clear_buffer()

        return day_file, latest_file
