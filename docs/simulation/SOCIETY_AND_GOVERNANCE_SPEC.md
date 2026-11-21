# SOCIETY_AND_GOVERNANCE_SPEC.md — Dynamic Faith, Altar Prayers, Elder Council Library, Bordered Polities, Neutral Free Cities, Double-Entry Economy, WTC Inflation, Property & God Interfaces 

## 1. Context-Aware Morality & Physical Rumors
### 1.1 `CombatContext` Classification (`sim_core/society/morality.py`)
No global "good vs. evil" score exists. Every harm or kill event is tagged deterministically in RAM:
1. **`SELF_DEFENSE`**: Victim attacked or threatened actor within the last `60` ticks (including a provoked `DRAGON` shifting to `TRUE_DRAGON` to repel attackers).
2. **`DEFENDING_KIN_OR_TOWN`**: Victim attacked actor's kin, same-settlement citizen, or trespassed violently onto a protected sanctuary within `60` ticks and `24m`.
3. **`ACTIVE_WAR`**: Actor and victim belong to Nations/States/Cities in `active_wars`.
4. **`UNPROVOKED_ATTACK`**: None of the above.

Standing is strictly **per-settlement/nation** (`settlement_standing[settlement_id][agent_id]`) and **pairwise** (`Relationship(trust, affinity, fear, role)`). Lawful wartime combat or verified self-defense never adds a domestic criminal stigma.

### 1.2 Physical Information Spread: Rumor Packets (`sim_core/society/rumors.py`)
Zero global telepathy. Major events (crimes, wars, royal deaths, World Bank defaults, Dragon retaliations, Oracle guidance, God Avatar sightings, Elder Library decrees) spawn a `RumorPacket`:
- Each agent keeps a RAM ring buffer of up to `12` recent rumors.
- During local interactions (`dist <= 8m`), agents exchange their top `2` highest-salience rumors (`hops += 1`, `credibility *= 0.90`). Rumors expire after `1` game day or when `credibility < 0.20`.
- **Emergent Dragon Deterrence & Oracle Guidance:** Survivors of a provoked `TRUE_DRAGON` counterattack carry high-salience rumors back to their homelands, organically teaching mortal nations to respect Dragon mountain borders over generations. Similarly, **Mortal Oracles** spread subtle guidance from their Racial God-Mother through normal rumor propagation.

---

## 2. Dynamic Faith, Prayer Routing, Decay & Congregational Altar Prayers (`sim_core/society/religion.py`)
Faith is a living, fluctuating social force integrated with the **Divine Family Hierarchy** (`docs/simulation/DIVINE_HIERARCHY_SPEC.md`).

### 2.1 Faith Founding & Papal Authority
- **Founding a Faith:** Any `ELDER` with `faith_devotion >= 0.70` and `>= 15` local followers (or a God decree) may found a `ReligionRecord` aligned to a Racial God-Mother or the World Goddess, with weighted tenets (`pacifism`, `charity_tithe_rate`, `work_ethic`, `sacred_land_defense`, `heresy_intolerance`).
- **The Pope / High Cleric:** Elected across national borders by a conclave of senior clerics when vacant. Powers (committed via `RELIGION_DECREE` through `WorldGoddessCritic`): collect voluntary tithes (`2–10%`) into the Church Treasury, canonize Elder-approved World Library texts as scripture, crown or excommunicate Kings/Leaders (excommunication drops faithful loyalty by `-0.40`), mediate peace, or call crusades/schisms.

### 2.2 Strict Prayer Routing (No Direct Mortal-to-God Prayers)
- **Hard Rule:** Mortals **cannot** pray directly to **God (Admin)**.
- All mortal prayers, gratitude messages, and crisis pleas route strictly to:
  1. The mortal's **Racial God-Mother** (`agent.patron_godmother_slot`; for mixed-race children under age 10, either parental God-Mother until their **Age-10 Patronage Choice**), OR
  2. The **World Goddess (Wife of God)** (for inter-racial/Neutral Free City altars, seasonal crises, or world-wide petitions).
- **God** receives messages *exclusively* from the **World Goddess** and the **4 Racial God-Mothers**, who relay notable prayers, congregational altar calls, Sister Council debates, and world crises.

### 2.3 Intent-Scaled Prayer Gains & Inactivity Decay
When an agent executes `PERFORM_TRADITION_OR_PRAY`, its `faith_devotion` (and for uncommitted mixed-race children under age 10, its per-deity `godmother_affinities`) updates based on **why** it prayed:

| Prayer Scenario | `faith_devotion` Delta | Notes |
| :--- | :--- | :--- |
| **Earnest Voluntary Prayer / Gratitude** | **`+0.045`** | Agent chose to pray freely or express thanks after surviving hardship/blessing |
| **Congregational Altar Prayer** | **`+0.035`** | Praying together (`>= 3` mortals) at an altar; boosts local community trust & Divine Energy |
| **Crisis Plea** | **`+0.025`** | Praying during famine, war, illness, or child distress (amplified `+0.03` if relief follows) |
| **Parent-Directed / Social Obligation** | **`+0.012`** | Child praying because a parent/tradition prompted them (gradual habit formation) |
| **Prolonged Inactivity Decay** | **`-0.015` / day** | After **`> 2` game days** without praying or attending an altar, affinity gradually decays toward `0.0` |

### 2.4 Accessible Prayer Thresholds, Congregational Altars & Salience Grouping
- **Who Can Send Structured Prayers & Gratitude to Their Deity:**
  - **Oracles/Champions, Priests, Clerics & Popes:** Always enabled.
  - **Faithful Citizens:** Any mortal with **`faith_devotion >= 0.35`** can send prayers, **gratitude/thanks**, or petitions.
  - **Crisis Pleas:** Any mortal with **`faith_devotion >= 0.15`** can send an urgent plea during famine, war, loss of kin, or unjust crisis.
- **Congregational Altar Prayers (Prayer Head Aggregation):**
  - When `>= 3` living mortals pray at the same Altar parcel within the same prayer window, the engine aggregates them into **one unified congregational message** and triggers Godot's `AltarPrayerBeacon.tscn` vertical light pillar.
  - **Prayer Head Selection:** Highest-ranking **Oracle/Champion** present → else **Pope/High Cleric/Priest** → else highest-devotion **Elder**.
  - Example relayed to God: `[Day 14 | Altar of Solis (42 citizens) | Prayer Head: Oracle Aldric -> Human Mother]: "We give thanks for the autumn harvest and ask protection over our borders."`
- **Salience Grouping (Anti-Spam at 10k+ Scale):**
  - **Individual Lines:** World Goddess reports, God-Mother escalations, Inter-Sister Council logs, Congregational Altar Prayers, urgent crisis pleas, heartfelt gratitude, and `ErrorHealer` alerts.
  - **Digest Summaries:** Routine solo citizen prayers aggregate cleanly (*"68 citizens of Ironhold prayed to [Human Mother] for safety"*).

---

## 3. Two-Book Governance: World Library & Divine Rules Book (`sim_core/society/library.py`)
Random agents **cannot** arbitrarily edit, overwrite, or delete knowledge or divine decrees. The world maintains two distinct books, both readable by all mortals and deities:

### 3.1 World Library (`world_library`) — Mortal & Divine Scholarship
Read access is open to all mortals and deities.
- **Appointment Limit:** Each recognized **`NATION`** may appoint **at most `2` living Elders** (`stage == "ELDER"` or senior scholar) to the **World Library Council** (committed via `SETTLEMENT_UPDATE(action="APPOINT_LIBRARY_ELDER")`).
- **Write / Proposal Protocols:**
  1. **God (Admin):** Unrestricted direct write/edit anytime (`bypass_god_check=True`, e.g. via God Console or Godot's 2D modal emitting `GOD_LIBRARY_EDIT`).
  2. **World Goddess:** Direct edit with **at least 1 of the 5 Daughters** (`>= 1`) voting `APPROVE`.
  3. **5 Daughters (God-Mothers) Alone:** Direct edit without the World Goddess if **`> 50%`** (**at least 3 of 5**) vote `APPROVE`.
  4. **Mortals:**
     - Author must have `skills[topic] >= 0.70` (or be `POPE` for scripture) to draft a `LibraryProposalRecord`.
     - **Stage 1 (Elders Council):** Appointed Council Elders cast votes (`APPROVE` / `REJECT`). Must pass with **strict `> 50%` consensus** (`approvals * 2 > total_appointed_elders`).
     - **Stage 2 (God-Mother Review):** Passed mortal proposals transition to `PENDING_GODMOTHERS`:
       - If **0** God-Mothers approve within **30 game days**, the proposal **auto-expires** (`EXPIRED`).
       - Once **`>= 1`** God-Mother approves, the proposal enters a **1-game-day objection window** (`OBJECTION_WINDOW`).
       - If **`> 50%` (`>= 3/5`)** of God-Mothers object before the 1-day window closes, it is **blocked** (`BLOCKED_BY_DAUGHTERS`). Blocked proposals may be formally appealed to the **World Goddess** or **God** for final judgment.
       - Otherwise, once the 1-day window elapses with `< 3` objections, it **passes and commits** (`APPROVED`) into `world_library`.
  5. **Unauthorized Attempts:** Any random agent attempting an unauthorized Library edit receives `CriticVerdict(status="FAILURE")`. Vandalism against Library halls opens a `VANDALISM` Judiciary case.

### 3.2 Divine Rules Book (`divine_codex`) — Divine Laws & Live Parameter Overrides
Read access is open to all. Stores permanent recorded divine laws/decrees (persisted in SQLite, logged to the God Ledger, referenced by Sister Councils) **and** dynamic live engine-parameter overrides (e.g., Non-Aggression Covenant penalties, Divine Truce duration, intervention cooldowns).

#### Option B: Split Write Authority (Maximum Security, No Parameter Bounds)
- **God (Admin):** Sole unrestricted direct write access (`bypass_god_check=True`) for text decrees and live engine-parameter overrides.
- **World Goddess + `> 50%` (`>= 3/5`) Daughters:** May commit **non-mechanical text decrees** directly to `divine_codex`.
- **Unrestricted Engine-Parameter Overrides & Rule Appeals:**
  - Neither the World Goddess nor the Daughters may apply parameter overrides directly.
  - Either the **World Goddess (alone)** OR **all 5 Daughters unanimously (`5/5`)** may submit a `DIVINE_CODEX_PROPOSAL` to **God (Admin)** (routed via God Ledger / Divine HUD).
  - Only **God** can approve and apply parameter overrides to the live simulation engine.
- **5 Daughters Alone (< 5/5, or without Goddess on text decrees) & All Mortals:** Strictly blocked (`FAILURE`).

---

## 4. Five-Tier Polities, Neutral Free Cities, Status Appeals & Explicit Borders (`sim_core/society/borders.py`, `politics.py`)

### 4.1 Five-Tier Territorial Hierarchy & World Goddess Status Appeals
Settlements cannot silently self-declare higher status. To earn or upgrade a title, a settlement's founder/leader must submit a formal **`SETTLEMENT_APPEAL`** to the **World Goddess**, which verifies objective population, contiguous parcel border, and treasury criteria:

| Tier | Min Living Pop | Min Owned `16×16m` Parcels | Min Treasury | Special Institutional Unlock |
| :--- | :--- | :--- | :--- | :--- |
| **`VILLAGE`** | `10` | `4` contiguous parcels | `50` | Local headman, shared granary, explicit village border |
| **`TOWN`** | `50` | `16` contiguous parcels | `300` | Local Judiciary court, property registry, infant welfare |
| **`CITY`** | `250` | `48` contiguous parcels | `1,500` | Regional WTC trading hub, Library branch, full garrison; eligible for **Neutral Free City** appeal |
| **`STATE`** | `600` | `100` parcels (or `>= 2` towns/cities) | `5,000` | Provincial governance, regional tax/tariff authority |
| **`NATION`** (Kingdom/Republic) | `1,000` | `160` parcels (or `>= 2` cities/states) | `12,000` | Sovereign diplomacy, war declarations, **appoint up to 2 World Library Elders** |

*(Thresholds are configurable in `sim_core/config.py` for smaller test worlds.)*

### 4.2 Neutral Free Cities (Inter-Racial Diplomacy Zones)
- Any `CITY` containing significant living populations of **`>= 2` races** (each representing `>= 15%` of living city population) may submit a `SETTLEMENT_APPEAL(requested_status="NEUTRAL_FREE_CITY")` to the **World Goddess**.
- **Mechanical Properties:**
  - Legally war-exempt (`war_exempt = true`): cannot declare offensive wars; attacking a Neutral Free City incurs severe standing penalties across all 5 races and triggers immediate **5-Sister Council** intervention.
  - Serves as a protected cosmopolitan hub for **WTC Regional Exchanges**, **World Library Branches**, inter-racial families, and peaceful `HUMANOID_DRAGON` visitors.

### 4.3 Explicit Non-Overlapping Borders
- Every `VILLAGE`, `TOWN`, `CITY`, `STATE`, and `NATION` owns an **explicit set of `16×16m` chunk parcels** (`parcel_id = f"{cx}_{cz}"`) registered in the NumPy spatial hash grid and projected visually in Godot via ground decals/Terrain3D border overlays.
- Two entities at the same tier **cannot** overlap on the same parcel; borders shift only via peaceful treaty/purchase (`PARCEL_TRANSFER`), formal annexation, or wartime conquest.

### 4.4 Governance: Kings vs. Elections
- **Monarchy (`KING`):** Crown passes to eldest living legitimate child, then sibling/nearest kin. Zero living heirs trigger a **Succession Crisis** (noble council vote or Civil War).
- **Republic (`ELECTED`):** Every `1` Year (`28` Game Days, or on incumbent death), living `ADULT`/`ELDER` citizens vote using a vectorized utility formula scoring personal prosperity, trust, shared religion/race, inflation pain, and war weariness.

---

## 5. Strictly Closed-Loop Double-Entry Economy, World Bank, Racial Trade & WTC Inflation

### 5.1 Zero-Magic Double-Entry Transfers (`sim_core/society/economy.py`)
- **World Bank is the Sole Currency Issuer:** No subsystem may conjure credits out of thin air.
- **Double-Entry Invariant:** Every transfer—including **a parent giving money/allowance to their child**, peer trade, property purchase, tax, tithe, or court fine—executes as `debit(sender, amount)` + `credit(receiver, amount)`. If `sender.credits < amount`, the transaction fails immediately (`FAILURE: "Insufficient funds"`).
- **Credit Score (`300–850`, start `650`):** `+10` on timely loan payments, `-35` on delinquency, `-100` on default. `3` consecutive missed windows trigger `DEFAULTED`, collateral/parcel/treasury seizure, credit freeze, and an automatic `DEBT_DEFAULT` Judiciary case.

### 5.2 World Trade Centre (WTC), Racial Comparative Advantage & Real Inflation (`sim_core/society/wtc_market.py`)
- Order-book exchange clearing `food`, `wood`, `stone`, `iron`, `tools`, and `land_deeds` each civic tick ($\pm 15\%$ clamp per tick), displayed live on Godot's `UPDATE_ONCE` 3D hanging signs.
- **Inter-Racial Trade Dynamics:** Dwarves (`BEASTHUMAN`) supply surplus `stone`/`iron`/`tools`, Elves supply `food`/timber, Humans drive WTC banking/logistics, and Dragons hold rare mountain ores—creating natural incentives for cross-racial trade treaties, tariffs, and Neutral Free Cities.
- **Real Inflation ($\text{CPI}_t$):** Driven by circulating money supply $M_t$ vs. trailing real output $Q_t$:
  $$\text{CPI}_t = \frac{\sum_k w_k P_k(t)}{\sum_k w_k P_k(0)}, \qquad \text{Monetary Pressure} = \frac{M_t / Q_t}{M_0 / Q_0}$$
- Winter scarcity or excessive war borrowing spikes `CPI`, eroding real wages and driving voter backlash, unrest, or fiscal tightening.

---

## 6. Property Ownership, Real Estate, Escheatment, Traditions & Judiciary

### 6.1 `16×16m` Chunk Parcels, Inheritance & Escheatment (`sim_core/society/property.py`)
Every `16×16m` parcel tracks `owner_id`, `owner_type` (`AGENT`, `SETTLEMENT`, `NATION`, `CHURCH`, `UNCLAIMED`), `settlement_id`, `nation_id`, `assessed_value`, `for_sale_price`, `tenant_id`, and `rent_per_civic_tick`.
- **Probate Cascade on Death:**
  1. **Direct Heirs:** Split evenly among living spouse and children.
  2. **Extended Kin:** Living parents or siblings if no spouse/children.
  3. **Escheatment (No Living Heirs):**
     - **Inside any Village/Town/City/State/Nation border:** Ownership transfers automatically to that **Settlement / Kingdom Treasury** (auctionable at the WTC or grantable to citizens).
     - **Outside all borders (Wilderness):** Flips to **`UNCLAIMED` (Nameless, `owner_id = None`)**—switching its Godot structures to abandoned ruins open to any settler or squatter.

### 6.2 Emergent Traditions (`sim_core/society/traditions.py`) & Judiciary (`judiciary.py`)
- **Traditions:** Evolvable `TraditionRecord` memes (`FIRST_DAY_OF_WINTER`, `HARVEST_SURPLUS`, `ROYAL_DEATH`, `MARRIAGE`, `WAR_VICTORY`, `GOD_SIGHTING`) with ritual actions and local `taboo_penalty` when ignored; carried by migrants across racial and national borders.
- **Judiciary:** Adjudicates `THEFT`, `UNPROVOKED_ATTACK`, `VANDALISM`, `DEBT_DEFAULT`, `TRESPASS`, and `CONTESTED_COMBAT`. Verified `SELF_DEFENSE`, `DEFENDING_KIN_OR_TOWN`, and `ACTIVE_WAR` are automatically `ACQUITTED` with zero domestic criminal record. Maintains **Population Ledger**, **Fatality Index** (including infant mortality and cross-species birth complications by race/season), and **Criminal Records**.

---

## 7. God Avatar, Godot 4.7.2 Interfaces, God Ledger & Rich God Console
You oversee the world through **three synchronized interfaces**:

1. **Godot 4.7.2 Unified 3D Client & Orbital God Map (`godot_client/`):**
   - **3D Reality Bubble (`60–120` pooled mortals within `120–160m`):** Fly freely in RTS mode or drop down as your visible `god_avatar.vrm` (`is_god = true`). Walk into WTC halls to read live `UPDATE_ONCE` CPI/price boards, click Library Lecterns to open the 2D `TextEdit` modal (routed via WebSocket to Python), spot `AltarPrayerBeacon` light pillars, and watch Dragons shift to `TRUE_DRAGON` form.
   - **Orbital God Map (`> 250m` altitude):** Zoom out to see all **10,000+ agents** in 1 draw call (`MultiMeshInstance3D`), explicit `16×16m` borders, wars, religions, and inflation heatmaps; click anywhere to swoop back into 3D.
   - **In-Godot Divine Family HUD:** Live stream of messages from the **World Goddess** and **4 Racial God-Mothers**, Sister Council summaries, `ErrorHealer` alerts, deity naming, and `speed 1x..60x` controls.
2. **God Presence & Persistent Daily God Ledger (`sim_core/divine/god_ledger.py`):**
   - **Active (Godot or CLI connected):** Divine Family reports, escalated prayers, congregational altar calls (with Prayer Head), and `ErrorHealer` alerts stream **in real time**.
   - **Away (AFK):** Buffered strictly in RAM during the 1–2 real-hour game day and flushed atomically by the **World Goddess** at end-of-day into **`data/god_ledger/day_XXXXX.md`** (and `latest.md`).
3. **Rich Terminal God Console (`sim_core/god_console/cli.py`):**
   - **Inspect:** `status`, `pop [race|settlement]`, `fatalities`, `crimes [agent]`, `nations`, `borders`, `elections`, `religions`, `deities`, `council`, `elders`, `wtc`, `bank`, `parcel <cx> <cz>`, `traditions`, `library [topic]`, `ledger [day]`, `inspect <agent_id>`.
   - **Intervene:** `name_deity <slot> "<name>"`, `spawn <race> [sub_lineage]`, `bless`, `curse`, `smite`, `war declare/peace`, `bank grant/forgive`, `wtc freeze/tariff`, `coronate`, `appoint_pope`, `decree "<msg>"`, `speed <1x..60x>`, `pause`, `resume`, `step <N>`, `save`, `rewind <day>`, `shutdown`.