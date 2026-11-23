# NEURAL_AND_LIFECYCLE_SPEC.md — 4-Pillar Hybrid Cognitive Core, Unbounded Slab-Grown Tensor Brains, GRU Memory, 8 Semantic Speech Acts, 5-Race Lifecycle, Distress/Crying & Mortality 

## 1. Unbounded Batched Tensor Brain Architecture & 4-Pillar Hybrid Cognitive Core (`sim_core/neural/`, `sim_core/brains/`)
There is **no hard `MAX_AGENTS` cap**. To simulate **1,000–10,000+ (and growing) unique, individually-evolved neural agents** in ~8–15 ms per cognitive tick on an AMD Ryzen 7 8840HS CPU (under 250 MB RAM at 10,000 agents), never loop over separate PyTorch `nn.Module` instances in Python. Pack all living agents into **contiguous slot-indexed tensors** (`slot_idx in [0, capacity)`), dynamically grown in **slabs of `2,048` slots** via `torch.cat` whenever `free_slots` is empty.

### The 4-Pillar Hybrid Cognitive Architecture
Gaia v4.0 introduces the **4-Pillar Hybrid Cognitive Core** (`sim_core/brains/`):
- **Pillar 1 — 3-Tier Hierarchical Neural Brain:**
  - **Tier 1 (`SharedLivingNet`):** Species-wide base physical survival and caregiving reflexes (Linear 32 $\rightarrow$ 64 $\rightarrow$ 64 $\rightarrow$ 20).
  - **Tier 2 (`ProfessionNetRegistry`):** 10 vocational MLP networks (Lv. 1–10 mastery) covering `FARMER`, `LUMBERJACK`, `MINER`, `BLACKSMITH`, `MERCHANT`, `BUILDER`, `GUARD`, `SCHOLAR`, `CLERIC`, and `HERBALIST`.
  - **Tier 3 (`BatchedAgentSelfNet`):** Slab-grown per-agent unique weights with manual `torch.bmm` + `GRUCell(20, 32)` working memory modulating preferences.
- **Pillar 2 — Grounded `MemoryRAGIndex`:**
  - Strict information asymmetry: mortal agents can only recall memories or cite books they have physically read or been told (`known_books: set[str]`). Zero global state hallucination.
- **Pillar 3 — 10-D `PersonalityVector` & `MoodState`:**
  - 10 orthogonal personality dimensions: `openness`, `conscientiousness`, `extraversion`, `agreeableness`, `neuroticism`, `ambition`, `caution`, `loyalty`, `rule_respect`, `faith_devotion`.
  - Couplings to dynamic `MoodState` (`joy`, `anger`, `fear`, `gloom`, `calm`) shaping action logit biases.
- **Pillar 4 — `SleepCycleConsolidator`:**
  - End-of-day sleep consolidation distilling daily episodic experiences into long-term traits with bounded drift ($\le 0.05$ per day).

- **Soft RAM Watermark:** `psutil` checks host memory once per civic tick; exceeding **75% host RAM** emits a `[RAM_WATERMARK]` alert to the World Goddess, God Console, Godot Divine HUD, and God Ledger without crashing or blocking births.
- **Race-Extensible Design (No Tensor Bloat):** Racial biology, lifespans, learning speeds, and visual scales are applied via the **`RaceProfile` multiplier layer** (`sim_core/races.py`, see `docs/simulation/RACES_AND_BIOLOGY_SPEC.md`) rather than hardcoding race-specific network dimensions. Existing neural checkpoints remain cleanly compatible across all 5 races (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`) and any future sub-lineages.
- **Multi-Tier Cognitive LOD:** Every tick evaluates active slots according to LOD tier:
  - **Tier 0 (3D Reality Bubble, `<= 160m` of God's camera):** `2 Hz` (every tick), synced to Godot's pre-allocated 60–120 mortal node pool.
  - **Tier 1 (Distant Awake):** `1 Hz` (every 2nd tick, staggered even/odd batches).
  - **Tier 2 (Distant Sleeping/Sheltered Idle):** `0.25 Hz` (every 8th tick; wakes immediately to Tier 1 on threat, provocation, injury, distress spike, or event).

### 1.1 `SharedSkillNet` (`sim_core/neural/shared_net.py`)
One shared MLP evaluated in a single batched forward pass across the scheduled batch of $N$ agents. It provides species-wide physical, caregiving, economic, and social competence over **20 embodied/macro primitives** and a state-value estimate $V(s)$.

- **Input Tensor $X_{\text{shared}} \in \mathbb{R}^{N \times 32}$ (normalized to $[0, 1]$ or $[-1, 1]$):**
  - `[0..3]` Core Vitals: `health / max_health`, `hunger / 100`, `stamina / 100`, `age_norm` (`age_days / (30 * race.lifespan_multiplier)`)
  - `[4..6]` Biological Condition: `injured` (`0..1`), `illness` (`0..1`), `distress` (`0..1`)
  - `[7..10]` Stage One-Hot: `[is_infant, is_child, is_adult, is_elder]`
  - `[11..15]` Environment & Season: `time_of_day / 24000`, `is_sheltered`, `danger_level`, `in_home_settlement`, `season_harshness` (`0.0` Spring/Summer, `0.4` Autumn, `1.0` Winter)
  - `[16..19]` Resource Proximity (`1 / (1 + dist/16)`): `food_prox`, `wood_prox`, `stone_prox`, `shelter_prox`
  - `[20..23]` Inventory Ratios (clamped to `1.0`): `food_inv`, `wood_inv`, `stone_inv`, `tools_inv`
  - `[24..28]` Social, Care & Economy: `nearby_allies_norm`, `nearby_threats_norm`, `parent_or_kin_nearby`, `crying_child_nearby`, `local_inflation_pressure`
  - `[29..31]` Conflict, Culture & Divine Presence: `home_nation_at_war`, `active_tradition_or_altar_trigger`, `is_god_or_deity_nearby` (`1.0` if God Avatar, World Goddess, or Racial God-Mother is within sensory radius, else `0.0`)
- **Architecture:**
  - `Linear(32, 64) -> LayerNorm -> Tanh`
  - `Linear(64, 64) -> LayerNorm -> Tanh`
  - **Policy Head:** `Linear(64, 20)` $\rightarrow L_{\text{shared}} \in \mathbb{R}^{N \times 20}$
  - **Value Head:** `Linear(64, 1)` $\rightarrow V \in \mathbb{R}^{N \times 1}$

### 1.2 `BatchedAgentSelfNet` with GRU Working Memory (`sim_core/neural/batched_self_net.py`)
Each agent owns **unique, evolvable weights** stored inside contiguous 3D parameter tensors of leading dimension $C$ (`capacity`, grown in slabs of `2,048`). A **batched manual `GRUCell(20, 32)`** gives every agent true multi-tick short-term working memory (~5 KB per agent).

- **Input Tensor $X_{\text{self}} \in \mathbb{R}^{N \times 20}$:**
  - `[0..5]` Traits & Faith: `[caution, sociability, ambition, loyalty, rule_respect, faith_devotion]` in $[-1, 1]$ (initialized with racial priors + parental inheritance + birth imprinting)
  - `[6..9]` Self-Model / Surprise Loop: `last_predicted_reward`, `last_prediction_error` (clamped $[-2, 2]$), `ema_failure_rate`, `last_critic_verdict` (`+1` World Goddess/God-Mother success, `-1` failure, `0` none)
  - `[10..13]` Economic & Legal Self-Status: `credits_norm` ($\tanh(\text{credits}/200)$), `credit_score_norm`, `owns_property_flag`, `wanted_or_debt_flag`
  - `[14..17]` Social & Cultural Standing: `avg_nearby_trust`, `has_dependent_child`, `skill_mastery_avg`, `settlement_standing_norm`
  - `[18..19]` Spiritual State: `ticks_since_last_prayer_norm`, `recent_gratitude_event_flag`
- **Contiguous Batched Parameters (per active slot $i \in [0, C)$):**
  - **Batched GRUCell (`20 -> 32`):**
    - `W_ih`: `(C, 20, 96)`, `b_ih`: `(C, 96)` (packed reset $r$, update $z$, candidate $n$ gates)
    - `W_hh`: `(C, 32, 96)`, `b_hh`: `(C, 96)`
    - Persistent working-memory hidden state `H`: `(C, 32)` (zeroed strictly on birth; preserved across ticks and daily checkpoints)
  - **Batched Output Heads (`32 -> 20`, `32 -> 1`, `32 -> 1`):**
    - `W_out`: `(C, 32, 22)`, `b_out`: `(C, 22)`
    - Slices: `[0:20]` $\rightarrow \Delta L_{\text{self}}$ (preference modulator), `[20:21]` $\rightarrow \hat{r}_t$ (outcome predictor), `[21:22]` $\rightarrow \sigma(\cdot) = c_t$ (confidence)
- **Single-Call Batched Forward Math (No Python Loop):**
  ```python
  # x_self: (N, 20), h_prev: (N, 32)
  gi = torch.bmm(x_self.unsqueeze(1), W_ih[idx]).squeeze(1) + b_ih[idx]  # (N, 96)
  gh = torch.bmm(h_prev.unsqueeze(1), W_hh[idx]).squeeze(1) + b_hh[idx]  # (N, 96)
  i_r, i_z, i_n = gi.chunk(3, dim=-1)
  h_r, h_z, h_n = gh.chunk(3, dim=-1)
  r = torch.sigmoid(i_r + h_r)
  z = torch.sigmoid(i_z + h_z)
  n = torch.tanh(i_n + r * h_n)
  h_next = (1.0 - z) * n + z * h_prev                                    # (N, 32)
  out = torch.bmm(h_next.unsqueeze(1), W_out[idx]).squeeze(1) + b_out[idx]
  ```
- **Tensor Integrity Guard:** After every forward pass and backprop step, check `torch.isfinite(out)` and `torch.isfinite(h_next)`. Any `NaN`/`Inf` slot is immediately routed to `ErrorHealer.handle("TENSOR_NAN_INF", slot=...)` to restore that slot from the last verified daily snapshot without affecting other agents.

### 1.3 Competence-Preserving Blending & Stage Masking
Personality, racial temperament, and faith shape *priorities, parenting style, politics, and risk tolerance*, never corrupting basic physical survival once unlocked:

$$L_{\text{raw}} = L_{\text{shared}} + \alpha_{\text{mod}} \cdot \tanh(\Delta L_{\text{self}}) \cdot g_{\text{survival}}$$

- $\alpha_{\text{mod}} = 1.25$.
- $g_{\text{survival}} \in [0.25, 1.0]$: vectorized clamp to `0.25` whenever `health / max_health < 0.25` or `hunger < 15.0`.
- **Hard Stage Masking:** Mask locked primitives with `-1e9` using a precomputed `(4, 20)` boolean stage mask tensor before `softmax(L_raw / tau)` with $\tau = 1.2 - 0.5 c_t$.

---

## 2. The 20 Embodied, Caregiving & Macro Primitives
Actions `0..16` execute physically with animations in Godot 4.7.2 when inside the Reality Bubble (or via fast vectorized transition rules + `world_heightmap.npy` elevation outside); actions `17..19` drive economic, property, and civic governance:

| Index | Primitive | Min Stage | Description |
| :--- | :--- | :--- | :--- |
| `0` | `IDLE` | `INFANT` | Pause, observe surroundings, exchange local rumors |
| `1` | `WANDER_LOCAL` | `INFANT` | Local exploration / locomotion practice |
| `2` | `FOLLOW_AGENT` | `INFANT` | Follow parent, caretaker, ally, Oracle, or leader |
| `3` | `FLEE_THREAT` | `INFANT` | Escape hostile agent, provoked True Dragon, or war raid |
| `4` | `SELF_CARE_REST` | `INFANT` | Rest, hygiene, shelter recovery (heals injury/illness gradually) |
| `5` | `EAT_FOOD` | `INFANT` | Consume food from inventory or caretaker |
| `6` | `FORAGE_FOOD` | `CHILD` | Gather berries/crops (reduced 60% in Winter; Elf nature bonus) |
| `7` | `GATHER_WOOD` | `CHILD` | Harvest timber |
| `8` | `APPROACH_AND_INTERACT` | `CHILD` | Teach, learn, trade, gossip, or social bond |
| `9` | `PERFORM_TRADITION_OR_PRAY` | `CHILD` | Pray earnestly/at altar to **Racial God-Mother or World Goddess** (never directly to God), express gratitude, perform local ritual, or tithe |
| `10` | `COMFORT_OR_CARE_CHILD` | `ADULT` | Stay near crying/injured/ill child to gradually soothe emotional distress, feed, or tend wounds |
| `11` | `GIVE_FAMILY_ALLOWANCE` | `ADULT` | Strict double-entry credit transfer from parent to offspring (fails if insufficient credits) |
| `12` | `MINE_STONE_OR_ORE` | `ADULT` | Extract stone/iron/mountain ore (Dwarf & Dragon specialty) for construction & WTC sale |
| `13` | `CRAFT_TOOL` | `ADULT` | Convert materials into tools/goods (Dwarf mastery bonus) |
| `14` | `BUILD_SHELTER_STEP` | `ADULT` | Build/upgrade racial housing, altar, library, or defense on owned/settlement parcel |
| `15` | `DEFEND_OR_ATTACK` | `ADULT` | Combat (always tagged with immutable `CombatContext`; may trigger Dragon `TRUE_DRAGON` metamorphosis) |
| `16` | `DEPOSIT_OR_WITHDRAW_CHEST` | `ADULT` | Interact with settlement/personal storage |
| `17` | `MARKET_WTC_ORDER` | `ADULT` | Submit commodity buy/sell order at World Trade Centre |
| `18` | `PROPERTY_BUY_OR_SELL` | `ADULT` | Buy unclaimed/listed `16×16m` parcel, list own parcel, or collect rent |
| `19` | `CIVIC_OR_BREED_ACTION` | `ADULT` | Propose breeding, vote/campaign, vote on Library Elder Council, submit settlement/Free City appeal to World Goddess, apply for Bank loan |

### 2.1 The 8 Semantic Speech Acts (`sim_core/society/speech_acts.py`)
In addition to macro primitives, agents engage in physical acoustic dialogues (8m radius) through structured `SpeechActRecord`s:
1. `GREET`: Polite acknowledgement between neighbors, raising pairwise `affinity` (`+0.02`).
2. `WARN_PRICE_SPIKE`: Alerts nearby consumers of high WTC inflation or commodity spikes, logging to their `MemoryRAGIndex`.
3. `TRADE_OFFER`: Direct bilateral barter or sale proposal between merchants and citizens.
4. `SHARE_BOOK_LORE`: Scholar or elder shares knowledge from a known World Library book with an apprentice (`teach_knowledge()`).
5. `REPORT_CRIME`: Witness shouts a crime report, instantly alerting nearby Palace Knights or City Guards and filing a case in the Judiciary.
6. `PRAYER_CALL`: Devout citizen or cleric rallies nearby faithful to join a Congregational Altar Prayer.
7. `COURT`: Romantic courtship proposition, checking mutual readiness and boosting mutual affinity if successful.
8. `POLITICAL_DEBATE`: Public campaign speech in settlement square, influencing votes for Headman, Mayor, or King elections.

- **Godot Reality Bubble Visualization:** Diegetic fantasy utterances (e.g., *"Good hunting to you, kin!"* or *"Watch your step around me, scholar."*) stream over `BUBBLE_SYNC` as `speech_text` to display above mortal heads in Godot.

---

## 3. Intrinsic Curiosity, Self-Awareness, Dependency Trap & Batched Backpropagation (`sim_core/neural/trainer.py`)
### 3.1 Prediction Error & Stage-Weighted Intrinsic Curiosity
When realized extrinsic reward $r_t^{\text{ext}}$ arrives on tick $t+1$:
1. Compute prediction error (surprise): $e_t = r_t^{\text{ext}} - \hat{r}_t$.
2. Compute **stage-weighted intrinsic curiosity bonus**:
   $$r_t^{\text{cur}} = \kappa(\text{stage}) \cdot \min(\vert e_t \vert, 1.5)$$
   where $\kappa(\text{INFANT}) = 0.05$, $\kappa(\text{CHILD}) = 0.035$, $\kappa(\text{ADULT}) = 0.01$, and $\kappa(\text{ELDER}) = 0.0$.
3. Total learning reward: $r_t = r_t^{\text{ext}} + r_t^{\text{cur}}$.
   - **No Auto-Evil Penalty:** Combat tagged `SELF_DEFENSE`, `DEFENDING_KIN_OR_TOWN`, or `ACTIVE_WAR` carries zero automatic moral penalty.
   - **RBAC & Conservation Learning:** Receiving a `CriticVerdict(status="FAILURE")` from the World Goddess (e.g., unauthorized World Library edit, insufficient funds for allowance, or invalid breeding) yields `-0.60` so agents learn real institutional and economic limits.
   - **The "Mortal Dependency" Trap:** If a Racial God-Mother frequently answers prayers with direct food/healing miracles, `PERFORM_TRADITION_OR_PRAY` receives high immediate survival reward—causing her mortals' neural nets to over-weight prayer relative to `FORAGE_FOOD` and `BUILD_SHELTER_STEP`. If her Divine Energy runs dry during a harsh Winter, an over-coddled civilization suffers severe famine, giving God-Mother restraint real mechanical weight.

### 3.2 Vectorized Rollout Buffer & Backpropagation (Every 32 Ticks)
Store the last $T = 32$ steps in pre-allocated RAM ring tensors (`shape = (32, C, ...)`). Every 32 sim ticks:
1. Compute vectorized discounted returns $G_t$ ($\gamma = 0.95$) and normalized advantages $A_t = G_t - V(s_t)$.
2. Compute batched loss over active slots:
   - **Policy Loss:** $-\text{mean}(\log \pi(a_t \vert s_t) \cdot \text{detach}(A_t)) - \text{mean}(\beta_{\text{ent}}(\text{stage}) \cdot H(\pi_t))$
   - **Value Loss (`SharedSkillNet`):** $\text{MSE}(V(s_t), G_t)$
   - **Self-Prediction Loss (`BatchedAgentSelfNet`):** $\text{MSE}(\hat{r}_t, r_t^{\text{ext}})$
3. Run `loss.backward()`, clip global gradient norm at `1.0`, and apply **per-slot stage- and race-scaled neuroplasticity learning rates** (`lr_slot = base_stage_lr * race.neuroplasticity_mult`):
   - `INFANT`: `3.0e-3` (entropy `0.025`)
   - `CHILD`: `1.5e-3` (entropy `0.020`)
   - `ADULT`: `5.0e-4` (entropy `0.008`)
   - `ELDER`: `1.5e-4` (entropy `0.004`)
   - `SharedSkillNet`: Adam `3.0e-4` (conservative shared update).

---

## 4. Realistic Biology: Injury, Illness, Infant Distress, Comforting & Dragon Metamorphosis (`sim_core/lifecycle.py`)
### 4.1 Injury & Illness States
- **`injured` $\in [0.0, 1.0]$:** Increases from combat hits, falls, or hazards. While `injured > 0.1`, passive health regeneration is disabled; healing requires `SELF_CARE_REST` in shelter or care from a parent/healer (or a restricted God-Mother healing blessing).
- **`illness` $\in [0.0, 1.0]$:** Triggered probabilistically by unsheltered Winter exposure (scaled down by `RaceProfile.winter_resistance`) or prolonged starvation (`hunger < 20`). Drains stamina and health gradually until treated with rest, warmth, and food.

### 4.2 Root-Cause Infant Distress, Crying & No-Magic Comforting
Every `INFANT` (and young `CHILD`) maintains `distress` $\in [0.0, 1.0]$ and boolean **`crying = (distress >= 0.45)`**:
- **Root-Cause Pressures Pushing `distress` Upward Each Tick:**
  - Unfed (`hunger < 55`): `+0.04` to `+0.09` / tick
  - Injured or ill (`injured > 0.1` or `illness > 0.1`): `+0.05` / tick
  - Cold / unsheltered in Winter: `+0.06` / tick (attenuated by `winter_resistance`)
  - Nearby threat, provoked True Dragon aura, or active combat (`dist <= 16m`): `+0.08` / tick
  - Caretaker absent (`nearest_parent_dist > 12m`): `+0.03` / tick
- **Gradual Comforting (`COMFORT_OR_CARE_CHILD`):**
  - A nearby parent/caretaker (`dist <= 4m`) executing `COMFORT_OR_CARE_CHILD` reduces isolation/emotional distress **gradually by `-0.06` to `-0.10` per tick** (scaled by parent's `care`/`teach` skill).
  - **No Magic Mute Button:** Comforting *cannot* instantly zero `distress` or stop crying if the baby is still hungry, injured, ill, freezing, or threatened—root-cause pressures continue pushing `distress` back up until the parent actually feeds, shelters, tends wounds, or defends the child.
  - Inside the Godot 4.7.2 Reality Bubble, `crying == True` activates the `InfantTears.tscn` particle emitter on the `Head` bone, plays `cry_distress` animation, and triggers subtle crying SFX so God can notice neglected or distressed children.

### 4.3 Dragon Metamorphosis State (`HUMANOID_DRAGON` $\leftrightarrow$ `TRUE_DRAGON`)
For `race == "DRAGON"` agents (`stage in {"ADULT", "ELDER"}`):
- **Default State (`HUMANOID_DRAGON`):** Normal humanoid scale (`1.05x`), low stamina burn, safe for peaceful sanctuary life and visiting Neutral Free Cities or WTC markets without triggering panic.
- **Transformation to `TRUE_DRAGON`:** Triggered when intentionally provoked (damaged, kin harmed, sanctuary border trespassed), during long-range aerial flight, or by rare aggressive outlier traits. Grants massive combat power and aerial speed, emits a `fear`/`awe` aura within `40m` to non-dragons, drains stamina continuously (`1.8x`), and sets the `dragon_true_form` bit in Python's binary WebSocket frame so Godot executes a zero-stutter node visibility toggle + `MetamorphosisBurst.tscn`.
- **Reversion:** Automatically reverts to `HUMANOID_DRAGON` once threat clears for `30` ticks or stamina drops below `15%`.

---

## 5. Developmental Stage Gates, Seasons & Autonomous Naming
### 5.1 Race-Scaled Stage Gates & Godot Bone Scaling
1 Game Day = `REAL_SECONDS_PER_GAME_DAY` (default `5400`s = 1.5 real hrs, tunable `3600–7200`s). Stage age thresholds scale by `L = RaceProfile.lifespan_multiplier` (`HUMAN 1.0x`, `BEASTHUMAN 1.0–1.5x`, `DEMON 2.8x`, `ELF 3.0x`, `DRAGON 6.0x`):

| Stage | Min Age (Game Days) | Base Max Health (× Race Mult) | Godot Height Scale (× Race Scale) | Sensory Radius | Promotion Threshold (`WorldGoddessCritic` `STAGE_UP`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `INFANT` | `0` | `40` | `0.45x` (`1.25x` head ratio) | `12m` | `age_days >= 2 * L`, `walk >= 0.35`, `self_care >= 0.35` |
| `CHILD` | `2 * L` | `70` | `0.75x` | `18m` | `age_days >= 6 * L`, `avg(walk, self_care, forage) >= 0.55` |
| `ADULT` | `6 * L` | `100` | `1.00x` | `24m` | `age_days >= 24 * L` (eligible for `ELDER`) |
| `ELDER` | `24 * L` | `75` | `0.94x` (+ spine slouch & silver hair) | `20m` | Natural vitality decay |

### 5.2 Four-Channel Learning (`sim_core/neural/social_learning.py`)
1. **Parental Care & Teaching:** Nearby parent/caretaker (`dist <= 6m`) boosts child skill by `+0.04 * (1 + parent.skills["teach"])`.
2. **Peer Observation:** Observing a trusted neighbor (`trust > 0.2`) succeed grants `+0.015 * trust * plasticity(stage)` (capped at peer's mastery).
3. **World Library Consultation:** Reading an Elder-approved `WorldLibraryEntry` at a Library grants a one-time `+0.08` boost (up to `0.60`).
4. **Cultural Tradition Transmission:** Infants and children adopt local settlement traditions observed during trigger events, storing `tradition_id` in their personal custom set.

### 5.3 Autonomous Naming & Dynasties (`sim_core/society/naming.py`)
- **Birth Naming:** On `BIRTH`, parents generate a culturally and racially flavored given name via a deterministic phoneme/syllable generator seeded by **`(race, sub_lineage, gender, culture/religion)`** plus an inherited **family/dynasty surname** (e.g., `Mira Thornwood`, `Aelarion Silverleaf`, `Ignis Ashwing`, `Torin Ironbeard`).
- **Self-Naming & Epithets:** Upon reaching `ADULT`, an agent may keep its birth name, adopt a self-chosen `display_name` (`SELF_RENAME`), or earn an epithet from notable life deeds (e.g., `Kaelen Ironhand`, `Aldric the Chronicler`). Internal keys always use immutable `agent_id`.

### 5.4 4-Season Scarcity Cycle (`sim_core/society/seasons.py`)
Each season lasts **`7` Game Days** (`1` Year = `28` Game Days), continuously updating Godot's `Sky3D v2.1` and global `season_progress` shader uniform:
- **Spring:** Hunger `1.0x`, wild food regen `1.2x`.
- **Summer:** Hunger `1.0x`, wild food regen `1.0x`, peak construction/trade.
- **Autumn:** Harvest surplus (`1.3x` crop yield).
- **Winter:** Hunger/exposure decay **`1.6x`** (unsheltered infants **`2.2x`**, reduced by `RaceProfile.winter_resistance`), wild food regen **`0.4x`** (-60%), elevated `illness` risk.

---

## 6. Birth Imprinting, Opposite-Gender Breeding Crossover & Permanent Mortality
### 6.1 Breeding Eligibility, Genetic Crossover & Cultural Imprinting
Two living `ADULT` agents $P_1, P_2$ may initiate breeding when **all** hold and `WorldGoddessCritic` approves `BIRTH`:
- **Strict Binary Gender Rule:** `P1.gender != P2.gender` (strictly one `BOY` and one `GIRL`).
- **Cross-Species & Dragon Rule:** All 5 races may mate with each other (Dragons must be in `HUMANOID_DRAGON` form when mating with non-dragons). Same-race pairings conceive at `100%`; cross-species pairings (`P1.race != P2.race`) roll **`50%` conception** (`CONCEPTION` commit).
- **Gestation & Delivery:** On conception, the female (`GIRL`) enters pregnancy for `mother.race.gestation_days` (`1.2` to `7.0` game days, `1.15x` hunger drain, `0.90x` speed). On delivery, cross-species births roll **`60%` survival** (stillbirths log `BIRTH_COMPLICATION` with zero tensor slot allocated); surviving mixed-race newborns start with `patron_godmother_slot = None` until their **Age-10 Patronage Choice**.
- **Biological & Social Readiness:** Proximity `<= 5m`, disjoint `parent_ids`, `health >= 70%` of `max_health`, `hunger >= 60`, `breeding_cooldown == 0` (scaled by `RaceProfile.breeding_cooldown_mult`), mutual `affinity >= 0.6`, and `trust >= 0.5`.
- **Offspring Generation:**
  1. Allocate a free slot `c` (growing tensor slabs by `2,048` if full).
  2. Assign `gender` via 50/50 RNG roll (`"BOY"` or `"GIRL"`), inherit `race` (and for `BEASTHUMAN`, randomly inherit one parent's `sub_lineage`), and inherit blended parent HSV skin/fur/scale/eye palette (`±8%` mutation).
  3. Blend `BatchedAgentSelfNet` weights with Bernoulli(0.5) crossover + $\mathcal{N}(0, 0.03)$ mutation; set `H[c] = 0`.
  4. Blend the 6 traits with $\mathcal{N}(0, 0.08)$ mutation, then apply **Cultural & Religious Birth Imprinting**:
     - If born inside a **Holy Nation** or devout settlement (or to high-devotion parents), apply an initial positive shift of **`+0.25` to `+0.45`** (clamped to `[-1, 1]`) to `traits["faith_devotion"]` and seed initial exposure to local settlement traditions.
     - Because mutation and lifelong backpropagation still operate, children born in holy nations are statistically more devout without losing free will.

### 6.2 Permanent Death, Slot Reclamation & Probate
When `health <= 0` (starvation, winter exposure, illness, injury/combat, old age, or `DIVINE_SMITE`):
1. Mark `alive[slot] = False` immediately; reclaim tensor slot after daily snapshot/logging.
2. If materialized in Godot's Reality Bubble, emit `POOL_RELEASE(reason="DEATH")`.
3. Execute `property.execute_probate(agent_id)` (direct heirs → extended kin → settlement treasury escheatment or wilderness `UNCLAIMED`).
4. Submit `CommitProposal(kind="DEATH", payload=...)` to **`WorldGoddessCritic`** and emit a local **Rumor Packet** to witnesses.