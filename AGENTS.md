# AGENTS.md — Persistent Unbounded Multi-Race AI Civilization Engine 

## 1. Mission & System Identity
You are building a **persistent, local-first, stylized anime-fantasy AI civilization simulation** with **no hard population cap**, scaling organically from initial founders to **10,000+ autonomous neural-network agents** across **4 distinct races** (`HUMAN`, `ELF`, `DRAGON`, and `BEASTHUMAN` with `CAT_KIN`, `DWARF`, `WOLF_KIN`, and `BARBARIAN`/`BEAR_KIN` sub-lineages) and **2 biological genders** (`BOY` / `GIRL`).

Agents live across **Villages, Towns, Cities, Neutral Free Cities, States, and Nations/Kingdoms** with explicit `16×16m` parcel borders. They are born as vulnerable infants with autonomous cultural/racial naming and dynasties, experience root-cause distress/crying, injury, and illness, grow through race-scaled developmental stage gates, mate within or across species (cross-species mating carries a `50%` conception chance, `60%` birth survival chance, and mother-race gestation durations), learn from parents/peers/traditions/mistakes, buy and sell deeded land (with probate & escheatment), trade at a **World Trade Centre (WTC)** under real inflation, borrow from a strictly closed-loop **World Bank**, vote or serve under Kings and Popes, govern the **World Library** through a **>50% consensus Council of Appointed Elders (max 2 Elders per Nation)**, stand trial in a context-aware **Judiciary**, fight wars, and die permanently. Dragons live peacefully in `HUMANOID_DRAGON` form by default and metamorphose into `TRUE_DRAGON` form when provoked or flying.

The world is governed by a **Divine Family Hierarchy**:
1. **God (Admin / User):** Bestows custom names on the World Goddess and the 4 God-Mothers, enters the live **Godot 4.7.2** 3D world as a visible **God Avatar** (`is_god = true`) surrounded by a **60–120 agent 3D Reality Bubble** (plus an integrated **Orbital God Map** when zooming above `250m`), and oversees the planet via the Godot Divine HUD, Rich God Console, and persistent **God Ledger**. **Mortals cannot pray directly to God.**
2. **World Goddess (Wife of God):** Global critic (`WorldGoddessCritic`), mediator between her 4 daughters, owner of the **Self-Healing Error Solver**, adjudicator of Settlement Status Appeals, Neutral Free Cities, and Age-10 mixed-race patronage tie-breaks, and sole owner of the **all-or-nothing atomic end-of-day SHA-256 save** and daily **God Ledger** (`data/god_ledger/day_XXXXX.md`).
3. **4 Racial God-Mothers (Daughters of God & World Goddess):** One patron deity per race (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`), each with a unique personality vector, finite Divine Energy, restricted/restrained mortal interventions, Mortal Oracles/Champions (`1–3` per race), and **Inter-Sister 1-on-1 & 4-Sister Council dialogue**.

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
   - **God** receives messages *only* from the **World Goddess** and the **4 Racial God-Mothers** (escalated prayers, congregational altar reports led by a **Prayer Head**, Inter-Sister Council logs, tie-break decrees, and healer alerts).
   - `GodPresenceTracker` streams messages in real time when God is active (Godot HUD / CLI), or buffers them strictly in RAM and flushes them atomically via the World Goddess into `data/god_ledger/day_XXXXX.md` (and `latest.md`) at end-of-day when away.
   - Racial God-Mothers obey finite **Divine Energy**, cooldowns, personality-driven **restraint**, and the **Non-Aggression Covenant** (preventing direct smiting of rival civilians and exposing the **Mortal Dependency Trap**).
6. **Strict RBAC, World Library Elder Consensus & Bordered Polities:**
   - Agents and subsystems **never** write directly to SQLite. All permanent mutations pass through `WorldGoddessCritic` as a `CommitProposal` and emit a `CriticVerdict(status="SUCCESS"|"FAILURE", reason=...)` back to the actor.
   - **World Library Governance:** Random agents cannot edit World Library books. Publishing or modifying entries requires **> 50% consensus from the Council of Appointed Elders**, where **each Nation may appoint at most 2 Elders** (only `God` may bypass via `bypass_god_check=True`).
   - **Settlement Status Appeals & Explicit Borders:** Upgrading a settlement's tier (`VILLAGE` → `TOWN` → `CITY` → `STATE` → `NATION`) or requesting **Neutral Free City** status requires a formal `SETTLEMENT_APPEAL` approved by the World Goddess. Every polity owns **explicit, non-overlapping `16×16m` chunk-parcel borders**.
   - Use **SQLite WAL** for atomic daily commits and **DuckDB (read-only attach)** for historical analytics. Never introduce PostgreSQL, MySQL, or MongoDB daemons.
7. **4 Races, 2 Genders, Cross-Species Pregnancy, Batched Tensor Brains & Realistic Biology:**
   - Strictly **2 biological genders (`BOY` / `GIRL`)**. Mating requires opposite genders (`P1.gender != P2.gender`). Different species may mate (Dragons must be in `HUMANOID_DRAGON` form) with **`50%` conception probability**, **`60%` offspring birth survival** (stillbirth logs `BIRTH_COMPLICATION` with zero tensor slot allocated), and **mother-race gestation duration** (`1.2` to `7.0` game days).
   - Never loop over agents in Python to run individual PyTorch networks. Use contiguous `(C, ...)` slab-grown `torch.bmm` + `GRUCell` tensors with `RaceProfile` multipliers. `SharedSkillNet` enforces hard stage masking; `BatchedAgentSelfNet` modulates preferences/risk clamped under critical health/hunger (`g_survival = 0.25`).
   - Infants experience root-cause `distress` (hunger, injury/illness, winter cold, threat, caretaker absence) and cry when `distress >= 0.45`. Parents comfort them **gradually** (`COMFORT_OR_CARE_CHILD`); zero magic mute buttons while root causes persist.
   - Agents receive autonomous culturally/racially flavored birth names + family dynasties, and may self-name or earn epithets upon adulthood. Children born in Holy Nations receive realistic birth imprinting on `faith_devotion`. Prayer faith gain varies by intent, and prolonged inactivity decays affinity gradually.
8. **Closed-Loop Double-Entry Economy, Real Inflation & No Auto-Evil:**
   - Never mint credits out of thin air. The **World Bank** is the sole currency issuer. Every transfer—including parent-to-child allowances—is a strict **double-entry debit/credit** that fails if `sender.credits < amount`. Prices clear dynamically at the **WTC** based on supply/demand and circulating money supply ($M$) vs. real output ($Q$).
   - Never create a global `good_vs_evil` scalar. Every combat harm event carries immutable `CombatContext` (`SELF_DEFENSE`, `DEFENDING_KIN_OR_TOWN`, `ACTIVE_WAR`, `UNPROVOKED_ATTACK`). Information spreads physically via **Rumor Packets** (zero telepathy).
9. **Headless-First Testability:**
   - The Python simulation core (`sim_core/`) must pass all unit tests, double-entry conservation checks, atomic corruption-rewind tests, and a **1,500+ agent 4-race headless soak test** via `MockWorldAdapter` before attaching the Godot 4.7.2 client.

---

## 4. Repository Layout
```text
.
├── AGENTS.md                                      # Master agent instructions & QA protocol (this file)
├── .python-version                                # Pinned via `uv python pin 3.12`
├── pyproject.toml                                 # Managed exclusively via `uv`
├── uv.lock
├── .qa_loop/                                      # Git-ignored multi-agent QA orchestration state
│   ├── precautions.json                           # Shared guardrails (Main Agent write-only)
│   ├── file_locks.json                            # Strict mutual exclusion locks
│   ├── handoff_reports/                           # Sub-agent escalation reports
│   └── backups/                                   # Ephemeral SHA-256 atomic rollback snapshots
├── docs/
│   ├── architecture/
│   │   ├── ARCHITECTURE.md                        # Topology, LOD, WebSocket bridge, atomic 2PC, healer
│   │   └── GODOT_CLIENT_AND_ASSETS_SPEC.md        # Godot 4.7.2, Terrain3D, Sky3D, VRoid, Quaternius/KayKit
│   ├── simulation/
│   │   ├── NEURAL_AND_LIFECYCLE_SPEC.md           # Slab-grown torch.bmm + GRU, stages, crying, seasons
│   │   ├── RACES_AND_BIOLOGY_SPEC.md              # 4 races, 2 genders, cross-species pregnancy, Dragon morph
│   │   ├── DIVINE_HIERARCHY_SPEC.md               # God -> World Goddess -> 4 God-Mothers, Age-10 choice, councils
│   │   └── SOCIETY_AND_GOVERNANCE_SPEC.md         # Economy, WTC inflation, borders, Elder Library, Judiciary
│   ├── data/
│   │   └── DATA_SCHEMA_AND_WORLD_GODDESS.md       # Pydantic v2 schemas, SQLite WAL DDL, DuckDB, validation
│   └── roadmap/
│       └── IMPLEMENTATION_ROADMAP.md              # Phased build order (Phases 0-5), benchmarks & Godot slices
├── scripts/
│   ├── setup_uv_env.sh                            # Pins compatible Python via uv & syncs dependencies
│   └── interactive_toolchain_setup.py             # Checks/searches/installs Godot, Blender, VRoid & packs with user confirmation
├── sim_core/
│   ├── __init__.py
│   ├── config.py                  # Day pacing (3600–7200s), LOD tiers, slab size (2048), RNG
│   ├── schemas.py                 # Pydantic v2 domain, race, divine, appeal & IPC contracts
│   ├── engine.py                  # Main tick loop, LOD scheduler, Reality Bubble, day-end hook
│   ├── lifecycle.py               # Aging, stage gates, pregnancy, injury/illness, crying, death
│   ├── races.py                   # RaceProfile registry (HUMAN, ELF, DRAGON, BEASTHUMAN), Dragon morph
│   ├── resilience/
│   │   └── healer.py              # Self-Healing Error Solver + 5-fault/day [CRITICAL] escalation guard
│   ├── spatial/
│   │   ├── hash_grid.py           # NumPy O(1) spatial hash grid & 16x16m parcel border lookup
│   │   └── heightmap.py           # world_heightmap.npy loader & O(1) elevation/slope queries
│   ├── neural/
│   │   ├── shared_net.py          # SharedSkillNet (MLP + survival gate + stage masking)
│   │   ├── batched_self_net.py    # Unbounded 2048-slab torch.bmm + GRUCell working memory
│   │   ├── trainer.py             # Batched rollout buffers, intrinsic curiosity, plasticity backprop
│   │   └── social_learning.py     # Parental care/comforting, peer observation, library & traditions
│   ├── divine/
│   │   ├── hierarchy.py           # World Goddess + 4 Racial God-Mothers (names, traits, energy, Oracles)
│   │   ├── sister_council.py      # 1-on-1 & 4-sister council dialogue, Divine Truces, Goddess mediation
│   │   └── god_ledger.py          # GodPresenceTracker, prayer/altar salience grouping, daily .md ledger
│   ├── society/
│   │   ├── naming.py              # Racial/cultural phoneme birth names, dynasties, self-naming & epithets
│   │   ├── borders.py             # Explicit non-overlapping 16x16m borders & settlement/Free City appeals
│   │   ├── morality.py            # CombatContext tagging & per-faction/pairwise reputation
│   │   ├── rumors.py              # Physical Rumor Packet propagation & decay
│   │   ├── seasons.py             # 4-Season cycle & scarcity multipliers
│   │   ├── economy.py             # Double-entry closed-loop credits & World Bank (sole issuer)
│   │   ├── wtc_market.py          # World Trade Centre order-book exchange & M/Q inflation engine
│   │   ├── property.py            # 16x16m chunk parcels, buy/sell/rent, probate & escheatment
│   │   ├── politics.py            # Village->Town->City->State->Nation, Free Cities, Kings, Elections, Wars
│   │   ├── religion.py            # Faiths, birth imprinting, intent-scaled prayer, decay, Popes, altars
│   │   ├── judiciary.py           # Case filing, witness evidence, rulings, criminal records
│   │   ├── traditions.py          # Emergent Cultural Memes (triggers, rituals, taboos)
│   │   └── library.py             # World Library + Appointed Elders Council (max 2/nation, >50% vote)
│   ├── persistence/
│   │   ├── world_goddess.py       # WorldGoddessCritic RBAC/validation matrix + verdict feedback emitter
│   │   ├── db.py                  # SQLite WAL atomic end-of-day writer + DuckDB read-only analytics
│   │   └── checkpoints.py         # Atomic Two-Phase Commit (SHA-256 manifest) + corruption rewind
│   ├── bridge/
│   │   ├── base.py                # Abstract WorldAdapter interface
│   │   ├── mock_adapter.py        # Fast headless adapter for unit & multi-thousand soak tests
│   │   └── godot_ws_bridge.py     # WebSocket server (JSON events + binary PackedFloat32Array stream)
│   ├── god_console/
│   │   └── cli.py                 # Interactive Rich God CLI (inspect, intervene, speed, name deities, rewind)
│   └── tools/
│       ├── bench_tensors.py       # 10,000-agent slab-grown forward-pass & RAM benchmark
│       └── soak_test.py           # 1,500-agent 4-race soak + atomic corruption rewind verifier
├── godot_client/                  # Godot 4.7.2 stylized anime-fantasy 3D + Orbital Map client
│   ├── project.godot
│   ├── addons/                    # Terrain3D v1.1.0, Sky3D v2.1, VRM Importer & MToon v2.6.1
│   ├── assets/                    # 6 VRoid deities, 6 Quaternius/KayKit base rigs, modular buildings, VFX/SFX
│   ├── shaders/                   # Global toon/cel shader, season_progress uniform, mortal instance HSV shader
│   ├── scenes/                    # MainWorld, RealityBubblePool, OrbitalMap, Landmarks, GodAvatar, UI Modals
│   └── scripts/                   # ws_client.gd, bubble_manager.gd, dragon_morph.gd, divine_hud.gd, library_modal.gd
├── tests/
│   ├── conftest.py                # Shared local SQLite & WorldState fixtures
│   ├── test_schemas.py
│   ├── test_world_goddess_rbac_and_atomic_save.py
│   ├── test_healer_resilience.py
│   ├── test_batched_neural_unbounded.py
│   ├── test_races_gender_pregnancy_dragon_morph.py
│   ├── test_divine_hierarchy_patronage_and_councils.py
│   ├── test_lifecycle_crying_and_naming.py
│   ├── test_economy_double_entry_inflation.py
│   ├── test_politics_borders_library_religion.py
│   └── test_persistence_corruption_rewind.py
└── data/                          # Git-ignored runtime artifacts (DB, checkpoints, god_ledger, heightmap)
```

---

## 5. Tech Stack & Coding Standards
- **Python Environment (`uv` Managed, Python `3.12`):** `torch` (CPU), `numpy`, `psutil`, `pydantic>=2.7`, `websockets`, `aiosqlite`, `duckdb`, `rich`, `pytest`, `pytest-asyncio`, `ruff`.
- **3D Client (Phase 5):** **Godot 4.7.2** (Vulkan on Fedora 45 Wayland), `Terrain3D v1.1.0`, `Sky3D v2.1`, `VRM Importer & MToon Shader v2.6.1`, `VRoid Studio` (Steam/Proton, built-in polygon reduction), `Blender` (bone-parenting props only—**never** Decimate on rigged VRMs), `Quaternius` + `KayKit` + `Kenney` CC0 packs.
- **IPC Protocol:** Native Godot `WebSocketPeer` ↔ Python `websockets` on `ws://127.0.0.1:8765` (JSON for discrete events/UI/prayers; raw binary `PackedFloat32Array` frames for bulk 10,000+ agent coordinates/states).
- **Code Style:** Full Python type hints, Pydantic v2 validation, vectorized NumPy/PyTorch ops for all per-agent hot paths, deterministic seedable RNG (`sim_core/config.py`), structured logging with `agent_id` and `tick`, and zero bare `except:` blocks (always route through `ErrorHealer`).

---

## 6. Verification Commands (Always via `uv run`)
Before marking any task or milestone complete, run:
```bash
uv run ruff check sim_core tests
uv run pytest --tb=short -q
# 1,500-agent 4-race headless soak test + atomic end-of-day save & corruption rewind verification
uv run python -m sim_core.tools.soak_test --ticks 600 --agents 1500 --verify-atomic-rewind
# 10,000-agent slab-grown batched forward-pass latency benchmark (target: < 25ms/tick)
uv run python -m sim_core.tools.bench_tensors --agents 10000 --steps 50
```

---

## 7. Multi-Agent QA Execution Loop & Atomic Rollback Protocol (`.qa_loop/`)

All implementation work across Phases 0–5 MUST execute through this deterministic **Main Agent (Orchestrator) → Sub-Agent (Fresh Context)** quality loop so failed edits never leave half-broken code in the repository.

### 7.1 End-to-End Execution Flow
```text
[MAIN AGENT (Orchestrator)]
  │ 1. Verifies no leftover `.qa_loop/backups/<task_id>/` exists (crash recovery)
  │ 2. Partitions tasks by file ownership (strictly disjoint files)
  │ 3. Acquires locks in `file_locks.json` & updates `precautions.json`
  ▼
[SPAWN SUB-AGENT (Fresh Context)] ◄───────────────────────────────┐
  │                                                               │
  ├─► Step 1: Read `precautions.json` + Handoff Findings (if any) │
  ├─► Step 2: Plan & Self-Critique ("Think & Verify Plan")        │
  ├─► Step 3: Create SHA-256 backup snapshot in `.qa_loop/backups`│
  │                                                               │
  │   ┌──► [INNER LOOP: Max 3 Attempts] ──────────────────────┐   │
  │   │     4. Apply code edits to owned files                │   │
  │   │     5. Run targeted tests + linters/typechecks (`uv`) │   │
  │   │     6. Verify output against acceptance criteria      │   │
  │   │     7. If FAIL & attempt < 3:                         │   │
  │   │        Diagnose -> Re-plan -> Verify Plan -> Loop ────┘   │
  │   └───────────────────────────────────────────────────────┘   │
  │                                                               │
  ├─► IF PASS: Purge backup folder -> Release locks -> Report OK  │
  │                                                               │
  └─► IF FAIL (3/3):                                              │
        ├─► 8. ATOMIC TRANSACTION (All-or-Nothing):               │
        │      Validate SHA-256 -> Stage & fsync -> Atomic swap   │
        │      -> Verify restored hashes -> Atomic delete backup  │
        ├─► 9. Emit `handoff_report.json` & release locks         │
        └─► 10. Escalate clean codebase to Main Agent ────────────┤
                                                                  │
[MAIN AGENT ANALYZES FAILURE]                                     │
  │ • Detects repeated mistakes -> Appends rule to `precautions.json`
  │ • Kills old sub-agent context & spawns NEW sub-agent ─────────┘
```

### 7.2 Core Data Contracts (JSON Schemas)

#### A. `.qa_loop/precautions.json` (Shared Guardrails)
**Permissions:** Only the Main Agent has write access. Every Sub-Agent MUST read this file as its very first action before planning.
```json
{
  "global_rules": [
    "Never use system python3 or pip on Fedora 45; execute everything via `uv run` on pinned Python 3.12.",
    "Godot must NEVER open or write directly to `data/civilization.db`; route edits via Python WebSocket.",
    "Always run pytest with `uv run pytest --tb=short -q` to keep test logs compact."
  ],
  "anti_patterns_detected": [
    {
      "id": "ERR-001",
      "pattern": "Sub-agents repeatedly mocked database calls instead of using the local SQLite fixture.",
      "mandatory_fix": "Use the `db_session` fixture from `tests/conftest.py`.",
      "added_after_task": "task_01_run_1"
    }
  ],
  "environment_constraints": {
    "python_manager": "uv",
    "pinned_python": "3.12",
    "python_runner": "uv run pytest --tb=short -q",
    "linter": "uv run ruff check sim_core tests"
  }
}
```

#### B. `.qa_loop/file_locks.json` (Strict Mutual Exclusion)
**Permissions:** Managed atomically by the Main Agent so no two sub-agents can read or write the same file concurrently.
```json
{
  "active_locks": {
    "sim_core/persistence/world_goddess.py": {
      "owner_agent_id": "subagent_alpha_02",
      "task_id": "phase1_task_02",
      "mode": "EXCLUSIVE_RW",
      "acquired_at": "2026-11-21T05:25:00Z",
      "expires_at": "2026-11-21T05:35:00Z"
    }
  }
}
```

#### C. `.qa_loop/backups/<task_id>/manifest.json` (Backup Integrity & Atomic Rollback Contract)
**Permissions:** Written once by the Sub-Agent before Attempt 1. Used to verify bit-for-bit restoration before deleting backups.
```json
{
  "task_id": "phase1_task_02",
  "subagent_id": "subagent_alpha_01",
  "created_at": "2026-11-21T05:25:02Z",
  "files": {
    "sim_core/persistence/world_goddess.py": {
      "backup_rel_path": "sim_core/persistence/world_goddess.py.orig",
      "original_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  }
}
```

#### D. `.qa_loop/handoff_reports/<task_id>_<subagent_id>.json` (Sub-Agent → Main Agent Escalation)
Emitted only after the atomic rollback and backup purge have committed, proving the workspace is back to a clean baseline.
```json
{
  "task_id": "phase1_task_02",
  "subagent_id": "subagent_alpha_01",
  "status": "FAILED_MAX_RETRIES",
  "rollback_transaction": {
    "status": "COMMITTED",
    "files_restored": ["sim_core/persistence/world_goddess.py"],
    "checksums_verified": true,
    "backup_purged": true
  },
  "attempts_used": 3,
  "attempt_history": [
    {
      "attempt": 1,
      "hypothesis": "Validated Elder Council quorum against total_nations * 2.",
      "result": "FAILED",
      "error_signature": "AssertionError: Expected >50% of currently appointed elders, not max seats"
    },
    {
      "attempt": 2,
      "hypothesis": "Checked approvals >= total_appointed_elders / 2.",
      "result": "FAILED",
      "error_signature": "AssertionError: 2 of 4 votes must NOT pass strict >50% rule"
    },
    {
      "attempt": 3,
      "hypothesis": "Added bypass flag check before Elder vote tally.",
      "result": "FAILED",
      "error_signature": "Regression in test_unauthorized_library_edit_blocked"
    }
  ],
  "root_cause_analysis": "Strict majority requires integer `approvals * 2 > total_appointed_elders` and `bypass_god_check` must only accept verified God origin.",
  "recommended_next_strategy": "Use integer comparison `len(votes_approve) * 2 > len(living_appointed_elders)` and gate bypass strictly on `proposal.bypass_god_check`."
}
```

### 7.3 Step-by-Step Execution Protocol
- **Stage A — Main Agent Pre-Flight & Partitioning:**
  1. **Orphaned Transaction Sweep:** Before scheduling any task, check `.qa_loop/backups/`. If an incomplete backup directory exists from a crashed sub-agent, complete its atomic restore-and-purge transaction first.
  2. **File Ownership Partitioning:** Map every file each task will read or modify. Tasks with strictly disjoint file sets may run in parallel; tasks sharing even one file run sequentially.
  3. **Lock Acquisition:** Write exclusive lock entries into `file_locks.json` before spawning the sub-agent. Any tool-level `read_file` or `write_file` call checks `file_locks.json` first and immediately throws `LOCK_VIOLATION` if the agent ID does not match.
- **Stage B — Sub-Agent Internal Loop (Max 3 Iterations):**
  1. **Ingest Guardrails & History:** Read `.qa_loop/precautions.json` and any prior `handoff_report.json`.
  2. **Plan & Critical Verification Gate:** Formulate a step-by-step plan (files, logic, edge cases, verification tests) and self-critique against `precautions.json` and prior `attempt_history` so disproven hypotheses are never repeated.
  3. **Immutable SHA-256 Backup Snapshot (Before Attempt 1 Only):** Copy each target file to `.qa_loop/backups/<task_id>/<path>.orig` and record `original_sha256` in `manifest.json`. Attempts 2 and 3 **never** touch or overwrite `.orig` or `manifest.json`.
  4. **Execute, Test & Iterate (`attempt = 1..3`):** Edit owned files → run `uv run ruff check` and targeted `uv run pytest --tb=short -q` → verify acceptance criteria.
     - **PASS:** Atomically delete `.qa_loop/backups/<task_id>/`, release locks in `file_locks.json`, report `SUCCESS`.
     - **FAIL & `attempt < 3`:** Diagnose exact error logs, re-plan, verify against `precautions.json`, loop.
     - **FAIL & `attempt == 3`:** Execute Stage C (Atomic Rollback & Purge).
- **Stage C — 4-Stage Atomic Restore & Backup Purge Transaction (All-or-Nothing):**
  1. **Stage 1 (Pre-Flight Validation — Read-Only):** Verify `manifest.json` and every `.orig` file exist and match `original_sha256`. **Abort Condition:** If any backup file is missing or corrupted, halt immediately without touching any live file, keep file locks held, and escalate `ROLLBACK_ABORTED`.
  2. **Stage 2 (Co-Located Staging + `fsync`):** Copy each `.orig` file to a hidden temporary sibling in the **exact same parent directory** as the target file (e.g., `sim_core/persistence/.world_goddess.py.restore_tmp`) and call `fsync()`. Same-mount staging guarantees an atomic swap.
  3. **Stage 3 (Atomic POSIX Swap + Re-Hash):** Atomically `rename()` each `.restore_tmp` file over its live target file. Re-hash every restored live file and confirm bit-for-bit match against `original_sha256`.
  4. **Stage 4 (Atomic Backup Purge — Commit Point):** Only after all live files pass SHA-256 verification, atomically rename `.qa_loop/backups/<task_id>` to `.qa_loop/backups/.trash_<task_id>` and delete it. Write `handoff_report.json` with `"status": "COMMITTED"`, release all locks in `file_locks.json`, and terminate.
- **Stage D — Main Agent Escalation, Respawn & Outer Circuit Breaker:**
  1. Inspect `handoff_report.json` alongside prior reports; append recurring failure rules to `anti_patterns_detected` in `precautions.json`.
  2. Discard the old sub-agent context, re-lock files, and spawn a fresh sub-agent on the guaranteed-pristine codebase.
  3. **Outer Circuit Breaker (`MAX_SPAWNS = 4`, totaling 12 attempts):** If all 4 outer spawns fail, halt and present the consolidated `handoff_report` history to the human operator with the workspace safely intact.

### 7.4 Critical Edge Cases Guarded
| Failure Mode | Prevention Mechanism |
| :--- | :--- |
| **Crash Mid-Rollback (Half-Restored State)** | Stage 2 stages and `fsync`s temp files before Stage 3 performs atomic `rename()` swaps. If killed before Stage 4 deletes the backup dir, the Main Agent detects the surviving backup on startup and deterministically finishes Stages 1–4. |
| **Corrupted Backup Overwriting Live Code** | Stage 1 validates SHA-256 hashes of all `.orig` files read-only before touching any live file; validation failure aborts cleanly and holds locks to preserve evidence. |
| **Cross-Filesystem Non-Atomic Moves** | Temporary `.restore_tmp` files are created in the exact parent directory of each target file rather than `/tmp`, guaranteeing atomic metadata pointer swaps on the same mount. |
| **Two Sub-Agents Colliding on a File** | Upfront disjoint file partitioning + tool-level enforcement against `file_locks.json` blocks both concurrent reads and writes (`LOCK_VIOLATION`). |
| **Infinite Outer Respawn Loops** | Hard cap (`MAX_SPAWNS = 4`) paired with mandatory `precautions.json` updates ensures each fresh sub-agent explores a genuinely new strategy. |

### 7.5 Spec Reading, Phase Order & User-Confirmed External Downloads
1. **Read the relevant v3.0 spec under `docs/`** before implementing any subsystem (`ARCHITECTURE.md`, `GODOT_CLIENT_AND_ASSETS_SPEC.md`, `NEURAL_AND_LIFECYCLE_SPEC.md`, `RACES_AND_BIOLOGY_SPEC.md`, `DIVINE_HIERARCHY_SPEC.md`, `SOCIETY_AND_GOVERNANCE_SPEC.md`, `DATA_SCHEMA_AND_WORLD_GODDESS.md`).
2. **Follow `docs/roadmap/IMPLEMENTATION_ROADMAP.md` strictly in phase order (`Phase 0 → Phase 5`).** Never build `godot_client/` until the headless Python core passes all unit, double-entry conservation, corruption-rewind, and 1,500-agent 4-race soak tests.
3. **Never silently drop requirements.** If a spec rule conflicts with a library limitation, document the fallback in code comments while keeping the architectural invariant intact.
4. **Always request explicit user confirmation** before downloading external software (`Godot 4.7.2`, `Blender`, `VRoid Studio`) or third-party asset packs.