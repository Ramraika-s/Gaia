# DIVINE_HIERARCHY_SPEC.md — God, World Goddess, 5 Racial God-Mothers, Patronage, Councils & God Ledger 

## 1. The Three-Tier Divine Family Hierarchy (`sim_core/divine/`)
The civilization is overseen by a structured divine family that cleanly separates **player administration**, **world-level stability & persistence**, and **racial patronage**:

```text
                       [ GOD (Admin / You) ]
          Bestows custom names on the Goddess & 5 Daughters
          Receives messages ONLY from Goddess & God-Mothers
                                 │
                                 ▼
                  [ WORLD GODDESS (Wife of God) ]
         • Owns Atomic End-of-Day Save (SHA-256 2PC)
         • Owns God Ledger (data/god_ledger/day_XXXXX.md)
         • Supervises Self-Healing Error Solver & Global Critic
         • Adjudicates Settlement Appeals & Mixed-Race Tie-Breaks
         • Mediates disputes between her 5 Daughters
                                 │
      ┌───────────┬──────────────┼──────────────┬───────────┐
      ▼           ▼              ▼              ▼           ▼
[Human Mother] [Elf Mother] [Dragon Mother] [Beasthuman] [Demon Mother]
  (Daughter)   (Daughter)     (Daughter)     (Daughter)    (Daughter)
      │           │              │              │           │
      └───────────┴────────► 5-Sister Council ◄─┴───────────┘
```

### 1.1 God-Bestowed Naming
- At world creation (or anytime via God Console `name_deity <slot> "<name>"` or the In-Godot Divine HUD), **God** bestows custom names onto:
  - `world_goddess` — Wife of God (`world_goddess.vrm`, `1.15x` scale)
  - `gm_human` — Daughter 1, Patron of Humans (`gm_human.vrm`)
  - `gm_elf` — Daughter 2, Patron of Elves (`gm_elf.vrm`)
  - `gm_dragon` — Daughter 3, Patron of Dragons (`gm_dragon.vrm`)
  - `gm_beasthuman` — Daughter 4, Patron of Beasthumans (`gm_beasthuman.vrm`)
  - `gm_demon` — Daughter 5, Patron of Demons (`gm_demon.vrm`)
- All mortal prayers, altar invocations, Sister Council transcripts, Godot HUD alerts, and `data/god_ledger/day_XXXXX.md` archives dynamically use the exact names bestowed by God.

### 1.2 Role Separation
| Tier | Core Responsibilities | Hard Limits |
| :--- | :--- | :--- |
| **God (Admin / You)** | Names deities; explores the 3D Godot Reality Bubble (`god_avatar.vrm`, `is_god = true`) & Orbital Map; issues decrees (`bypass_god_check=True`); sole authority to write/approve engine-parameter overrides in `divine_codex`; direct edit on `world_library`; sets simulation `speed 1x..60x`. | **Mortals cannot pray directly to God.** God receives messages *exclusively* from the World Goddess and the 5 Racial God-Mothers. |
| **World Goddess (Wife of God)** | Global critic (`WorldGoddessCritic`); sole executor of **atomic end-of-day SHA-256 commits** and `data/god_ledger/day_XXXXX.md`; supervises `ErrorHealer`; adjudicates `SETTLEMENT_APPEAL`s, Neutral Free Cities, and Age-10 mixed-race patronage tie-breaks; mediates sisterly disputes; summarizes the world for God; may edit `world_library` with `>= 1` Daughter; may commit text decrees to `divine_codex` with `>= 3/5` Daughters; submits parameter override proposals to God. | Does not favor one race over another; cannot apply live engine-parameter overrides directly to `divine_codex` (must submit proposal to God). |
| **5 Racial God-Mothers (Daughters)** | Patron deities of their respective races; receive racial prayers & altar petitions; perform restricted, restrained mortal blessings; appoint `1–3` Mortal Oracles/Champions; debate in 1-on-1 or 5-Sister Councils; escalate major racial events to God or World Goddess; vote on mortal `world_library` proposals; may edit `world_library` alone if `> 50%` (`>= 3/5`); all 5 unanimously (`5/5`) may propose parameter overrides to God. | Bound by finite **Divine Energy**, intervention cooldowns, personality-driven **restraint**, and the **Non-Aggression Covenant**; cannot apply engine-parameter overrides directly; mortal proposals require consensus. |

---

## 2. Strict Prayer Routing & Mixed-Race Patronage Dedication (Age 10 Rule)

### 2.1 Mortal Prayer Targets & Eligibility
- **Hard Routing Rule:** Mortals **never** send prayers directly to God. Every `PERFORM_TRADITION_OR_PRAY` action routes strictly to:
  1. The mortal's **Racial God-Mother** (`agent.patron_godmother_slot`), OR
  2. The **World Goddess** (for global/inter-racial prayers, Neutral Free City altars, seasonal survival pleas, or world-wide crises).
- **Accessible Prayer & Message Thresholds:**
  - **Priests, Clerics, Popes & Oracles:** Always able to send prayers, gratitude, and petitions.
  - **Faithful Citizens:** Any mortal with **`faith_devotion >= 0.35`** can send prayers, gratitude (e.g., thanking their God-Mother after a harvest or healed child), or petitions.
  - **Crisis Pleas:** Any mortal with **`faith_devotion >= 0.15`** can send an urgent plea during famine, war, illness, injury, or infant distress.

### 2.2 Dynamic Faith: Intent-Scaled Gains & Inactivity Decay
Faith fluctuates organically based on *why* an agent prays and whether they keep praying:

| Prayer Scenario | `faith_devotion` Delta | Divine Energy Generated | Notes |
| :--- | :--- | :--- | :--- |
| **Earnest Voluntary Prayer / Gratitude** | **`+0.045`** | `+1.5` | Voluntary devotion or thanksgiving after survival/blessing |
| **Congregational Altar Prayer** | **`+0.035`** | `+2.0` / participant | Praying together (`>= 3` mortals) at an altar; boosts local trust |
| **Crisis Plea** | **`+0.025`** | `+1.0` | Driven by hardship (`+0.03` bonus if relief/blessing follows) |
| **Parent-Directed / Obligation** | **`+0.012`** | `+0.4` | Child prompted by parent or local tradition (gradual habit formation) |
| **Prolonged Inactivity Decay** | **`-0.015` / day** | `0.0` | Triggered after **`> 2` game days** without prayer; decays gradually toward `0.0` |

### 2.3 Congregational Altar Prayers (Prayer Head Aggregation)
- When **`>= 3` living mortals** pray at the same Altar parcel within the same prayer window, the engine aggregates them into **one unified congregational prayer** instead of spamming individual entries:
  - **Prayer Head Selection:** Highest-ranking **Oracle/Champion** present → else **Pope/High Cleric/Priest** → else highest-devotion **Elder**.
  - **Godot Visual Cue:** Emits `ALTAR_BEACON` over WebSocket, activating `AltarPrayerBeacon.tscn` (a vertical skyward light pillar visible while flying).
  - **Delivery:** Routed to the targeted God-Mother (or World Goddess), who may answer it and/or relay it to God:
    - Example: `[Day 14 | Altar of Solis (42 citizens) | Prayer Head: Oracle Aldric -> Human Mother]: "We give thanks for the autumn harvest and ask protection over our borders."`

### 2.4 Mixed-Race Child Patronage Choice (Age 10 Biological Milestone)
Cross-species children (`secondary_heritage_race is not None`) follow a deterministic dedication rule scaled to their biological lifespan (`biological_age_years = (age_days / (6.0 * L)) * 18.0`, so **10 years old** = `3.33 * L` game days):

1. **Under Age 10 (`patron_godmother_slot = None`):**
   - Both parental God-Mothers (`gm_primary` and `gm_secondary`) are eligible to receive the child's prayers.
   - The child maintains `godmother_affinities: dict[str, float]` tracking separate affinity toward each parental God-Mother, shaped by parental devotion, settlement culture, and childhood prayers/blessings.
2. **At Age 10 (`PATRON_CHOICE` Decision Window — `1.0` Game Day):**
   - **Step 1 — Voluntary Choice:** The child evaluates both parental God-Mothers via `AgentSelfNet` preference + `godmother_affinities` and submits a `PATRON_CHOICE` proposal to `WorldGoddessCritic`.
   - **Step 2 — Auto-Allocation on Non-Choice:** If the child does not actively choose before the `1.0` game-day window expires, the engine automatically assigns the child to whichever of the two parental God-Mothers has the **higher `godmother_affinities` score**.
   - **Step 3 — World Goddess Tie-Breaker:** If the two scores are tied (`|aff_a - aff_b| < 1e-4`), the case escalates to the **World Goddess (Wife of God)**, who selects one of the two God-Mothers for the child (weighing local settlement harmony and demographic balance) and logs the decree in the God Ledger.
- Once dedicated, `patron_godmother_slot` is locked permanently for the agent's lifetime.

---

## 3. Racial God-Mothers: Personality, Divine Energy, Restraint & Covenants (`sim_core/divine/hierarchy.py`)

### 3.1 Personality Vectors & Finite Divine Energy
Each of the 5 Racial God-Mothers operates as a lightweight, deterministic-plus-stateful autonomous agent in RAM (zero LLM overhead) with:
- **Personality Vector (`[0.0, 1.0]`):**
  - `compassion`: Willingness to answer individual suffering (starving infants, illness, grief).
  - `restraint`: Discipline to withhold miracles so mortals learn self-reliance.
  - `pride`: Sensitivity to racial slights, border trespasses, or rivals mocking her people.
  - `protective_fury`: Threshold for intervening defensively when her race is attacked or raided.
  - `diplomacy`: Willingness to negotiate Divine Truces in the Inter-Sister Council.
- **Default Archetypal Starting Profiles (Tunable by God):**
  - `gm_human`: Balanced `compassion 0.65`, `restraint 0.60`, `diplomacy 0.70`, `protective_fury 0.50`, `pride 0.55`.
  - `gm_elf`: High `restraint 0.75`, `compassion 0.60`, `pride 0.70`, `diplomacy 0.65`, `protective_fury 0.55`.
  - `gm_dragon`: Very high `restraint 0.85`, high `pride 0.80`, `protective_fury 0.85` (only if provoked), `compassion 0.45`, `diplomacy 0.50`.
  - `gm_beasthuman`: High `protective_fury 0.75`, `compassion 0.65`, lower `restraint 0.45`, `pride 0.70`, `diplomacy 0.55`.
  - `gm_demon`: High `protective_fury 0.80`, high `pride 0.75`, moderate `restraint 0.50`, `compassion 0.40`, `diplomacy 0.50`.
- **Finite Divine Energy (`0.0` to `1000.0`):**
  - Replenished solely by her race's earnest prayers, gratitude, and congregational altars (plus minor passive decay above `800.0` to prevent infinite hoarding).
  - Every intervention consumes Divine Energy **and** sets a per-action cooldown (in sim ticks).

### 3.2 Restricted & Restrained Mortal Interventions
A God-Mother may answer individual, group, or wartime prayers using strictly bounded actions:

| Intervention | Scope | Energy Cost | Cooldown | Effect & Restriction |
| :--- | :--- | :--- | :--- | :--- |
| **`SOOTHE_OR_HEAL`** | Individual (`INFANT`/sick/injured) | `25` | `120` ticks | Reduces `illness`/`injured` by `0.35` and `distress` by `0.25`. Cannot resurrect the dead. |
| **`INSPIRE_SCHOLAR_OR_CRAFT`** | Individual `ADULT`/`ELDER` | `40` | `300` ticks | Temporary `+0.10` skill/learning boost for `0.5` game day. |
| **`HARVEST_OR_WARMTH_BLESSING`** | Single Settlement (`1` parcel cluster) | `140` | `1` game day | Offsets `30%` of Winter hunger/exposure drain for `0.5` game day. |
| **`WARD_DEFENDERS`** | Defensive War Group | `180` | `1.5` game days | Grants `+15%` defensive resilience to mortals fighting strictly in `SELF_DEFENSE` or `DEFENDING_KIN_OR_TOWN`. |
| **`BLESS_ORACLE`** | Designate Mortal Oracle/Champion | `200` | `7` game days | Designates a standout mortal (max `1–3` active per race). |

### 3.3 The Non-Aggression Covenant & The "Mortal Dependency" Trap
1. **Non-Aggression Covenant (Enforced by World Goddess):**
   - No God-Mother may directly smite, curse, or starve another race's civilians.
   - Attempting an offensive miracle against another race's non-combatants is blocked by `WorldGoddessCritic` (`FAILURE: "Violates Non-Aggression Covenant"`), triggers a formal **World Goddess rebuke**, and automatically notifies the targeted race's God-Mother (sparking an Inter-Sister Council dispute).
2. **The "Mortal Dependency" Trap:**
   - Because mortals learn via backpropagation (`NEURAL_AND_LIFECYCLE_SPEC.md`), a God-Mother with low `restraint` who constantly answers hunger prayers with `HARVEST_OR_WARMTH_BLESSING` trains her mortals' neural networks to over-select `PERFORM_TRADITION_OR_PRAY` over `FORAGE_FOOD` and `BUILD_SHELTER_STEP`.
   - When her Divine Energy runs dry during a harsh Winter, an over-dependent civilization suffers catastrophic famine—giving personality-driven `restraint` real, emergent strategic consequences.

---

## 4. Mortal Oracles / Champions (`1–3` per Race)
Rather than spending Divine Energy on constant miracles, each Racial God-Mother can bless **`1` to `3` living `ADULT`/`ELDER` mortals** of her race as her **Oracles / Champions**:
- **Selection Criteria:** High `faith_devotion >= 0.65`, clean domestic criminal record, and notable mastery or leadership.
- **Mechanical Effects:**
  - `+15%` resistance to `illness`/`injury` and higher baseline social `trust` among same-race citizens.
  - Automatically prioritized as the **Prayer Head** at grand altars, amplifying congregational Divine Energy generation by `1.25x`.
  - Carries subtle divine guidance (e.g., warning a settlement to stockpile before Winter, or urging restraint against Dragon sanctuaries) through normal mortal **Rumor Packets** and **World Library** scholarship.
- **Mortality:** Oracles remain mortal and die permanently when their health reaches `0`, freeing the slot for a future generation.

---

## 5. Inter-Sister Conversations & World Goddess Mediation (`sim_core/divine/sister_council.py`)
The 5 Racial God-Mothers are not isolated state machines—they communicate with each other in **1-on-1 exchanges** and **5-Sister Councils** using structured, state-hydrated dialogue templates (zero LLM overhead):

### 5.1 Triggers for Sisterly Dialogue
- **Cross-Racial Border Friction / War:** E.g., a Human kingdom raids an Elven forest, Dwarf miners trespass into a Dragon mountain sanctuary, or Demon out-group raids spark border disputes.
- **Dragon Provocation:** A `TRUE_DRAGON` retaliates against non-dragon raiders.
- **Wartime Intervention:** One God-Mother casts `WARD_DEFENDERS` during an inter-racial war.
- **Inter-Racial Milestones:** Founding of a **Neutral Free City**, a cross-species royal marriage, or a major WTC trade treaty.

### 5.2 Council Outcomes
1. **Divine Truce (`DIVINE_TRUCE`):** Two sisters with sufficient `diplomacy` mutually agree **not** to cast wartime interventions (`WARD_DEFENDERS`) for `7` game days, letting mortals settle the conflict or negotiate peace on their own.
2. **Sisterly Warning / Protest:** High-`pride` or high-`protective_fury` sisters warn another sister to restrain her mortals' expansion (relayed subtly to mortals via Oracles).
3. **World Goddess Mediation:** If two sisters refuse a truce or breach the Non-Aggression Covenant, the **World Goddess (Wife of God)** convenes a mediation session—imposing a temporary intervention freeze (`cooldown` penalty) on the aggressor sister and escalating a concise report to **God**.
4. **Archive:** Notable 1-on-1 exchanges and all 5-Sister Council resolutions are logged into the **God Ledger** so God can read the family's dynamics.

---

## 6. Communication Pipeline to God & `GodPresenceTracker` (`sim_core/divine/god_ledger.py`)

### 6.1 Who Speaks to God
Only the **World Goddess** and the **5 Racial God-Mothers** may message God directly:
- **Racial God-Mother Reports:** Escalated urgent prayers/gratitude from their race, congregational altar petitions (with Prayer Head), Oracle appointments, border crises, or requests for Father's guidance.
- **World Goddess Reports:** Daily civilization summaries, Settlement Status Appeals / Neutral Free City approvals, Age-10 mixed-race tie-break decrees, Sister Council mediations, `RAM_WATERMARK` warnings, and `ErrorHealer` auto-fixes / `[CRITICAL]` escalations.

### 6.2 Real-Time vs. Away Delivery (`GodPresenceTracker`)
`GodPresenceTracker` monitors whether God is currently **Active** (connected in **Godot 4.7.2** OR attached to the **Rich God CLI**) or **Away (AFK)**:
- **When God is Active:**
  - High-salience reports from the World Goddess and 5 God-Mothers stream **in real time** to the In-Godot Divine Family HUD (`DIVINE_HUD_MESSAGE`) and the Rich God Terminal—while also buffering in RAM for the permanent daily archive.
  - Routine solo citizen prayers are automatically aggregated into clean digests (*"68 citizens of Solis prayed to [Human Mother] for a safe harvest"*) so 10,000+ agents never spam the HUD.
- **When God is Away (AFK):**
  - Zero mid-day disk writes. All divine reports, sisterly council dialogues, escalated prayers, gratitude notes, and `ErrorHealer` alerts accumulate strictly in RAM (`god_ledger_buffer`).
  - At the **end of the game day**, the **World Goddess** flushes the complete buffer atomically into **`data/god_ledger/day_XXXXX.md`** (and updates **`data/god_ledger/latest.md`**) as part of the SHA-256 Two-Phase Commit.

### 6.3 Example Daily God Ledger Format (`data/god_ledger/day_00014.md`)
```markdown
# World Goddess Daily Ledger — Day 14 (Autumn, Year 1)
Compiled & Verified by: **[World Goddess Name]** | SHA-256 Commit: `VERIFIED`

## 1. World Goddess Summary
- Living Population: 2,418 (Humans: 1,120 | Elves: 410 | Beasthumans: 742 | Demons: 100 | Dragons: 46)
- WTC CPI Inflation: 1.08 (+0.02) | Active Wars: 1 | Neutral Free Cities: 1
- Mixed-Race Patronage Tie-Break: Assigned child *Lyra Ashleaf* (Human/Elf) to **[Elf Mother Name]** for forest settlement harmony.

## 2. Messages from the 5 Racial God-Mothers
- **[Human Mother Name]:** "At the Altar of Solis (42 citizens), Prayer Head *Oracle Aldric* gave thanks for the autumn harvest and asked for protection along the eastern road."
- **[Demon Mother Name]:** "Ashridge mortals raised a new obsidian shrine, seeking protection against frost and beasts."
- **[Dragon Mother Name]:** "Human scouts entered Ashpeak without provocation; Elder *Ignis* shifted to True Dragon form to drive them back. No mortal casualties."

## 3. Inter-Sister Council Log
- **[Human Mother Name] ↔ [Dragon Mother Name]:** Agreed to a 7-day **Divine Truce**; [Human Mother Name] instructed Oracle Aldric to warn Solis against crossing Ashpeak's ridge.

## 4. Self-Healing Error Solver & System Alerts
- `[AUTO-HEALED]` Slot 1842 (`TENSOR_NAN_INF`): Restored GRU state from Day 13 verified snapshot. Daily fault count: 1/5.
```

---

## 7. Python Data Contracts (`sim_core/divine/hierarchy.py`)

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

DeitySlot = Literal["world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"]

class DivinePersonality(BaseModel):
    compassion: float = Field(default=0.6, ge=0.0, le=1.0)
    restraint: float = Field(default=0.6, ge=0.0, le=1.0)
    pride: float = Field(default=0.5, ge=0.0, le=1.0)
    protective_fury: float = Field(default=0.5, ge=0.0, le=1.0)
    diplomacy: float = Field(default=0.6, ge=0.0, le=1.0)

class DivineEntityRecord(BaseModel):
    slot: DeitySlot
    bestowed_name: str                      # Custom name set by God (Admin)
    role: Literal["WORLD_GODDESS", "RACIAL_GOD_MOTHER"]
    patron_race: Optional[Literal["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]] = None
    divine_energy: float = Field(default=300.0, ge=0.0, le=1000.0)
    personality: DivinePersonality = Field(default_factory=DivinePersonality)
    oracle_agent_ids: list[str] = Field(default_factory=list)  # Max 3 living Oracles
    active_truce_with: list[DeitySlot] = Field(default_factory=list)
    intervention_cooldown_until_tick: int = 0
    covenant_rebukes: int = 0

class SisterCouncilMessage(BaseModel):
    message_id: str
    day: int
    tick: int
    sender_slot: DeitySlot
    recipient_slots: list[DeitySlot]        # 1 sister, all 5 sisters, or ["world_goddess"]
    topic: Literal[
        "BORDER_FRICTION", "DRAGON_PROVOCATION", "WAR_INTERVENTION",
        "DIVINE_TRUCE", "COVENANT_BREACH", "FREE_CITY_ACCORD", "GOD_ESCALATION"
    ]
    summary: str
    resolution: Optional[str] = None
```

---

## 8. Two-Book Governance: World Library (`world_library`) & Divine Rules Book (`divine_codex`)

The civilization engine maintains two distinct books of knowledge and law, both fully readable by all entities:

### 8.1 World Library (`world_library`) — Read Access: Everyone
Contains cumulative mortal scholarship, history, martial treatises, craft recipes, and canonized scripture.
- **God (Admin):** Unrestricted direct write/edit anytime (`bypass_god_check=True`).
- **World Goddess:** May edit directly if at least 1 of her 5 Daughters (`>= 1`) votes `APPROVE`.
- **5 Daughters (God-Mothers) Alone:** May edit without the World Goddess if `> 50%` (`>= 3/5`) vote `APPROVE`.
- **Mortals:**
  1. Author passes `skills[topic] >= 0.70` (or `POPE` for scripture).
  2. Must first pass `> 50%` of the Mortal Council of Appointed Elders (`approvals * 2 > total_appointed_elders`, max 2 Elders per Nation).
  3. Passed proposals route to the 5 Racial God-Mothers:
     - **0 approvals in 30 game days:** Auto-expires (`EXPIRED`).
     - **`>= 1` approval:** Enters a **1-game-day objection window**.
     - **`> 50%` (`>= 3/5`) objections** before window closes: Blocked (`BLOCKED_BY_DAUGHTERS`); may be appealed to World Goddess or God.
     - **`< 3` objections** when window elapses: Passes and commits (`APPROVED`).

### 8.2 Divine Rules Book (`divine_codex`) — Read Access: Everyone
Stores permanent recorded divine laws/decrees (persisted in SQLite, logged to the God Ledger, referenced by Sister Councils) **and** dynamic live engine-parameter overrides (e.g., Non-Aggression Covenant penalties, Divine Truce duration, intervention cooldowns).

#### Option B: Split Write Authority (Maximum Security, No Parameter Bounds)
- **God (Admin):** Sole unrestricted direct write access (`bypass_god_check=True`) for both text decrees and unrestricted live engine-parameter overrides.
- **World Goddess + `> 50%` (`>= 3/5`) Daughters:** May commit **non-mechanical text decrees** directly to `divine_codex`.
- **Unrestricted Engine-Parameter Overrides & Rule Appeals:**
  - Neither the World Goddess nor the Daughters may apply parameter overrides directly.
  - Either the **World Goddess (alone)** OR **all 5 Daughters unanimously (`5/5`)** may submit a `DIVINE_CODEX_PROPOSAL` to **God (Admin)** via the God Ledger / Divine HUD.
  - Only **God** can approve and apply engine-parameter overrides.
- **5 Daughters Alone (< 5/5, or without Goddess on text decrees) & All Mortals:** Strictly blocked (`FAILURE`).