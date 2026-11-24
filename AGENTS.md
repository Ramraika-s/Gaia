# AGENTS.md — Persistent Unbounded Multi-Race AI Civilization Engine 

## 1. Mission & System Identity
You are building a **persistent, local-first, stylized anime-fantasy AI civilization simulation** with **no hard population cap**, scaling organically from initial founders to **10,000+ autonomous neural-network agents** across **5 distinct races** (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN` with `CAT_KIN`, `DWARF`, `WOLF_KIN`, and `BARBARIAN`/`BEAR_KIN` sub-lineages, and `DEMON`) and **2 biological genders** (`BOY` / `GIRL`).

Agents live across **Villages, Towns, Cities, Neutral Free Cities, States, and Nations/Kingdoms** with explicit `16×16m` parcel borders. They are born as vulnerable infants with autonomous cultural/racial naming and dynasties, experience root-cause distress/crying, injury, and illness, grow through race-scaled developmental stage gates, mate within or across species (cross-species mating carries a `50%` conception chance, `60%` birth survival chance, and mother-race gestation durations), learn from parents/peers/traditions/mistakes, buy and sell deeded land (with probate & escheatment), trade at a **World Trade Centre (WTC)** under real inflation, borrow from a strictly closed-loop **World Bank**, vote or serve under Kings and Popes, govern through a **Two-Book Governance model** (`world_library` for mortal/divine scholarship, and `divine_codex` for recorded divine decrees and live engine-parameter overrides), stand trial in a context-aware **Judiciary**, fight wars, and die permanently. Dragons live peacefully in `HUMANOID_DRAGON` form by default and metamorphose into `TRUE_DRAGON` form when provoked or flying. Demons embody fierce out-group temperaments with generational Dragon deterrence and abyssal craft/combat mastery.

The world is governed by a **Divine Family Hierarchy**:
1. **God (Admin / User):** Bestows custom names on the World Goddess and the 5 God-Mothers, enters the live **Godot 4.7.2** 3D world as a visible **God Avatar** (`is_god = true`) surrounded by a **60–120 agent 3D Reality Bubble** (plus an integrated **Orbital God Map** when zooming above `250m`), and oversees the planet via the Godot Divine HUD, Rich God Console, and persistent **God Ledger**. **Mortals cannot pray directly to God.**
2. **World Goddess (Wife of God):** Global critic (`WorldGoddessCritic`), mediator between her 5 daughters, owner of the **Self-Healing Error Solver**, adjudicator of Settlement Status Appeals, Neutral Free Cities, and Age-10 mixed-race patronage tie-breaks, and sole owner of the **all-or-nothing atomic end-of-day SHA-256 save** and daily **God Ledger** (`data/god_ledger/day_XXXXX.md`).
3. **5 Racial God-Mothers (Daughters of God & World Goddess):** One patron deity per race (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`), each with a unique personality vector, finite Divine Energy, restricted/restrained mortal interventions, Mortal Oracles/Champions (`1–3` per race), and **Inter-Sister 1-on-1 & 5-Sister Council dialogue**.

---

## 2. Target Hardware, OS, `uv` Toolchain & External Software Rules
All code, dependencies, tensor layouts, shaders, and Godot project settings must target:
- **Host Device:** HP EliteBook 845 G11 (AMD Ryzen 7 8840HS, Radeon 780M iGPU, 32GB DDR5 RAM, NVMe SSD)
- **Operating System:** Fedora Linux 45 (KDE Plasma on Wayland)
- **Mandatory `uv` Python Version Management:**
  - Fedora 45 ships a bleeding-edge system Python that is **too new** for reliable pre-built binary wheels (`torch`, `duckdb`, `pydantic`, `numpy`).
  - **NEVER use system `python3` or system `pip`.** Always use **`uv`** to fetch, pin, and run the most compatible Python release (default **`3.12`**, pinned in `.python-version` and `pyproject.toml`):
    ```bash
    uv python install 3.12
    uv python pin 3.12
    uv sync
    ```
  - All scripts, tests, linters, and benchmarks MUST run via `uv run ...`.
- **Interactive External Software & Asset Provisioning:**
  - Whenever host applications or large binary/asset dependencies are needed (**Godot 4.7.2**, **Blender**, **VRoid Studio** via Steam/Proton, **Terrain3D v1.1.0**, **Sky3D v2.1**, **VRM Importer & MToon v2.6.1**, or **Quaternius / KayKit / Kenney CC0 packs**), the agent must first detect what is already installed, search/locate exact compatible official versions/links, present the plan clearly to the user, and **request explicit user interaction/confirmation** before downloading binaries, extracting packs, or invoking `sudo dnf install ...`.
- **Resource & SSD Discipline:**
  - **Zero multi-billion-parameter LLMs per agent.** All unique `AgentSelfNet` brains + `GRUCell` working memory states are packed into contiguous 3D PyTorch tensors (`torch.bmm`), dynamically grown in **slabs of `2,048` slots** with **no hard agent cap**. At 10,000 agents, neural tensors consume **under 250 MB RAM** and execute a full forward pass in **~8–15 ms** on CPU.
  - **Soft RAM Watermark:** Monitor host memory via `psutil` once per civic tick; emit a `[RAM_WATERMARK]` alert at **75% host RAM** to the World Goddess, God Console, and God Ledger rather than crashing or hard-blocking births.
  - **Godot 780M Budget:** Target **60–120 pre-allocated, pooled rigged mortals** inside the `120–160m` 3D Reality Bubble (Forward+ MSAA 2x, 2048px shadow atlas; or Mobile renderer for locked 60 FPS at 150+ visible agents), `UPDATE_ONCE` on all 3D SubViewports, and 1-draw-call `MultiMeshInstance3D` for the 10,000+ Orbital God Map.
  - **Pure End-of-Day SSD Protection Rule:** Zero per-tick disk writes, zero mid-day flushes, and **no 15-minute crash journal**. All live simulation state, prayers, sisterly dialogues, and verdicts stay strictly in RAM during the 1–2 real-hour game day, flushing to disk **only at the end of each game day** (or clean shutdown) via an atomic all-or-nothing commit executed by the **World Goddess**.

---

## 3. Non-Negotiable Architectural Invariants
Do **not** violate these rules in any module or refactor:

1. **Unbounded Population + Multi-Tier Cognitive LOD:**
   - Never enforce a fixed `MAX_AGENTS` ceiling. Reallocate contiguous neural and spatial slabs in chunks of `2,048` slots (`torch.cat` / `np.concatenate`) whenever `free_slots` is empty.
   - Use **Multi-Tier Cognitive LOD**: Tier 0 (Reality Bubble) steps at `2 Hz`, Tier 1 (distant awake) at `1 Hz`, Tier 2 (distant sleeping/sheltered idle) at `0.25 Hz` (waking immediately on threat/distress/event).
2. **Python Core is the Single Source of Truth (Godot NEVER Writes to SQLite):**
   - Godot 4.7.2 is strictly the 3D/Orbital viewport, terrain renderer, and interactive God UI. **Godot must NEVER open or write directly to `data/civilization.db`.**
   - Every in-world God edit (e.g., saving a World Library book in Godot's 2D `TextEdit` modal, freezing WTC, or issuing decrees) sends a JSON event over WebSocket (`ws://127.0.0.1:8765`) to Python, which mutates RAM immediately (`bypass_god_check=True`) and commits atomically at end-of-day.
   - Python loads an exported `data/world_heightmap.npy` (from Terrain3D) for $O(1)$ elevation lookups so distant agents respect mountains, valleys, and Dragon crags.
3. **1–2 Real Hours = 1 Game Day + Atomic End-of-Day Two-Phase Commit:**
   - Default `REAL_SECONDS_PER_GAME_DAY = 5400`s (1.5 real hours, tunable `3600–7200`s), synced to Godot's `Sky3D v2.1` time-of-day hook. Support `speed 1x..60x` in the God Console for headless fast-forwarding.
   - At the end of each game day (or clean shutdown), the **World Goddess** executes an **all-or-nothing atomic commit**: single SQLite `BEGIN IMMEDIATE ... COMMIT` (full `ROLLBACK` on any error) + `day_XXXXX.pt` + `day_XXXXX.db` + `data/god_ledger/day_XXXXX.md` + SHA-256 checksums + `manifest.json` written last.
   - On startup, verify SHA-256 hashes against `manifest.json`; if the latest day is incomplete or corrupted, automatically rewind to the last `VERIFIED` daily snapshot.
4. **Self-Healing Error Solver (`sim_core/resilience/healer.py`):**
   - Wrap every tick phase, neural batch, double-entry transfer, WebSocket frame, and end-of-day commit in structured `try/except` boundaries routed to `ErrorHealer`.
   - Auto-heal isolated faults (`NaN`/`Inf` tensor slot restore, double-entry rollback, out-of-bounds coord clamp, WebSocket reconnect, single-agent quarantine).
   - **Escalation Guard:** If the exact same `fault_class` occurs **more than 5 times in one game day**, stop silently patching it, pause the affected subsystem, and log a `[CRITICAL]` alert to the World Goddess, Godot HUD/CLI (if active), and God Ledger.
5. **Divine Hierarchy, Prayer Routing, Mixed-Race Age-10 Choice & God Ledger:**
   - **Mortals cannot pray directly to God.** Mortals pray only to their **Racial God-Mother** or to the **World Goddess**.
   - **Mixed-Race Patronage Rule:** Cross-species children start uncommitted (`patron_godmother_slot = None`) until **biological age 10** (`3.33 * L` game days), when they choose between their two parental God-Mothers; non-choice auto-allocates to the higher-affinity God-Mother, and exact ties escalate to the **World Goddess** to decide.
   - **God** receives messages *only* from the **World Goddess** and the **5 Racial God-Mothers** (escalated prayers, congregational altar reports led by a **Prayer Head**, Inter-Sister Council logs, tie-break decrees, and healer alerts).
   - `GodPresenceTracker` streams messages in real time when God is active (Godot HUD / CLI), or buffers them strictly in RAM and flushes them atomically via the World Goddess into `data/god_ledger/day_XXXXX.md` (and `latest.md`) at end-of-day when away.
   - Racial God-Mothers obey finite **Divine Energy**, cooldowns, personality-driven **restraint**, and the **Non-Aggression Covenant** (preventing direct smiting of rival civilians and exposing the **Mortal Dependency Trap**).
6. **Strict RBAC, Two-Book Governance (`world_library` + `divine_codex`) & Bordered Polities:**
   - Agents and subsystems **never** write directly to SQLite. All permanent mutations pass through `WorldGoddessCritic` as a `CommitProposal` and emit a `CriticVerdict(status="SUCCESS"|"FAILURE", reason=...)` back to the actor.
   - **Two-Book Governance Architecture:**
     - **World Library (`world_library`) — Read Access: Everyone:**
       - **God (Admin):** Direct edit anytime (`bypass_god_check=True`).
       - **World Goddess:** May edit directly with **at least 1 of the 5 Daughters** (`>= 1`) voting `APPROVE`.
       - **5 Daughters (God-Mothers) Alone:** May edit without the World Goddess if **`> 50%`** (**at least 3 of 5**, `>= 3/5`) vote `APPROVE`.
       - **Mortals:**
         1. Must first pass **`> 50%`** of the Mortal Council of Appointed Elders (`approvals * 2 > total_appointed_elders`, max 2 Elders per Nation).
         2. Passed mortal proposals are routed to the **5 Racial God-Mothers**:
            - If **0** God-Mothers approve within **30 game days**, the proposal **auto-expires** (`EXPIRED`).
            - Once **`>= 1`** God-Mother approves, it enters a **1-game-day objection window**.
            - If **`> 50%` (`>= 3/5`)** of God-Mothers object before the 1-day window closes, it is **blocked** (`BLOCKED_BY_DAUGHTERS`) and may be appealed to the **World Goddess** or **God** for final judgment.
            - Otherwise, once the 1-day window elapses with `< 3` objections, it **passes and commits** to `world_library`.
     - **Divine Rules Book (`divine_codex`) — Read Access: Everyone:**
       - Stores both permanent recorded divine laws/decrees (persisted in SQLite, logged to the God Ledger, referenced by Sister Councils) **and** dynamic live engine-parameter overrides (e.g., Non-Aggression Covenant penalties, Divine Truce duration, intervention cooldowns).
       - **Option B (Split Write Authority — Maximum Security, No Parameter Bounds on Divine Rules):**
         - **God (Admin):** Sole unrestricted direct write access (`bypass_god_check=True`) for both text decrees and unrestricted live engine-parameter overrides.
         - **World Goddess + `> 50%` (`>= 3/5`) Daughters:** May commit **non-mechanical text decrees** directly to `divine_codex`.
         - **Unrestricted Engine-Parameter Overrides & Rule Appeals:** Neither the World Goddess nor the Daughters may apply parameter overrides directly. Instead, either the **World Goddess (alone)** OR **all 5 Daughters unanimously (`5/5`)** may submit a `DIVINE_CODEX_PROPOSAL` / appeal to **God (Admin)** (routed through the God Ledger / Divine HUD), and only **God** can approve and apply it.
         - **5 Daughters Alone (< 5/5, or without Goddess on text decrees) & All Mortals:** Strictly blocked (`FAILURE`).
   - **Settlement Status Appeals & Explicit Borders:** Upgrading a settlement's tier (`VILLAGE` → `TOWN` → `CITY` → `STATE` → `NATION`) or requesting **Neutral Free City** status requires a formal `SETTLEMENT_APPEAL` approved by the World Goddess. Every polity owns **explicit, non-overlapping `16×16m` chunk-parcel borders**.
   - Use **SQLite WAL** for atomic daily commits and **DuckDB (read-only attach)** for historical analytics. Never introduce PostgreSQL, MySQL, or MongoDB daemons.
7. **5 Races, 2 Genders, Cross-Species Pregnancy, Batched Tensor Brains & Realistic Biology:**
   - Strictly **2 biological genders (`BOY` / `GIRL`)**. Mating requires opposite genders (`P1.gender != P2.gender`). Different species may mate (Dragons must be in `HUMANOID_DRAGON` form) with **`50%` conception probability**, **`60%` offspring birth survival** (stillbirth logs `BIRTH_COMPLICATION` with zero tensor slot allocated), and **mother-race gestation duration** (`1.2` to `7.0` game days).
   - Demons (`DEMON`) are a unified race without sub-lineages, native to volcanic/ashland crags with high combat/magic aptitude, lifespan multiplier `2.8x`, gestation `4.0` days, winter resistance `1.50x`, an emergent out-group aggression prior (with per-agent Gaussian variation/mutation), learned generational Dragon deterrence caution (refraining from unprovoked attacks on Dragons), and elevated baseline reverence for `gm_demon`.
   - Never loop over agents in Python to run individual PyTorch networks. Use contiguous `(C, ...)` slab-grown `torch.bmm` + `GRUCell` tensors with `RaceProfile` multipliers. `SharedSkillNet` enforces hard stage masking; `BatchedAgentSelfNet` modulates preferences/risk clamped under critical health/hunger (`g_survival = 0.25`).
   - Infants experience root-cause `distress` (hunger, injury/illness, winter cold, threat, caretaker absence) and cry when `distress >= 0.45`. Parents comfort them **gradually** (`COMFORT_OR_CARE_CHILD`); zero magic mute buttons while root causes persist.
   - Agents receive autonomous culturally/racially flavored birth names + family dynasties, and may self-name or earn epithets upon adulthood. Children born in Holy Nations receive realistic birth imprinting on `faith_devotion`. Prayer faith gain varies by intent, and prolonged inactivity decays affinity gradually.
8. **Closed-Loop Double-Entry Economy, Real Inflation & No Auto-Evil:**
   - Never mint credits out of thin air. The **World Bank** is the sole currency issuer. Every transfer—including parent-to-child allowances—is a strict **double-entry debit/credit** that fails if `sender.credits < amount`. Prices clear dynamically at the **WTC** based on supply/demand and circulating money supply ($M$) vs. real output ($Q$).
   - Never create a global `good_vs_evil` scalar. Every combat harm event carries immutable `CombatContext` (`SELF_DEFENSE`, `DEFENDING_KIN_OR_TOWN`, `ACTIVE_WAR`, `UNPROVOKED_ATTACK`). Information spreads physically via **Rumor Packets** (zero telepathy).
9. **Headless-First Testability:**
   - The Python simulation core (`sim_core/`) must pass all unit tests, double-entry conservation checks, atomic corruption-rewind tests, and a **1,500+ agent 5-race headless soak test** via `MockWorldAdapter` before attaching the Godot 4.7.2 client.

---

## 4. Repository Layout
```text
.
├── AGENTS.md                                      # Master agent instructions & architecture rules (this file)
├── .python-version                                # Pinned via `uv python pin 3.12`
├── pyproject.toml                                 # Managed exclusively via `uv`
├── uv.lock
├── docs/
│   ├── INDEX.md                                       # Master documentation directory & architecture index
│   ├── architecture/
│   │   ├── ARCHITECTURE.md                            # Topology, LOD, WebSocket bridge, atomic 2PC, healer
│   │   ├── GODOT_CLIENT_AND_ASSETS_SPEC.md            # Godot 4.7.2, Terrain3D, Sky3D, VRoid, Quaternius/KayKit
│   │   ├── WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md      # Concentric 8kmx8km 4-ring world, Acropolis, 5 cities
│   │   ├── HYBRID_COGNITIVE_AND_LLM_SPEC.md           # 4-Pillar Hybrid Cognitive Core, Speech Acts, local LLM
│   │   ├── ECONOMY_HOUSING_AND_GEAR_SPEC.md           # Closed-loop economy, housing market & gear specs
│   │   └── WEBSOCKET_PROTOCOL_SPEC.md                 # Binary PackedFloat32Array & JSON frame contracts
│   ├── simulation/
│   │   ├── NEURAL_AND_LIFECYCLE_SPEC.md               # Slab-grown torch.bmm + GRU, stages, crying, seasons
│   │   ├── RACES_AND_BIOLOGY_SPEC.md                  # 5 races, 2 genders, cross-species pregnancy, Dragon morph
│   │   ├── DIVINE_HIERARCHY_SPEC.md                   # God -> World Goddess -> 5 God-Mothers, Age-10 choice, councils
│   │   └── SOCIETY_AND_GOVERNANCE_SPEC.md             # Economy, WTC inflation, borders, Elder Library, Judiciary
│   ├── data/
│   │   └── DATA_SCHEMA_AND_WORLD_GODDESS.md           # Pydantic v2 schemas, SQLite WAL DDL, DuckDB, validation
│   ├── guides/
│   │   └── PLAYER_AND_OPERATOR_GUIDE.md               # Controls, CLI commands, UI modals & author workflows
│   └── roadmap/
│       └── IMPLEMENTATION_ROADMAP.md                  # Phased build order, Sprints 0-6 milestones & future ideas
├── knowledge_foundry/                                 # Self-contained lore & book authoring repository
│   ├── AGENTS.md                                      # Knowledge authoring invariants & rules
│   ├── DEDUPE_AND_REVIEW_PLAYBOOK.md                  # 3-Stage deduplication & audit verification guide
│   ├── SCHEMA_SPEC.md                                 # KnowledgePack & KnowledgeEntry schema specification
│   └── subjects/                                      # 10 canonical subject reference documents
├── scripts/
│   ├── celestial_ingest.py                            # Sandboxed celestial lore harvester & ingestion CLI
│   ├── generate_world_heightmap.py                    # 8km x 8km 1024x1024 heightmap generator
│   ├── interactive_toolchain_setup.py                 # Interactive host toolchain & CC0 pack checker
│   ├── knowledge_merge.py                             # Atomic World Library merge CLI with deduplication
│   ├── knowledge_review.py                            # 3-Stage pre-merge review CLI for staged packs
│   ├── launch_gaia.py                                 # One-command simulator & Godot client launcher
│   ├── setup_uv_env.sh                                # Pins compatible Python via uv & syncs dependencies
│   ├── unpack_and_import_assets.py                    # Asset extractor and importer utility
│   └── verify_live_qwen.py                            # Live smoke test for Qwen3.5-4B via llama-server
├── sim_core/
│   ├── __init__.py
│   ├── config.py                                      # Master constants, pacing, LOD tiers, 8km world bounds
│   ├── schemas.py                                     # Pydantic v2 domain, race, divine, appeal & IPC contracts
│   ├── engine.py                                      # Main tick loop, LOD scheduler, Reality Bubble, day-end hook
│   ├── lifecycle.py                                   # Aging, stage gates, pregnancy, crying, death
│   ├── races.py                                       # RaceProfile registry (5 races), Dragon morph controller
│   ├── brains/
│   │   ├── action_bridge.py                           # CognitiveActionExecutor bridging neural logits to world actions
│   │   ├── consolidation.py                           # Sleep-cycle consolidation & stability gate
│   │   ├── hierarchical_brain.py                      # 3-Tier hierarchical brain composition engine
│   │   ├── memory_rag.py                              # Grounded RAG index with strict known_books asymmetry
│   │   ├── personality.py                             # 10-D personality vector & dynamic mood states
│   │   ├── profession_nets.py                         # ProfessionNetRegistry (10 professions Lv. 1-10)
│   │   └── shared_living_net.py                       # SharedLivingNet universal survival/reflex MLP
│   ├── bridge/
│   │   ├── godot_ws_bridge.py                         # WebSocket server bridge (ws://127.0.0.1:8765)
│   │   └── protocol.py                                # Binary PackedFloat32Array & JSON frame contracts
│   ├── divine/
│   │   ├── autonomy.py                                # Autonomous Divine Agenda Engine (6 deities)
│   │   ├── god_ledger.py                              # GodPresenceTracker, salience grouping, daily .md ledger
│   │   ├── hierarchy.py                               # World Goddess + 5 God-Mothers, traits, Oracles
│   │   ├── llm_brain.py                               # Async llama.cpp client & grounded deterministic fallback
│   │   └── sister_council.py                          # 1-on-1 & 5-sister council dialogue, Divine Truces
│   ├── god_console/
│   │   └── cli.py                                     # Interactive Rich God CLI (inspection, intervention, rewind)
│   ├── knowledge/
│   │   ├── db_loader.py                               # Atomic database loader & known books indexer
│   │   ├── dedupe.py                                  # 3-Stage cascaded deduplication engine
│   │   └── schema.py                                  # KnowledgePack Pydantic models & validation rules
│   ├── neural/
│   │   ├── batched_self_net.py                        # Unbounded 2048-slab torch.bmm + GRUCell working memory
│   │   ├── shared_net.py                              # SharedSkillNet baseline physical network
│   │   ├── social_learning.py                         # Caregiving, peer observation, traditions
│   │   └── trainer.py                                 # Batched rollout buffers, intrinsic curiosity, plasticity
│   ├── persistence/
│   │   ├── checkpoints.py                             # Atomic Two-Phase Commit (SHA-256 manifest) + rewind
│   │   ├── db.py                                      # SQLite WAL atomic end-of-day writer + DuckDB analytics
│   │   ├── state_serializer.py                        # Dedicated daily SQL deltas & checkpoint state serializer
│   │   └── world_goddess.py                           # WorldGoddessCritic RBAC/validation matrix & verdicts
│   ├── resilience/
│   │   └── healer.py                                  # Self-Healing Error Solver + 5-faults/day escalation
│   ├── society/
│   │   ├── borders.py                                 # Explicit non-overlapping 16x16m chunk borders & appeals
│   │   ├── economy.py                                 # Double-entry closed-loop credits & World Bank
│   │   ├── gear_economy.py                            # Crafted outfits, accessories, tools/weapons economy
│   │   ├── housing_market.py                          # Autonomous housing market, tier upgrades, probate
│   │   ├── judiciary.py                               # Context-aware judicial rulings & criminal records
│   │   ├── library.py                                 # Two-Book Governance (world_library + divine_codex)
│   │   ├── morality.py                                # CombatContext tagging & per-faction reputation
│   │   ├── naming.py                                  # Autonomous cultural naming, dynasties, epithets
│   │   ├── politics.py                                # Settlement tiers, Neutral Free Cities, Kings, Wars
│   │   ├── property.py                                # 16x16m deeds, buy/sell/rent, probate & escheatment
│   │   ├── religion.py                                # Faiths, birth imprinting, intent-scaled prayer, altars
│   │   ├── rumors.py                                  # Physical Rumor Packet propagation (8m acoustic range)
│   │   ├── seasons.py                                 # 4-Season cycle & environmental scarcity multipliers
│   │   ├── speech_acts.py                             # 8 Semantic Speech Acts engine & diegetic utterances
│   │   ├── traditions.py                              # Emergent cultural traditions, rituals, taboos
│   │   └── wtc_market.py                              # WTC order-book exchange & Fisher CPI inflation engine
│   ├── spatial/
│   │   ├── hash_grid.py                               # NumPy O(1) spatial hash grid & chunk parcel index
│   │   ├── heightmap.py                               # 8km x 8km world_heightmap.npy O(1) elevation sampler
│   │   └── navigation.py                              # Vectorized pathfinding & terrain slope traversal
│   ├── tools/
│   │   ├── bench_tensors.py                           # 10,000-agent slab-grown forward-pass latency benchmark
│   │   └── soak_test.py                               # 1,500-agent 5-race soak & atomic corruption rewind test
│   └── world/
│       ├── city_layout.py                             # 5 Ring 1 Gated Cities, God-Mother Palaces, street grid
│       ├── palace_security.py                         # Ring 0 Acropolis, Twin Dragons, 24 Palace Knights
│       └── regional_weather.py                        # Dynamic regional weather cells & microclimates
├── godot_client/                                      # Godot 4.7.2 stylized anime-fantasy 3D client
│   ├── project.godot
│   ├── addons/                                        # Terrain3D v1.1.0, Sky3D v2.1, VRM Importer & MToon v2.6.1
│   ├── assets/                                        # 7 VRoid deities, 6 Quaternius rigs + Demon rig, props, audio
│   ├── scenes/                                        # MainWorld, RealityBubble, Landmarks, Buildings, UI Modals
│   ├── shaders/                                       # TerrainBiome, WaterStylized, GrassSway, EmissiveWindow
│   └── scripts/                                       # Controllers, UiStateManager, animators, and UI modal scripts
├── tests/                                             # 21 domain test files (191 passing tests under pytest)
│   ├── conftest.py                                    # Shared isolated fixtures & typed domain factories
│   ├── brains/                                        # Cognitive architecture, batched neural slabs, RAG & LLM
│   │   ├── test_batched_neural_slab.py
│   │   ├── test_consolidation_and_rag.py
│   │   ├── test_divine_ai_and_llm.py
│   │   └── test_hierarchical_brain_and_actions.py
│   ├── bridge/                                        # WebSocket protocol v4.0.0, dialogue & God Console CLI
│   │   ├── test_god_console_cli.py
│   │   └── test_ws_protocol_and_dialogue.py
│   ├── core/                                          # Schemas, 5-race biology, lifecycle, distress & resilience
│   │   ├── test_healer_resilience.py
│   │   ├── test_races_and_lifecycle.py
│   │   └── test_schemas_and_config.py
│   ├── economy/                                       # Double-entry banking, WTC, probate & gear market
│   │   ├── test_banking_and_wtc.py
│   │   ├── test_housing_frontier_and_gear.py
│   │   └── test_property_and_probate.py
│   ├── hygiene/                                       # Asset manifest parity, orphan cleanup & doc link integrity
│   │   └── test_repo_assets_and_docs.py
│   ├── persistence/                                   # SQLite WAL migrations, atomic 2PC, rewind & Two-Book governance
│   │   ├── test_db_migrations_and_atomic_checkpoints.py
│   │   ├── test_knowledge_foundry_and_cli.py
│   │   ├── test_restore_rewind_and_launcher.py
│   │   └── test_two_book_governance_and_world_goddess.py
│   └── world/                                         # Heightmap parity, weather, cities, security & polities
│       ├── test_cities_gates_and_buildings.py
│       ├── test_heightmap_and_weather.py
│       ├── test_palace_security_and_navigation.py
│       └── test_politics_borders_religion_and_speech.py
└── data/                                              # Git-ignored runtime state (DB, checkpoints, god_ledger)
```

---

## 5. Tech Stack & Coding Standards
- **Python Environment (`uv` Managed, Python `3.12`):** `torch` (CPU), `numpy`, `psutil`, `pydantic>=2.7`, `websockets`, `aiosqlite`, `duckdb`, `rich`, `pytest`, `pytest-asyncio`, `ruff`.
- **3D Client (Godot 4.7.2):** **Godot 4.7.2** (Forward+ Vulkan / Mobile on Fedora 45 Wayland), `Terrain3D v1.1.0`, `Sky3D v2.1`, `VRM Importer & MToon Shader v2.6.1`, `VRoid Studio` (Steam/Proton, built-in polygon reduction), `Blender` (bone-parenting props only—**never** Decimate on rigged VRMs), `Quaternius` + `KayKit` + `Kenney` CC0 packs.
- **IPC Protocol:** Native Godot `WebSocketPeer` ↔ Python `websockets` on `ws://127.0.0.1:8765` (JSON for discrete events/UI/prayers; raw binary `PackedFloat32Array` frames for bulk 10,000+ agent coordinates/states at 24 bytes/agent).
- **Code Style:** Full Python type hints, Pydantic v2 validation, vectorized NumPy/PyTorch ops for all per-agent hot paths, deterministic seedable RNG (`sim_core/config.py`), structured logging with `agent_id` and `tick`, and zero bare `except:` blocks (always route through `ErrorHealer`).

---

## 6. Verification Commands (Always via `uv run`)
Before marking any task or milestone complete, run:
```bash
uv run ruff check sim_core tests scripts
uv run pytest --tb=short -q
# 1,500-agent 5-race headless soak test + atomic end-of-day save & corruption rewind verification
uv run python -m sim_core.tools.soak_test --ticks 600 --agents 1500 --verify-atomic-rewind
# 10,000-agent slab-grown batched forward-pass latency benchmark (target: < 25ms/tick)
uv run python -m sim_core.tools.bench_tensors --agents 10000 --steps 50
```

---

## 7. Git Hygiene, Verification Protocol & Spec Compliance

1. **Standard Git Hygiene:**
   - Before starting and before signing off on any task, inspect `git status --short` and review `git diff` to confirm all changes are intentional, cleanly scoped, and free of leftover temporary or scratch files in the repository root.
   - If multi-agent or parallel sub-agent work is used, partition tasks across strictly disjoint file sets so agents never edit the same file concurrently.
2. **Read the Relevant Spec Under `docs/` First:**
   - Always inspect the canonical specification under `docs/` before modifying a subsystem (`ARCHITECTURE.md`, `GODOT_CLIENT_AND_ASSETS_SPEC.md`, `WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md`, `HYBRID_COGNITIVE_AND_LLM_SPEC.md`, `ECONOMY_HOUSING_AND_GEAR_SPEC.md`, `WEBSOCKET_PROTOCOL_SPEC.md`, `NEURAL_AND_LIFECYCLE_SPEC.md`, `RACES_AND_BIOLOGY_SPEC.md`, `DIVINE_HIERARCHY_SPEC.md`, `SOCIETY_AND_GOVERNANCE_SPEC.md`, `DATA_SCHEMA_AND_WORLD_GODDESS.md`).
3. **Follow `docs/roadmap/IMPLEMENTATION_ROADMAP.md` & Architectural Invariants:**
   - Ensure the headless Python core passes all unit, double-entry conservation, corruption-rewind, and 1,500-agent 5-race soak tests alongside any Godot 4.7.2 client work.
   - Never silently drop requirements. If a spec rule conflicts with a library limitation, document the fallback in code comments while keeping the architectural invariant intact.
4. **User-Confirmed External Downloads:**
   - Always request explicit user confirmation before downloading external software (`Godot 4.7.2`, `Blender`, `VRoid Studio`) or third-party asset packs.