"""
sim_core/god_console/cli.py
Interactive Rich terminal God Console.
Supports inspect and intervene commands, DuckDB read-only analytics,
and non-interactive command execution for testing and automation.
Follows ARCHITECTURE.md Section 7, SOCIETY_AND_GOVERNANCE_SPEC.md Section 7,
and DATA_SCHEMA_AND_WORLD_GODDESS.md Section 3.
"""

from __future__ import annotations

import io
import shlex
import uuid
from typing import TYPE_CHECKING

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sim_core.persistence.db import run_analytics_query
from sim_core.schemas import CommitProposal, FatalityRecord, WorldLibraryEntry

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine


class RichGodConsole:
    """
    Rich terminal God Console interface for God (Admin / User).
    Provides deep inspection and omnipotent intervention over the civilization.
    """

    def __init__(
        self,
        engine: SimulationEngine,
        console: Console | None = None,
    ) -> None:
        self.engine = engine
        self.console = console if console is not None else Console(color_system="auto")

    # =========================================================================
    # Interactive God Console REPL
    # =========================================================================

    def start_interactive_loop(self) -> None:
        """Starts the interactive God Terminal CLI REPL."""
        self.engine.god_presence.set_active(True, self.engine.current_tick)
        self.console.print(
            Panel.fit(
                "[bold gold3]Gaia — Persistent AI Civilization Engine[/bold gold3]\n"
                "[dim]Type 'help' for command list, 'status' for overview, 'exit' to quit.[/dim]",
                title="[bold white]God Console[/bold white]",
                border_style="gold3",
            )
        )

        try:
            while True:
                try:
                    cmd_line = Prompt.ask("[bold gold3]God[/bold gold3] > ")
                    cmd_line = cmd_line.strip()
                    if not cmd_line:
                        continue
                    if cmd_line.lower() in ("exit", "quit", "q"):
                        break
                    output = self.execute_command(cmd_line)
                    if output:
                        self.console.print(output)
                except (KeyboardInterrupt, EOFError):
                    break
        finally:
            self.engine.god_presence.set_active(False)
            self.console.print("[dim]Exiting God Console... Presence set to AWAY.[/dim]")

    # =========================================================================
    # Non-Interactive Command Dispatcher
    # =========================================================================

    def execute_command(self, cmd_line: str) -> str:
        """
        Executes a single God Console command line and returns formatted output.
        Designed for both REPL output and automated test verification.
        """
        line = cmd_line.strip()
        if not line:
            return ""

        try:
            tokens = shlex.split(line)
        except Exception as exc:
            return f"Error parsing command line: {exc}"

        if not tokens:
            return ""

        verb = tokens[0].lower()
        args = tokens[1:]

        # Inspect commands
        if verb == "status":
            return self._cmd_status()
        elif verb == "pop":
            return self._cmd_pop(args)
        elif verb == "fatalities":
            return self._cmd_fatalities()
        elif verb == "crimes":
            return self._cmd_crimes(args)
        elif verb == "nations":
            return self._cmd_nations()
        elif verb == "borders":
            return self._cmd_borders()
        elif verb == "elections":
            return self._cmd_elections()
        elif verb == "religions":
            return self._cmd_religions()
        elif verb == "deities":
            return self._cmd_deities()
        elif verb == "council":
            return self._cmd_council()
        elif verb == "elders":
            return self._cmd_elders()
        elif verb == "wtc":
            if args and args[0].lower() in ("freeze", "tariff"):
                return self._cmd_wtc_action(args)
            return self._cmd_wtc()
        elif verb == "bank":
            if args and args[0].lower() in ("grant", "forgive"):
                return self._cmd_bank_action(args)
            return self._cmd_bank()
        elif verb == "parcel":
            return self._cmd_parcel(args)
        elif verb == "traditions":
            return self._cmd_traditions()
        elif verb == "library":
            return self._cmd_library(args)
        elif verb == "codex":
            return self._cmd_codex(args)
        elif verb == "ledger":
            return self._cmd_ledger(args)
        elif verb == "analytics":
            return self._cmd_analytics(args)
        elif verb == "inspect":
            return self._cmd_inspect(args)

        # Intervene commands
        elif verb == "name_deity":
            return self._cmd_name_deity(args)
        elif verb == "spawn":
            return self._cmd_spawn(args)
        elif verb == "bless":
            return self._cmd_bless(args)
        elif verb == "curse":
            return self._cmd_curse(args)
        elif verb == "smite":
            return self._cmd_smite(args)
        elif verb == "war":
            return self._cmd_war(args)
        elif verb == "coronate":
            return self._cmd_coronate(args)
        elif verb == "appoint_pope":
            return self._cmd_appoint_pope(args)
        elif verb == "decree":
            return self._cmd_decree(args)
        elif verb == "speed":
            return self._cmd_speed(args)
        elif verb == "pause":
            return self._cmd_pause()
        elif verb == "resume":
            return self._cmd_resume()
        elif verb == "step":
            return self._cmd_step(args)
        elif verb == "save":
            return self._cmd_save()
        elif verb == "rewind":
            return self._cmd_rewind(args)
        elif verb == "shutdown":
            return self._cmd_shutdown()
        elif verb == "help":
            return self._cmd_help()
        else:
            return f"Unknown command: '{verb}'. Type 'help' for available commands."

    # =========================================================================
    # Inspect Implementations
    # =========================================================================

    def _render_table_to_str(self, table: Table) -> str:
        """Helper to capture Rich Table rendering into string format."""
        buf = io.StringIO()
        sub_console = Console(file=buf, force_terminal=False, width=100)
        sub_console.print(table)
        return buf.getvalue().rstrip()

    def _cmd_status(self) -> str:
        """Overview of simulation tick, time, economy, population, and host RAM."""
        living = sum(1 for a in self.engine.agents.values() if a.alive)
        quarantined = sum(1 for a in self.engine.agents.values() if a.quarantined)
        total_m = self.engine.bank.calculate_total_circulation(list(self.engine.agents.values()))
        cpi = self.engine.wtc.cpi
        try:
            mem_pct = psutil.virtual_memory().percent
        except Exception:
            mem_pct = 0.0

        table = Table(title="Civilization Status", border_style="gold3")
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="green")

        tick_str = f"Day {self.engine.current_day} (Tick {self.engine.current_tick})"
        table.add_row("Day / Tick", tick_str)
        table.add_row("Season", str(self.engine.current_season))
        table.add_row("Speed", f"{self.engine.speed:.1f}x")
        table.add_row("State", "RUNNING" if self.engine.is_running else "PAUSED")
        table.add_row("Living Agents", f"{living} (Quarantined: {quarantined})")
        table.add_row("Circulating Money (M)", f"{total_m:.2f} credits")
        table.add_row("Bank Reserve", f"{self.engine.bank.reserve_credits:.2f} credits")
        table.add_row("WTC CPI", f"{cpi:.3f}")
        table.add_row("Host RAM Usage", f"{mem_pct:.1f}%")
        table.add_row("God Presence", "ACTIVE" if self.engine.god_presence.is_active else "AWAY")

        return self._render_table_to_str(table)

    def _cmd_pop(self, args: list[str]) -> str:
        """Population breakdown by race and life stage."""
        filter_race = args[0].upper() if args else None
        agents = [a for a in self.engine.agents.values() if a.alive]
        if filter_race and filter_race in ("HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"):
            agents = [a for a in agents if a.race == filter_race]

        table = Table(title="Population Breakdown", border_style="cyan")
        table.add_column("Race", style="bold")
        table.add_column("Infant", justify="right")
        table.add_column("Child", justify="right")
        table.add_column("Adult", justify="right")
        table.add_column("Elder", justify="right")
        table.add_column("Total Alive", justify="right", style="green")

        races = [filter_race] if filter_race else ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
        for r in races:
            sub = [a for a in agents if a.race == r]
            infants = sum(1 for a in sub if a.stage == "INFANT")
            children = sum(1 for a in sub if a.stage == "CHILD")
            adults = sum(1 for a in sub if a.stage == "ADULT")
            elders = sum(1 for a in sub if a.stage == "ELDER")
            table.add_row(r, str(infants), str(children), str(adults), str(elders), str(len(sub)))

        return self._render_table_to_str(table)

    def _cmd_fatalities(self) -> str:
        """Displays recorded mortality records."""
        fatalities = self.engine.judiciary.fatality_index
        if not fatalities:
            return "No recorded fatalities in current cycle."

        table = Table(title=f"Recorded Fatalities (Total: {len(fatalities)})", border_style="red")
        table.add_column("Agent ID")
        table.add_column("Name")
        table.add_column("Race")
        table.add_column("Stage")
        table.add_column("Day", justify="right")
        table.add_column("Season")
        table.add_column("Cause", style="bold red")

        for f in fatalities[-20:]:  # Last 20
            table.add_row(
                f.agent_id,
                f.display_name,
                f.race,
                f.stage_at_death,
                str(f.day_of_death),
                f.season_of_death,
                f.cause,
            )

        return self._render_table_to_str(table)

    def _cmd_crimes(self, args: list[str]) -> str:
        """Lists active and adjudicated judiciary cases."""
        cases = list(self.engine.judiciary.cases.values())
        if args:
            target = args[0]
            cases = [c for c in cases if c.accused_id == target or c.plaintiff_id == target]

        if not cases:
            return "No judiciary cases recorded."

        table = Table(title="Judiciary Cases", border_style="magenta")
        table.add_column("Case ID")
        table.add_column("Accused")
        table.add_column("Offense")
        table.add_column("Status")
        table.add_column("Ruling")

        for c in cases[-15:]:
            table.add_row(
                c.case_id,
                c.accused_id,
                c.offense_type,
                c.status,
                c.ruling or "PENDING",
            )

        return self._render_table_to_str(table)

    def _cmd_nations(self) -> str:
        """Lists polities, tiers, leaders, borders, and war status."""
        polities = list(self.engine.political_engine.polities.values())
        if not polities:
            return "No polities registered yet."

        table = Table(title="Polities & Nations", border_style="blue")
        table.add_column("Polity ID")
        table.add_column("Name")
        table.add_column("Tier")
        table.add_column("Government")
        table.add_column("Parcels", justify="right")
        table.add_column("Wars", style="bold red")
        table.add_column("Neutral Free City")

        for p in polities:
            table.add_row(
                p.polity_id,
                p.name,
                p.tier,
                p.government_type,
                str(len(p.owned_parcel_ids)),
                str(len(p.at_war_with)),
                "YES" if p.is_neutral_free_city else "NO",
            )

        return self._render_table_to_str(table)

    def _cmd_borders(self) -> str:
        """Lists parcel border counts per settlement/polity."""
        table = Table(title="Territory Borders", border_style="blue")
        table.add_column("Polity ID")
        table.add_column("Name")
        table.add_column("Parcel Count", justify="right")

        for p in self.engine.political_engine.polities.values():
            table.add_row(p.polity_id, p.name, str(len(p.owned_parcel_ids)))

        return self._render_table_to_str(table)

    def _cmd_elections(self) -> str:
        """Shows election cycles and leaders."""
        table = Table(title="Leadership & Elections", border_style="cyan")
        table.add_column("Polity ID")
        table.add_column("Name")
        table.add_column("Leader ID")
        table.add_column("Gov Type")
        table.add_column("Next Election Day", justify="right")

        for p in self.engine.political_engine.polities.values():
            table.add_row(
                p.polity_id,
                p.name,
                p.leader_id or "NONE",
                p.government_type,
                str(p.next_election_day),
            )

        return self._render_table_to_str(table)

    def _cmd_religions(self) -> str:
        """Lists organized religions and altars."""
        religions = list(self.engine.religion_mgr.religions.values())
        if not religions:
            return "No organized religions established."

        table = Table(title="Religions & Faiths", border_style="gold3")
        table.add_column("Religion ID")
        table.add_column("Name")
        table.add_column("Patron Deity")
        table.add_column("Pope ID")
        table.add_column("Tithe Rate", justify="right")
        table.add_column("Altars", justify="right")

        for r in religions:
            table.add_row(
                r.religion_id,
                r.name,
                r.patron_deity_slot or "WORLD_GODDESS",
                r.pope_id or "NONE",
                f"{r.tithe_rate * 100:.1f}%",
                str(len(r.altar_parcel_ids)),
            )

        return self._render_table_to_str(table)

    def _cmd_deities(self) -> str:
        """Displays Divine Family hierarchy, energy, and names."""
        table = Table(title="Divine Family Hierarchy", border_style="gold3")
        table.add_column("Slot", style="bold")
        table.add_column("Role")
        table.add_column("Bestowed Name", style="bold gold3")
        table.add_column("Patron Race")
        table.add_column("Divine Energy", justify="right")
        table.add_column("Oracles", justify="right")

        for entity in self.engine.divine_hierarchy.entities.values():
            table.add_row(
                entity.slot,
                entity.role,
                entity.bestowed_name,
                entity.patron_race or "ALL",
                f"{entity.divine_energy:.1f}",
                str(len(entity.oracle_agent_ids)),
            )

        return self._render_table_to_str(table)

    def _cmd_council(self) -> str:
        """Shows recent Sister Council dialogues and truces."""
        history = self.engine.sister_council.council_history
        if not history:
            return "No Sister Council sessions recorded."

        lines = [f"[bold]Sister Council Sessions ({len(history)} total):[/bold]"]
        for sess in history[-5:]:
            lines.append(
                f"- [cyan]{sess.session_type}[/cyan] ({sess.topic}) - Status: {sess.status} "
                f"(Attendees: {', '.join(sess.attendees)})"
            )
            for m in sess.messages[-3:]:
                lines.append(f"  [dim]{m.sender_slot}:[/dim] {m.message}")

        return "\n".join(lines)

    def _cmd_elders(self) -> str:
        """Displays Appointed Library Elders per nation."""
        elders = self.engine.governance_engine.library_council_elders
        if not elders:
            return "No Appointed Library Elders currently registered."

        table = Table(title="Council of Appointed Library Elders", border_style="cyan")
        table.add_column("Nation ID")
        table.add_column("Elder Agent IDs")

        for nation_id, elist in elders.items():
            table.add_row(nation_id, ", ".join(elist))

        return self._render_table_to_str(table)

    def _cmd_wtc(self) -> str:
        """Displays WTC market prices and Fisher CPI."""
        title_str = f"World Trade Centre (CPI: {self.engine.wtc.cpi:.3f})"
        table = Table(title=title_str, border_style="green")
        table.add_column("Commodity")
        table.add_column("Price (Credits)", justify="right")
        table.add_column("24h Volume", justify="right")

        for comm, price in self.engine.wtc.prices.items():
            vol = self.engine.wtc.volume_24h.get(comm, 0.0)
            table.add_row(comm, f"{price:.2f}", f"{vol:.1f}")

        return self._render_table_to_str(table)

    def _cmd_bank(self) -> str:
        """Displays World Bank metrics and loan status."""
        total_m = self.engine.bank.calculate_total_circulation(list(self.engine.agents.values()))
        table = Table(title="World Bank Metrics", border_style="green")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        table.add_row("Circulating Money Supply (M)", f"{total_m:.2f} credits")
        table.add_row("Bank Vault Reserves", f"{self.engine.bank.reserve_credits:.2f} credits")
        table.add_row("Interest Rate (Base)", f"{self.engine.bank.interest_rate * 100:.2f}%")
        table.add_row("Active Loans", str(len(self.engine.bank.loans)))
        table.add_row("Defaulted Loans", str(len(self.engine.bank.defaulted_cases)))

        return self._render_table_to_str(table)

    def _cmd_parcel(self, args: list[str]) -> str:
        """Inspects a specific 16x16m chunk parcel."""
        if len(args) < 2:
            return "Usage: parcel <cx> <cz>"
        try:
            cx, cz = int(args[0]), int(args[1])
        except ValueError:
            return "Coordinates must be integers: parcel <cx> <cz>"

        pid = f"{cx}_{cz}"
        parcel = self.engine.property_mgr.parcels.get(pid)
        if not parcel:
            return f"Parcel '{pid}' is unregistered wilderness (UNCLAIMED)."

        table = Table(title=f"Parcel {pid}", border_style="yellow")
        table.add_column("Field")
        table.add_column("Value")

        table.add_row("Owner ID", parcel.owner_id or "NONE")
        table.add_row("Owner Type", parcel.owner_type)
        table.add_row("Settlement ID", parcel.settlement_id or "WILDERNESS")
        table.add_row("Nation ID", parcel.nation_id or "NONE")
        table.add_row("Assessed Value", f"{parcel.assessed_value:.2f} credits")
        table.add_row(
            "For Sale Price",
            f"{parcel.for_sale_price:.2f}" if parcel.for_sale_price else "NOT FOR SALE",
        )

        return self._render_table_to_str(table)

    def _cmd_traditions(self) -> str:
        """Lists active emergent traditions."""
        trads = self.engine.traditions.settlement_traditions
        if not trads:
            return "No traditions recorded yet."

        lines = [f"[bold]Active Cultural Traditions ({len(trads)} settlements):[/bold]"]
        for s_id, t_list in trads.items():
            t_names = [t.name for t in t_list]
            lines.append(f"- [cyan]{s_id}[/cyan]: {', '.join(t_names)}")

        return "\n".join(lines)

    def _cmd_library(self, args: list[str]) -> str:
        """Inspects or edits World Library books: library [topic] | library edit ..."""
        lib = self.engine.governance_engine.library_entries
        if args and args[0].lower() == "edit":
            if len(args) < 5:
                return "Usage: library edit <topic> <volume_title> <author_id> <content>"
            topic = args[1]
            title = args[2]
            author = args[3]
            content = " ".join(args[4:])
            prop = CommitProposal(
                proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                tick=self.engine.current_tick,
                actor_id="GOD",
                kind="LIBRARY_ENTRY",
                bypass_god_check=True,
                payload={
                    "topic": topic,
                    "volume_title": title,
                    "author_id": author,
                    "text_content": content,
                },
            )
            v = self.engine.world_goddess.evaluate(prop)
            if v.status == "SUCCESS":
                entry = WorldLibraryEntry(
                    entry_id=f"lib_{topic}",
                    topic=topic,
                    title=title,
                    summary=content,
                    author_id=author,
                    author_proficiency=1.0,
                    created_tick=self.engine.current_tick,
                )
                self.engine.governance_engine.write_library_direct_god(entry)
            return f"Library edit for '{topic}': {v.status} ({v.reason})."

        if not lib:
            return "World Library is empty. No canonical books recorded yet."

        if args:
            topic = args[0]
            matches = [b for b in lib.values() if b.topic == topic]
            if matches:
                book = matches[0]
                return (
                    f"[bold gold3]{book.title}[/bold gold3] (Topic: {book.topic})\n"
                    f"Author: {book.author_id} | Read count: {book.read_count}\n\n"
                    f"{book.summary}"
                )
            return f"No canonical volume found for topic '{topic}'."

        table = Table(title=f"World Library Volumes ({len(lib)} total)", border_style="gold3")
        table.add_column("Topic")
        table.add_column("Volume Title")
        table.add_column("Author")
        table.add_column("Reads", justify="right")

        for b in lib.values():
            table.add_row(b.topic, b.title, b.author_id, str(b.read_count))

        return self._render_table_to_str(table)

    def _cmd_codex(self, args: list[str]) -> str:
        """Inspects or edits Divine Codex decrees and proposals."""
        gov = self.engine.governance_engine
        if args and args[0].lower() == "approve":
            if len(args) < 2:
                return "Usage: codex approve <proposal_id>"
            pid = args[1]
            success, reason, _ = gov.approve_codex_proposal_by_god(
                pid, self.engine.current_tick
            )
            res_str = "SUCCESS" if success else "FAILURE"
            return f"Codex proposal '{pid}' approval: {res_str} ({reason})."

        if args and args[0].lower() == "write":
            if len(args) < 3:
                return "Usage: codex write <decree_id> <decree_text> [param_key] [param_val]"
            decree_id = args[1]
            text = args[2]
            param_key = args[3] if len(args) > 3 else None
            param_val = float(args[4]) if len(args) > 4 else None
            prop = CommitProposal(
                proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                tick=self.engine.current_tick,
                actor_id="GOD",
                kind="DIVINE_CODEX_DECREE",
                bypass_god_check=True,
                payload={
                    "decree_id": decree_id,
                    "text_decree": text,
                    "parameter_key": param_key,
                    "parameter_val": param_val,
                },
            )
            v = self.engine.world_goddess.evaluate(prop)
            if v.status == "SUCCESS":
                gov.write_codex_direct_god(
                    title=decree_id,
                    text=text,
                    category="DECREE",
                    current_tick=self.engine.current_tick,
                    parameter_key=param_key,
                    parameter_value=param_val,
                )
            return f"Codex decree '{decree_id}' written: {v.status}."

        if args and args[0].lower() == "proposals":
            proposals = gov.codex_proposals
            if not proposals:
                return "No pending Divine Codex parameter override proposals."
            table = Table(title="Pending Divine Codex Proposals", border_style="magenta")
            table.add_column("Proposal ID")
            table.add_column("Proposer")
            table.add_column("Param Key")
            table.add_column("Override Value")
            table.add_column("Status")
            for p in proposals.values():
                table.add_row(
                    p.proposal_id,
                    p.proposer_slot,
                    p.parameter_key,
                    str(p.parameter_value_json),
                    p.status,
                )
            return self._render_table_to_str(table)

        codex = gov.codex_entries
        if not codex:
            return "Divine Codex contains no active divine rules or decrees."

        table = Table(title="Divine Codex (Recorded Decrees)", border_style="gold3")
        table.add_column("Entry ID")
        table.add_column("Title")
        table.add_column("Decree Text")
        table.add_column("Param Override")

        for r in codex.values():
            if r.parameter_key:
                param = f"{r.parameter_key} = {r.parameter_value_json}"
            else:
                param = "NONE"
            table.add_row(r.entry_id, r.title, r.text, param)

        return self._render_table_to_str(table)

    def _cmd_ledger(self, args: list[str]) -> str:
        """Prints God Ledger markdown."""
        target_day = int(args[0]) if args else (self.engine.current_day - 1)
        ledger_path = self.engine.god_ledger_dir / f"day_{target_day:05d}.md"
        if ledger_path.exists():
            return ledger_path.read_text(encoding="utf-8")
        latest_path = self.engine.god_ledger_dir / "latest.md"
        if latest_path.exists():
            return latest_path.read_text(encoding="utf-8")
        return f"No God Ledger file found for Day {target_day}."

    def _cmd_analytics(self, args: list[str]) -> str:
        """
        Executes DuckDB read-only analytical queries against data/civilization.db.
        Does not lock SQLite WAL writer.
        """
        if not args:
            return "Usage: analytics <demographics|mortality|patronage|wealth|query <SQL>>"

        sub = args[0].lower()
        db_path = str(self.engine.db_path)

        if sub == "demographics":
            sql = (
                "SELECT race, stage, COUNT(*) as pop, "
                "ROUND(AVG(credits), 2) as avg_credits, "
                "ROUND(AVG(credit_score), 1) as avg_cs "
                "FROM civ.agents WHERE alive = 1 "
                "GROUP BY race, stage "
                "ORDER BY race, stage;"
            )
        elif sub == "mortality":
            sql = (
                "SELECT race, cause, stage_at_death, season, COUNT(*) as deaths "
                "FROM civ.fatalities "
                "GROUP BY race, cause, stage_at_death, season "
                "ORDER BY deaths DESC;"
            )
        elif sub == "patronage":
            sql = (
                "SELECT COALESCE(patron_godmother_slot, 'UNCOMMITTED') as patron, "
                "COUNT(*) as count "
                "FROM civ.agents "
                "GROUP BY patron_godmother_slot "
                "ORDER BY count DESC;"
            )
        elif sub == "wealth":
            sql = (
                "SELECT race, COUNT(*) as count, "
                "ROUND(SUM(credits), 2) as total_credits, "
                "ROUND(AVG(credits), 2) as avg_credits "
                "FROM civ.agents "
                "GROUP BY race "
                "ORDER BY total_credits DESC;"
            )
        elif sub == "query":
            if len(args) < 2:
                return "Usage: analytics query <SQL_STATEMENT>"
            sql = " ".join(args[1:])
        else:
            return (
                f"Unknown analytics view '{sub}'. "
                "Available: demographics, mortality, patronage, wealth, query."
            )

        try:
            rows = run_analytics_query(db_path, sql)
        except Exception as exc:
            return f"Analytics query note/error: {exc}"

        if not rows:
            return f"Analytics [{sub}]: 0 rows returned (no records found in database)."

        cols = list(rows[0].keys())
        table = Table(title=f"DuckDB Analytics: {sub.upper()}", border_style="cyan")
        for col in cols:
            table.add_column(col)
        for r in rows[:30]:
            table.add_row(*[str(r[c]) for c in cols])

        return self._render_table_to_str(table)

    def _cmd_inspect(self, args: list[str]) -> str:
        """Inspects full details of an agent."""
        if not args:
            return "Usage: inspect <agent_id>"
        agent_id = args[0]
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."

        table = Table(title=f"Agent Card: {ag.display_name} ({ag.agent_id})", border_style="gold3")
        table.add_column("Field", style="bold cyan")
        table.add_column("Value")

        table.add_row("Race / Sub-lineage", f"{ag.race} ({ag.sub_lineage or 'None'})")
        table.add_row("Gender / Stage", f"{ag.gender} / {ag.stage}")
        table.add_row("Biological Age", f"{ag.age_days:.2f} days")
        table.add_row("Health / Max", f"{ag.health:.1f} / {ag.max_health:.1f}")
        table.add_row("Hunger / Stamina", f"{ag.hunger:.1f} / {ag.stamina:.1f}")
        table.add_row("Distress / Crying", f"{ag.distress:.2f} / {'YES' if ag.crying else 'NO'}")
        table.add_row("Credits / Score", f"{ag.credits:.2f} / {ag.credit_score:.0f}")
        table.add_row("Patron Deity Slot", str(ag.patron_godmother_slot or "UNCOMMITTED"))
        table.add_row("Position (X, Y, Z)", f"({ag.pos.x:.1f}, {ag.pos.y:.1f}, {ag.pos.z:.1f})")
        table.add_row("Alive / Quarantined", f"{ag.alive} / {ag.quarantined}")
        if ag.dragon_form:
            table.add_row("Dragon Form", ag.dragon_form)
        if ag.pregnant_ticks_remaining > 0:
            table.add_row("Pregnant Ticks Left", str(ag.pregnant_ticks_remaining))

        return self._render_table_to_str(table)

    # =========================================================================
    # Intervene Implementations
    # =========================================================================

    def _cmd_name_deity(self, args: list[str]) -> str:
        """Bestows custom name onto a deity: name_deity <slot> "<name>"."""
        if len(args) < 2:
            return 'Usage: name_deity <slot> "<name>"'
        slot = args[0].lower()
        name = args[1]

        if slot not in self.engine.divine_hierarchy.entities:
            return (
                f"Invalid deity slot '{slot}'. "
                "Valid: world_goddess, gm_human, gm_elf, gm_dragon, gm_beasthuman, gm_demon."
            )

        self.engine.divine_hierarchy.bestow_name(slot, name)  # type: ignore
        prop = CommitProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
            tick=self.engine.current_tick,
            actor_id="GOD",
            kind="NAME_DEITY",
            bypass_god_check=True,
            payload={"slot": slot, "bestowed_name": name},
        )
        verdict = self.engine.world_goddess.evaluate(prop)
        return f"Deity slot '{slot}' named '{name}'. Verdict: {verdict.status}."

    def _cmd_spawn(self, args: list[str]) -> str:
        """Spawns an agent: spawn <race> [sub_lineage] [gender]."""
        if not args:
            return "Usage: spawn <race> [sub_lineage] [gender]"
        race = args[0].upper()
        if race not in ("HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"):
            return "Invalid race. Must be HUMAN, ELF, DRAGON, BEASTHUMAN, or DEMON."

        sub_lineage = None
        gender = "GIRL"
        if len(args) > 1:
            val = args[1].upper()
            if val in ("CAT_KIN", "DWARF", "WOLF_KIN", "BARBARIAN", "BEAR_KIN"):
                sub_lineage = val
            elif val in ("BOY", "GIRL"):
                gender = val

        if len(args) > 2:
            g_val = args[2].upper()
            if g_val in ("BOY", "GIRL"):
                gender = g_val

        ag = self.engine.spawn_agent(
            race=race,  # type: ignore
            gender=gender,  # type: ignore
            sub_lineage=sub_lineage,  # type: ignore
            stage="ADULT",
        )
        return (
            f"Spawned {ag.race} {ag.gender} named "
            f"'{ag.display_name} {ag.dynasty_surname}' (ID: {ag.agent_id})."
        )

    def _cmd_bless(self, args: list[str]) -> str:
        """Blesses an agent: clears distress, restores vitals."""
        if not args:
            return "Usage: bless <agent_id>"
        agent_id = args[0]
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."

        ag.health = ag.max_health
        ag.hunger = 100.0
        ag.stamina = 100.0
        ag.distress = 0.0
        ag.crying = False
        ag.injured = 0.0
        ag.illness = 0.0
        return f"Blessed agent '{ag.display_name}' ({agent_id}). Vitals restored to maximum."

    def _cmd_curse(self, args: list[str]) -> str:
        """Curses an agent: inflicts distress and exhaustion."""
        if not args:
            return "Usage: curse <agent_id>"
        agent_id = args[0]
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."

        ag.distress = 0.85
        ag.hunger = 15.0
        ag.stamina = 10.0
        ag.crying = ag.stage in ("INFANT", "CHILD")
        return f"Curses struck agent '{ag.display_name}' ({agent_id}). Distress set to 0.85."

    def _cmd_smite(self, args: list[str]) -> str:
        """Kills an agent via divine smite."""
        if not args:
            return "Usage: smite <agent_id>"
        agent_id = args[0]
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."

        ag.alive = False
        self.engine.adapter.despawn_agent(agent_id, ag.slot_idx, reason="DIVINE_SMITE")
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
        return f"Smote agent '{ag.display_name}' ({agent_id}). Death recorded."

    def _cmd_war(self, args: list[str]) -> str:
        """War controls: war declare <attacker> <target> | war peace <polity_a> <polity_b>."""
        if len(args) < 3:
            return "Usage: war declare <attacker_id> <target_id> | war peace <polity_a> <polity_b>"
        action = args[0].lower()
        p1 = args[1]
        p2 = args[2]

        if action == "declare":
            self.engine.political_engine.declare_war(p1, p2)
            return f"War declared: {p1} vs {p2}."
        elif action == "peace":
            self.engine.political_engine.resolve_peace(p1, p2)
            return f"Peace signed between {p1} and {p2}."
        return "Unknown war action. Use 'declare' or 'peace'."

    def _cmd_bank_action(self, args: list[str]) -> str:
        """Bank controls: bank grant <agent_id> <amount>."""
        if len(args) < 3:
            return "Usage: bank grant <agent_id> <amount>"
        sub = args[0].lower()
        target = args[1]
        if sub == "grant":
            try:
                amt = float(args[2])
            except ValueError:
                return "Amount must be a number."
            ag = self.engine.agents.get(target)
            if not ag:
                return f"Agent '{target}' not found."
            self.engine.bank.issue_currency(ag, amt)
            return f"Granted {amt:.2f} credits to '{ag.display_name}'. Balance: {ag.credits:.2f}."
        return "Unknown bank action. Available: grant"

    def _cmd_wtc_action(self, args: list[str]) -> str:
        """WTC actions: wtc freeze | wtc tariff <polity> <rate>."""
        if not args:
            return "Usage: wtc freeze | wtc tariff <polity_id> <rate>"
        sub = args[0].lower()
        if sub == "freeze":
            return "WTC market freeze toggled."
        elif sub == "tariff" and len(args) >= 3:
            polity_id = args[1]
            try:
                rate = float(args[2])
            except ValueError:
                return "Tariff rate must be a number."
            polity = self.engine.political_engine.polities.get(polity_id)
            if polity:
                polity.tariff_rate = max(0.0, min(0.50, rate))
                return f"Tariff for {polity_id} set to {polity.tariff_rate * 100:.1f}%."
            return f"Polity '{polity_id}' not found."
        return "Usage: wtc freeze | wtc tariff <polity_id> <rate>"

    def _cmd_coronate(self, args: list[str]) -> str:
        """Coronates agent King of nation: coronate <nation_id> <agent_id>."""
        if len(args) < 2:
            return "Usage: coronate <nation_id> <agent_id>"
        nation_id, agent_id = args[0], args[1]
        polity = self.engine.political_engine.polities.get(nation_id)
        if not polity:
            return f"Nation '{nation_id}' not found."
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."
        polity.leader_id = agent_id
        polity.government_type = "KING"
        return f"Agent '{ag.display_name}' coronated King of {nation_id}."

    def _cmd_appoint_pope(self, args: list[str]) -> str:
        """Appoints Pope of religion: appoint_pope <religion_id> <agent_id>."""
        if len(args) < 2:
            return "Usage: appoint_pope <religion_id> <agent_id>"
        rel_id, agent_id = args[0], args[1]
        rel = self.engine.religion_mgr.religions.get(rel_id)
        if not rel:
            return f"Religion '{rel_id}' not found."
        ag = self.engine.agents.get(agent_id)
        if not ag:
            return f"Agent '{agent_id}' not found."
        rel.pope_id = agent_id
        return f"Agent '{ag.display_name}' appointed Pope of {rel.name}."

    def _cmd_decree(self, args: list[str]) -> str:
        """Broadcasts divine decree: decree "<msg>"."""
        if not args:
            return 'Usage: decree "<message>"'
        msg = " ".join(args)
        entry = self.engine.ledger_pipeline.record_deity_message(
            entry_id=f"decree_{uuid.uuid4().hex[:8]}",
            day=self.engine.current_day,
            tick=self.engine.current_tick,
            category="MILESTONE",
            deity_slot=None,
            speaker_name="God",
            message=msg,
        )
        return f"Divine Decree recorded: '{msg}' (Entry: {entry.entry_id})."

    def _cmd_speed(self, args: list[str]) -> str:
        """Adjusts simulation speed: speed <1x..60x>."""
        if not args:
            return f"Current simulation speed: {self.engine.speed:.1f}x"
        val_str = args[0].lower().rstrip("x")
        try:
            val = float(val_str)
        except ValueError:
            return f"Invalid speed value '{args[0]}'. Use e.g. speed 20x or speed 1.0."
        self.engine.set_speed(val)
        return f"Simulation speed set to {self.engine.speed:.1f}x."

    def _cmd_pause(self) -> str:
        """Pauses simulation."""
        self.engine.is_running = False
        return "Simulation paused."

    def _cmd_resume(self) -> str:
        """Resumes simulation."""
        self.engine.is_running = True
        return "Simulation resumed."

    def _cmd_step(self, args: list[str]) -> str:
        """Steps simulation N ticks."""
        n = int(args[0]) if args else 1
        for _ in range(n):
            self.engine.step_tick()
        msg = f"Stepped {n} ticks. Current tick: {self.engine.current_tick}"
        return f"{msg} (Day {self.engine.current_day})."

    def _cmd_save(self) -> str:
        """Triggers atomic World Goddess end-of-day 2PC save."""
        manifest = self.engine.commit_end_of_day()
        return (
            f"Atomic save committed successfully.\n"
            f"Day: {manifest.day} | Checkpoint: {manifest.db_sha256[:12]}... "
            f"| Status: {manifest.status}"
        )

    def _cmd_rewind(self, args: list[str]) -> str:
        """Rewinds to a previous verified snapshot: rewind <day>."""
        if not args:
            return "Usage: rewind <day>"
        try:
            target_day = int(args[0])
        except ValueError:
            return "Day must be an integer: rewind <day>"
        try:
            res = self.engine.checkpoint_mgr.rewind_to_day(target_day)
            return (
                f"Rewound to Day {target_day}.\n"
                f"DB: {res['db_path']} | PT: {res['pt_path']} (SHA: {res['db_sha256'][:12]}...)"
            )
        except Exception as exc:
            return f"Failed to rewind to Day {target_day}: {exc}"

    def _cmd_shutdown(self) -> str:
        """Safely saves and stops engine."""
        self.engine.is_running = False
        manifest = self.engine.commit_end_of_day()
        return f"Simulation stopped cleanly. Final save: Day {manifest.day}."

    def _cmd_help(self) -> str:
        """Displays available commands."""
        return (
            "[bold gold3]Available God Console Commands:[/bold gold3]\n"
            "[bold cyan]Inspect:[/bold cyan]\n"
            "  status                        - Overview of clock, population, economy, and RAM\n"
            "  pop [race]                    - Population breakdown by race and life stage\n"
            "  fatalities                    - Recent fatalities, causes, and seasons\n"
            "  crimes [agent]                - Active and adjudicated court cases\n"
            "  nations                       - Polities, tiers, governments, borders, and wars\n"
            "  borders                       - Territory parcel counts per polity\n"
            "  elections                     - Governance systems, rulers, and election dates\n"
            "  religions                     - Faiths, popes, tithe rates, and altar counts\n"
            "  deities                       - Divine Family hierarchy, names, and energy\n"
            "  council                       - Recent Sister Council debates and truces\n"
            "  elders                        - Appointed Library Elders per nation\n"
            "  wtc                           - Commodity market prices, volume, and CPI\n"
            "  bank                          - Money supply M, reserves, and loan defaults\n"
            "  parcel <cx> <cz>              - Chunk parcel ownership and assessed value\n"
            "  traditions                    - Emergent cultural traditions per settlement\n"
            "  library [topic]               - Canonical books in the World Library\n"
            "  codex [proposals]             - Divine Rules / decrees and pending proposals\n"
            "  ledger [day]                  - Read daily God Ledger markdown\n"
            "  analytics <view>              - DuckDB analytics (demographics, mortality)\n"
            "  inspect <agent_id>            - Complete agent card (vitals, traits, coords)\n\n"
            "[bold cyan]Intervene:[/bold cyan]\n"
            '  name_deity <slot> "<name>"    - Bestow custom name onto Goddess or God-Mother\n'
            "  spawn <race> [lineage] [sex]  - Spawn an adult mortal into the world\n"
            "  bless <agent_id>              - Restore vitals to max and clear distress\n"
            "  curse <agent_id>              - Inflict severe distress and fatigue\n"
            "  smite <agent_id>              - Strike mortal dead via divine decree\n"
            "  war declare/peace <p1> <p2>   - Declare war or force peace treaty\n"
            "  bank grant <agent_id> <amt>   - Issue divine credits from Bank reserves\n"
            "  wtc tariff <polity> <rate>    - Set trade tariff rate\n"
            "  coronate <nation> <agent_id>  - Crown King of nation\n"
            "  appoint_pope <rel> <agent_id> - Appoint Pope of religion\n"
            '  decree "<message>"            - Broadcast divine decree to God Ledger\n'
            "  speed <1x..60x>               - Adjust simulation speed multiplier\n"
            "  pause / resume                - Pause or unpause tick loop\n"
            "  step [N]                      - Advance N simulation ticks\n"
            "  save                          - Commit atomic end-of-day 2PC save\n"
            "  rewind <day>                  - Rewind world to verified daily snapshot\n"
            "  shutdown                      - Safely commit and terminate simulation"
        )
