"""
sim_core/divine/llm_brain.py
Async Local-LLM Divine Brain & Grounded Deterministic Fallback.
Follows Gaia v4.0 Sprint 5 specifications:
- Non-blocking async client targeting local OpenAI-compatible llama.cpp / Ollama server.
- Grounded RAG prompt pulling PersonalityVector, MoodState, MemoryRAGIndex memories,
  live world telemetry (5-race populations, WTC CPI, pending proposals, active wars/crimes).
- Parses structured JSON responses (spoken_reply, mood_delta, proposed_action) gated
  strictly through WorldGoddessCritic (fail-closed on unauthorized actions).
- Mandatory Offline Fallback: rich, state-grounded deterministic response generator
  referencing exact same live RAG memories, CPI, proposals, and personality traits.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import TYPE_CHECKING, Any

from sim_core.schemas import CommitProposal, DialogueRequest, DialogueResponse

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine

logger = logging.getLogger(__name__)

DEFAULT_LLM_URL = os.environ.get("GAIA_LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
DEFAULT_LLM_MODEL = os.environ.get(
    "GAIA_LLM_MODEL", "models/Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf"
)
DEFAULT_MODEL_DISPLAY = "Huihui-Qwen3.5-4B"
LLM_TIMEOUT_SECONDS = 14.0
LLM_HEALTH_REPROBE_INTERVAL_SECONDS = 20.0


SAFE_DIVINE_ACTIONS: frozenset[str] = frozenset(
    {
        "CONVENE_COUNCIL",
        "PATROL_PLAZA",
        "RETURN_PALACE",
        "INSPECT_LIBRARY",
        "INSPECT_WTC",
        "RECORD_LEDGER_NOTE",
        "PROPOSE_TRUCE",
        "BLESS_HARVEST",
    }
)


def extract_json_from_llm_text(text: str) -> dict[str, Any] | None:
    """
    Strips Qwen3.5 <think>...</think> blocks, markdown code fences,
    and extracts the structured JSON object.
    """
    if not text or not isinstance(text, str):
        return None

    # 1. Strip complete <think>...</think> blocks
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    # Also strip unclosed <think> if response got cut off
    if "<think>" in cleaned:
        cleaned = re.sub(r"<think>[\s\S]*", "", cleaned).strip()

    # 2. Strip markdown code fences (```json ... ``` or ``` ... ```)
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    # 3. Direct JSON parse
    try:
        res = json.loads(cleaned)
        if isinstance(res, dict):
            return res
    except json.JSONDecodeError:
        pass

    # 4. Fallback: find outermost { ... }
    brace_match = re.search(r"(\{[\s\S]*\})", cleaned)
    if brace_match:
        try:
            res = json.loads(brace_match.group(1))
            if isinstance(res, dict):
                return res
        except json.JSONDecodeError:
            pass

    # 5. Resilient fallback: regex search for spoken_reply if JSON was cut off mid-stream
    reply_match = re.search(r'"spoken_reply"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', cleaned)
    if reply_match:
        try:
            unescaped = json.loads(f'"{reply_match.group(1)}"')
        except (json.JSONDecodeError, ValueError):
            unescaped = reply_match.group(1)
        return {"spoken_reply": unescaped}

    return None


class DivineLLMBrain:
    """
    Manages interactive dialogue generation for Deities and Mortals,
    providing both an async local LLM connection and an offline deterministic fallback.
    """

    def __init__(
        self,
        engine: SimulationEngine | None = None,
        llm_url: str = DEFAULT_LLM_URL,
        model_name: str = DEFAULT_LLM_MODEL,
        active_model_name: str = DEFAULT_MODEL_DISPLAY,
    ) -> None:
        self.engine = engine
        self.llm_url = llm_url
        self.model_name = model_name
        self.active_model_name = active_model_name
        self.llm_online: bool = False
        # Monotonic timestamp of the last health probe / failed request (0.0 = never probed).
        self._last_health_check_time: float = 0.0
        self._lock = threading.Lock()

    def build_rag_context(self, target_slot: str) -> dict[str, Any]:
        """Collects live grounded telemetry and deity personality/memory state."""
        ctx: dict[str, Any] = {
            "target_id": target_slot,
            "populations": {},
            "cpi": 1.0,
            "money_supply": 1000000.0,
            "pending_proposals": 0,
            "active_crimes": 0,
            "top_memories": [],
            "personality": {},
            "mood": "calm",
        }

        if not self.engine:
            return ctx

        # 1. 5-Race Populations
        pop_counts: dict[str, int] = {
            "HUMAN": 0,
            "ELF": 0,
            "DRAGON": 0,
            "BEASTHUMAN": 0,
            "DEMON": 0,
        }
        for a in self.engine.agents.values():
            if a.race in pop_counts:
                pop_counts[a.race] += 1
        ctx["populations"] = pop_counts

        # 2. Economy
        if hasattr(self.engine, "wtc"):
            ctx["cpi"] = round(getattr(self.engine.wtc, "cpi", 1.0), 3)
        if hasattr(self.engine, "bank"):
            ctx["money_supply"] = round(
                self.engine.bank.calculate_total_circulation(list(self.engine.agents.values())),
                2,
            )

        # 3. Governance
        if hasattr(self.engine, "governance_engine"):
            ctx["pending_proposals"] = len(self.engine.governance_engine.library_proposals)

        # 4. Judiciary active cases
        if hasattr(self.engine, "judiciary"):
            ctx["active_crimes"] = len(self.engine.judiciary.cases)

        # 5. Memories & Personality
        deity_record = self.engine.divine_hierarchy.entities.get(target_slot)  # type: ignore
        if deity_record:
            if deity_record.personality_vector:
                ctx["personality"] = {
                    "courage": deity_record.personality_vector.courage,
                    "empathy": deity_record.personality_vector.empathy,
                    "ambition": deity_record.personality_vector.ambition,
                    "discipline": deity_record.personality_vector.discipline,
                    "devotion": deity_record.personality_vector.devotion,
                    "out_group_trust": deity_record.personality_vector.out_group_trust,
                    "caution": deity_record.personality_vector.caution,
                    "pride": deity_record.personality_vector.pride,
                }
            if deity_record.mood:
                ctx["mood"] = deity_record.mood.dominant_mood()

        if hasattr(self.engine, "memory_rag"):
            mems = self.engine.memory_rag.get_recent_memories(target_slot, limit=3)
            ctx["top_memories"] = [m.summary for m in mems]

        return ctx

    def check_health(self) -> bool:
        """Checks if llama-server is healthy at /health endpoint."""
        self._last_health_check_time = time.monotonic()
        try:
            base_url = self.llm_url.split("/v1/")[0]
            health_url = f"{base_url}/health"
            req = urllib.request.Request(health_url, headers={"User-Agent": "GaiaEngine"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                self.llm_online = resp.status == 200
                return self.llm_online
        except (urllib.error.URLError, TimeoutError, OSError):
            self.llm_online = False
            return False

    def _send_http_request(
        self, payload: dict[str, Any], timeout: float = LLM_TIMEOUT_SECONDS
    ) -> dict[str, Any] | None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.llm_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if "chat_template_kwargs" in payload:
                logger.info(
                    "Local server rejected chat_template_kwargs (%s); retrying without it...", e
                )
                retry_payload = dict(payload)
                retry_payload.pop("chat_template_kwargs", None)
                return self._send_http_request(retry_payload, timeout=timeout)
            logger.warning("Local LLM HTTP error: %s", e)
            return None
        except Exception as e:
            logger.debug("Local LLM request failed: %s", e)
            return None

    def _query_local_llm(self, prompt: str, system_prompt: str) -> dict[str, Any] | None:
        """
        Attempts HTTP POST to local llama.cpp server with chat_template_kwargs,
        serialized via thread lock for single-slot (-np 1) safety.
        Strips thinking blocks and code fences, returning parsed JSON dict.
        """
        with self._lock:
            # Fast failover: while offline, re-probe /health at most once per interval so
            # dialogue replies return instantly via OFFLINE_FALLBACK instead of burning timeouts.
            if not self.llm_online and self._last_health_check_time > 0.0:
                since = time.monotonic() - self._last_health_check_time
                if since < LLM_HEALTH_REPROBE_INTERVAL_SECONDS:
                    return None
                if not self.check_health():
                    return None
            payload: dict[str, Any] = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 160,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            resp_data = self._send_http_request(payload, timeout=LLM_TIMEOUT_SECONDS)
            if not resp_data or not isinstance(resp_data, dict):
                self.llm_online = False
                self._last_health_check_time = time.monotonic()
                return None

            choices = resp_data.get("choices", [])
            if not choices or not isinstance(choices, list):
                self.llm_online = False
                self._last_health_check_time = time.monotonic()
                return None

            content = choices[0].get("message", {}).get("content", "")
            parsed = extract_json_from_llm_text(content)
            if parsed is not None:
                self.llm_online = True
                return parsed
            else:
                logger.warning("Failed to extract valid JSON from LLM response: %s", content[:120])
                return None

    def generate_dialogue(self, request: DialogueRequest) -> DialogueResponse:
        """
        Generates grounded dialogue response for Deity or Mortal.
        Uses local LLM if online, otherwise deterministic grounded fallback.
        """
        target_type = request.target_type
        target_id = request.target_id
        msg = request.message
        order = request.order

        if target_type == "DEITY":
            return self._generate_deity_dialogue(target_id, msg, order)
        else:
            return self._generate_mortal_dialogue(target_id, msg)

    def _generate_deity_dialogue(
        self, deity_slot: str, message: str, order: str
    ) -> DialogueResponse:
        """Processes interaction with one of the 6 Deities."""
        ctx = self.build_rag_context(deity_slot)
        deity_obj = (
            self.engine.divine_autonomy.deities.get(deity_slot)  # type: ignore
            if (self.engine and hasattr(self.engine, "divine_autonomy"))
            else None
        )
        name = deity_obj.name if deity_obj else deity_slot.replace("_", " ").title()
        title = deity_obj.title if deity_obj else "Patron Deity"
        race = deity_obj.race if deity_obj else "DIVINE"

        action_taken = ""
        # Handle God direct orders first
        if order and self.engine and hasattr(self.engine, "divine_autonomy"):
            action_taken = self.engine.divine_autonomy.issue_god_order(
                order,
                target_deity_slot=deity_slot,  # type: ignore
            )

        # Attempt local LLM
        memories_str = ""
        if ctx.get("top_memories"):
            memories_str = f" Recent memories: {'; '.join(ctx['top_memories'])}."

        system_prompt = (
            f"You are {name}, {title} of the Gaia civilization. "
            f"Your race affinity is {race}. Your personality traits: {ctx['personality']}. "
            f"Current mood: {ctx['mood']}. World telemetry: CPI={ctx['cpi']}, "
            f"Populations={ctx['populations']}, "
            f"Active proposals={ctx['pending_proposals']}.{memories_str} "
            "Output strictly valid JSON with keys: "
            "spoken_reply (string, 1-2 concise regal sentences), "
            "mood_delta (dict), proposed_action (optional dict)."
        )
        user_prompt = f"God says: '{message}'. Order: '{order}'. Formulate your reply."
        llm_result = self._query_local_llm(user_prompt, system_prompt)

        if (
            llm_result
            and isinstance(llm_result, dict)
            and str(llm_result.get("spoken_reply") or "").strip()
        ):
            spoken_reply = str(llm_result["spoken_reply"]).strip()
            # Validate proposed action through critic if present
            prop_action = llm_result.get("proposed_action")
            if prop_action and self.engine and hasattr(self.engine, "world_goddess"):
                is_valid = self._validate_proposed_action(deity_slot, prop_action)
                if not is_valid:
                    action_taken += " [Action rejected by WorldGoddessCritic]"
            backend_tag = f"LIVE ({self.active_model_name})"
            return DialogueResponse(
                target_id=deity_slot,
                target_name=name,
                title=title,
                race=race,
                mood=ctx["mood"],
                spoken_reply=spoken_reply,
                action_taken=action_taken,
                llm_backend=backend_tag,
            )

        # Deterministic Grounded Offline Fallback
        spoken_reply = self._generate_offline_deity_reply(deity_slot, name, message, order, ctx)
        if deity_obj:
            deity_obj.set_speech(spoken_reply[:60] + "...")

        return DialogueResponse(
            target_id=deity_slot,
            target_name=name,
            title=title,
            race=race,
            mood=ctx["mood"],
            spoken_reply=spoken_reply,
            action_taken=action_taken,
            llm_backend="OFFLINE_FALLBACK",
        )

    def _generate_offline_deity_reply(
        self,
        slot: str,
        name: str,
        msg: str,
        order: str,
        ctx: dict[str, Any],
    ) -> str:
        """Rich grounded deterministic fallback for Deities."""
        msg_lower = msg.lower()

        # Order response
        if order.upper() == "CONVENE_COUNCIL":
            return (
                "The Great Bell tolls across the Acropolis. I have summoned my four sisters "
                "to the Grand Palace Courtyard. We shall assemble before Your gaze."
            )
        elif order.upper() == "FOLLOW_GOD":
            return "At once, My Lord. I shall walk in Your shadow and guard Your divine presence."
        elif order.upper() == "RETURN_PALACE":
            return "By Your will, Lord. I return to my sacred throne to guide my children."
        elif order.upper() == "PATROL_PLAZA":
            return (
                "I descend to the Central Basin plaza to watch over the mortals and ensure peace."
            )

        # Topical queries
        if "report" in msg_lower or "state" in msg_lower or "world" in msg_lower:
            pops = ctx.get("populations", {})
            cpi = ctx.get("cpi", 1.0)
            pending = ctx.get("pending_proposals", 0)
            return (
                f"The realm numbers {sum(pops.values())} living souls across the five rings "
                f"(Humans: {pops.get('HUMAN', 0)}, Elves: {pops.get('ELF', 0)}, "
                f"Dragons: {pops.get('DRAGON', 0)}, Beasthumans: {pops.get('BEASTHUMAN', 0)}, "
                f"Demons: {pops.get('DEMON', 0)}). Market inflation rests at CPI {cpi:.2f}, "
                f"with {pending} mortal petitions currently awaiting our divine consensus."
            )

        if "book" in msg_lower or "library" in msg_lower or "council" in msg_lower:
            pending = ctx.get("pending_proposals", 0)
            if pending > 0:
                return (
                    f"There are {pending} scrolls and treaties currently under review "
                    "in the World Library. The mortals seek wisdom in warfare, agriculture, "
                    "and metallurgy. We shall weigh their merits."
                )
            return (
                "The World Library shelves remain tranquil. The elders debate philosophy "
                "in the hall, and no contested treatises demand our immediate intervention."
            )

        return self._flavor_reply(slot) + self._grounded_suffix(ctx)

    @staticmethod
    def _grounded_suffix(ctx: dict[str, Any]) -> str:
        """Appends real populations, CPI, proposals, and memories so replies never feel canned."""
        pops = ctx.get("populations", {}) or {}
        parts = [
            f"The realm counts {sum(pops.values())} souls",
            f"CPI rests at {float(ctx.get('cpi', 1.0)):.2f}",
            f"{int(ctx.get('pending_proposals', 0))} petitions await judgment",
        ]
        suffix = " (" + "; ".join(parts) + ".)"
        mems = ctx.get("top_memories") or []
        if mems:
            suffix += f" I recall: {mems[0]}."
        return suffix

    @staticmethod
    def _flavor_reply(slot: str) -> str:
        """Deity-specific flavor text (never empty)."""
        if slot == "world_goddess":
            return (
                "Peace be with You, My Lord. I watch over our daughters and balance the "
                "scales of justice. The five nations prosper under Your heavens, "
                "and all ledger accounts remain intact."
            )
        elif slot == "gm_human":
            return (
                "My people in Aurelia cultivate the sunlit plains and expand their workshops. "
                "Their ambition burns bright, yet they honor the covenant and trade with integrity."
            )
        elif slot == "gm_elf":
            return (
                "Sylvanor's ancient emerald canopy breathes in harmony. "
                "My children study the living botany of the world and pray for enduring quietude."
            )
        elif slot == "gm_dragon":
            return (
                "Drakonis Spire stands unbroken above the clouds. "
                "My kindred soar in humanoid grace, keeping their primordial flames reserved "
                "for true peril."
            )
        elif slot == "gm_beasthuman":
            return (
                "The timber steppes of Fenris Hold echo with the laughter of cubs and "
                "the craft of timber. The pack stands loyal and vigilant on the southern road."
            )
        elif slot == "gm_demon":
            return (
                "Malakor’s basalt towers glow with abyssal forgecraft. "
                "My folk remain fiercely proud, yet we keep strict distance from the dragons' "
                "aerie as agreed."
            )

        return "I hear Your words, Lord. May Your divine will be made manifest upon Gaia."

    def _generate_mortal_dialogue(self, agent_id: str, message: str) -> DialogueResponse:
        """Generates grounded responses for Mortal NPCs."""
        agent = self.engine.agents.get(agent_id) if self.engine else None
        name = agent.display_name if agent else "Mortal Citizen"
        title = f"{agent.race} {agent.profession.title()}" if agent else "Citizen"
        race = agent.race if agent else "HUMAN"
        mood = agent.mood.dominant_mood() if (agent and agent.mood) else "calm"

        msg_lower = message.lower()
        if "name" in msg_lower or "who" in msg_lower:
            spoken_reply = (
                f"I am {name} of Clan {agent.dynasty_surname if agent else 'Gaia'}, "
                f"a humble {agent.profession.lower() if agent else 'citizen'} of this land."
            )
        elif "trade" in msg_lower or "buy" in msg_lower or "price" in msg_lower:
            spoken_reply = (
                "If you seek goods, the stalls around the central plaza have honest wares, "
                "though grain prices have been shifting at the World Trade Centre."
            )
        elif "god" in msg_lower or "deity" in msg_lower or "pray" in msg_lower:
            spoken_reply = (
                "We offer our daily devotion at the cathedral pillars. "
                "The World Goddess watches over all souls who keep the peace."
            )
        else:
            spoken_reply = (
                "Blessings upon you, traveler. May your journey through our city be prosperous."
            )

        return DialogueResponse(
            target_id=agent_id,
            target_name=name,
            title=title,
            race=race,
            mood=mood,
            spoken_reply=spoken_reply,
            action_taken="",
        )

    def _validate_proposed_action(self, deity_slot: str, action: dict[str, Any]) -> bool:
        """Validates actions strictly fail-closed through allowlist and WorldGoddessCritic."""
        action_type = action.get("action_type")
        if not action_type or not isinstance(action_type, str):
            return False

        if action_type not in SAFE_DIVINE_ACTIONS:
            return False

        if (
            self.engine
            and hasattr(self.engine, "world_goddess")
            and self.engine.world_goddess is not None
        ):
            kind_map = {
                "CONVENE_COUNCIL": "SISTER_COUNCIL_RESOLUTION",
                "PROPOSE_TRUCE": "SISTER_COUNCIL_RESOLUTION",
                "RECORD_LEDGER_NOTE": "DIVINE_DECREE",
                "INSPECT_LIBRARY": "LIBRARY_ENTRY",
                "INSPECT_WTC": "WTC_INTERVENTION",
                "PATROL_PLAZA": "GOD_MOTHER_INTERVENTION",
                "RETURN_PALACE": "GOD_MOTHER_INTERVENTION",
            }
            commit_kind = kind_map.get(action_type, "GOD_MOTHER_INTERVENTION")
            proposal = CommitProposal(
                proposal_id=f"divine_act_{uuid.uuid4().hex[:8]}",
                tick=getattr(self.engine, "current_tick", 0),
                kind=commit_kind,  # type: ignore
                actor_id=deity_slot,
                payload=action,
            )
            verdict = self.engine.world_goddess.evaluate(proposal)
            return verdict.status == "SUCCESS"

        return True
