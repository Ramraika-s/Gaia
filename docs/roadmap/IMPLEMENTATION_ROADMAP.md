# IMPLEMENTATION_ROADMAP.md — Phased Build Order & Acceptance Tests 

Build strictly in phase order (`Phase 0` through `Phase 5`). **Do not advance to Phase N+1 until every acceptance test, lint check, and benchmark in Phase N passes cleanly under `uv run`.**

> **Execution Governance:** Every coding task in this roadmap executes under the **Multi-Agent QA Execution Loop & Atomic Rollback Protocol** defined in `AGENTS.md` (Section 7).

---

## Phase 0: `uv` Python Bootstrap, `.qa_loop/` Init & Interactive Toolchain Check
**Goal:** Establish a rock-solid, reproducible Python `3.12` environment via **`uv`** (bypassing Fedora 45's bleeding-edge system Python), initialize `.qa_loop/`, and inventory external software needed later in Phase 5 via interactive user confirmation.

### Deliverables
- `scripts/setup_uv_env.sh`:
  - Checks if `uv` is installed (offers official install command with user confirmation if missing).
  - Runs `uv python install 3.12`, `uv python pin 3.12`, and `uv sync` to resolve compatible CPU wheels for `torch`, `numpy`, `psutil`, `pydantic>=2.7`, `websockets`, `aiosqlite`, `duckdb`, `rich`, `pytest`, `pytest-asyncio`, and `ruff`.
- `pyproject.toml`, `.python-version`, `.gitignore` (ignoring `data/`, `.qa_loop/`, `.venv/`).
- `.qa_loop/precautions.json` and `.qa_loop/file_locks.json` initialized with baseline guardrails.
- `scripts/interactive_toolchain_setup.py`:
  - Audits host availability of external tools (`blender`, `godot` 4.7.2, `steam` / `VRoid Studio` via Proton) and checks `godot_client/addons/` + `godot_client/assets/`.
  - Searches for and prints exact official download URLs/commands for any missing software or CC0 packs, then prompts the user interactively (`[y/N]`) before executing any downloads or package installs.

### Acceptance Tests
- [ ] `uv run python --version` outputs pinned `Python 3.12.x` (isolated from Fedora 45 system Python).
- [ ] `uv run python -c "import torch, numpy, duckdb, aiosqlite, pydantic, websockets, psutil; print('OK')"` prints `OK` with zero warnings/errors.
- [ ] `uv run ruff check` and `uv run pytest --tb=short -q` execute cleanly.
- [ ] `.qa_loop/` backup, SHA-256 restore, and lock-violation self-check passes.

---

## Phase 1: Skeleton, Schemas, Spatial Grid/Heightmap, Self-Healer, World Goddess RBAC & Atomic Daily 2PC
**Goal:** Build all Pydantic v2 v3.0 contracts (4 races, 2 genders, cross-species pregnancy, Age-10 patronage, Divine Family), $O(1)$ spatial hash grid + heightmap loader, Self-Healing Error Solver with 5-fault escalation, `WorldGoddessCritic` RBAC, God Ledger, SQLite WAL atomic end-of-day commits, SHA-256 corruption rewind, and DuckDB read-only analytics.

### Deliverables
- `sim_core/config.py` (`REAL_SECONDS_PER_GAME_DAY=5400`, `SLAB_SIZE=2048`, LOD frequencies, race-scaled stage thresholds, settlement & Neutral Free City appeal thresholds, seedable RNG).
- `sim_core/schemas.py` & `sim_core/races.py` (exact v3.0 contracts: `Gender`, `RaceProfile`, `CROSS_SPECIES_CONCEPTION_CHANCE=0.50`, `CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE=0.60`, `DragonForm`, `DivineEntityRecord`, `SisterCouncilMessage`, `DailyManifest`).
- `sim_core/spatial/hash_grid.py` (vectorized `16×16m` chunk cell index for `10,000 × 10,000m` world) & `sim_core/spatial/heightmap.py` (`data/world_heightmap.npy` loader + fallback flat plane for headless tests).
- `sim_core/resilience/healer.py` (`ErrorHealer` covering `TENSOR_NAN_INF`, `ECONOMY_CONSERVATION_DRIFT`, `COORD_OUT_OF_BOUNDS`, `WS_BRIDGE_DROP`, `SQLITE_COMMIT_FAIL`, `AGENT_REPEAT_FAULT` quarantine, and `> 5` same-class faults/day `[CRITICAL]` escalation).
- `sim_core/persistence/db.py` (v3.0 WAL DDL + atomic `BEGIN IMMEDIATE ... COMMIT/ROLLBACK` daily executor + DuckDB read-only analytics helper).
- `sim_core/persistence/world_goddess.py` (full v3.0 `WorldGoddessCritic` RBAC & validation matrix + `CriticVerdict` emitter).
- `sim_core/divine/god_ledger.py` (`GodPresenceTracker`, strict deity-only routing to God, prayer/altar Prayer Head salience grouping, daily `data/god_ledger/day_XXXXX.md` + `latest.md` writer).
- `sim_core/persistence/checkpoints.py` (World Goddess atomic Two-Phase Commit with SHA-256 `manifest.json` + automatic startup corruption rewind).
- `tests/conftest.py` (shared local SQLite + deterministic world fixtures).

### Acceptance Tests (`tests/test_schemas.py`, `tests/test_world_goddess_rbac_and_atomic_save.py`, `tests/test_healer_resilience.py`, `tests/test_persistence_corruption_rewind.py`)
- [ ] Spatial hash grid inserts and queries `10,000` random coordinates in under `2 ms`; heightmap bilinear lookup runs in $O(1)$.
- [ ] Same-gender mating (`BOY+BOY` or `GIRL+GIRL`) and `TRUE_DRAGON` cross-species mating are rejected by `WorldGoddessCritic`.
- [ ] Random mortal attempting to edit `world_library` without `> 50%` Appointed Elder Council consensus receives `FAILURE`; Nation attempting to appoint a 3rd Library Elder is rejected; `God` (`bypass_god_check=True`) succeeds.
- [ ] Double-entry `CREDIT_TRANSFER` (e.g., parent allowance) fails with `"Insufficient funds"` if `sender.credits < amount` and never mints credits.
- [ ] `JUDICIARY_RULING` attempting to convict verified `SELF_DEFENSE` or `ACTIVE_WAR` is rejected.
- [ ] Injecting a simulated SQLite error mid-commit triggers full `ROLLBACK` (zero partial rows written).
- [ ] Bit-flipping `day_00002.pt` causes startup loader to fail SHA-256 check, automatically rewind to `day_00001` (both `.db` and `.pt`), and log `[CORRUPTION_REWIND]`.
- [ ] Triggering the same `fault_class` 6 times in 1 day auto-heals the first 5 and escalates to `[CRITICAL]` on the 6th.
- [ ] DuckDB read-only attach queries `civ.fatalities` and `civ.agents` without locking `aiosqlite`.

---

## Phase 2: Unbounded Slab-Grown Tensor Brains (`torch.bmm` + `GRUCell`) & Cognitive LOD
**Goal:** Implement `SharedSkillNet`, dynamically growable `BatchedAgentSelfNet` (no hard cap, 2,048-slot slabs), Multi-Tier Cognitive LOD, race-scaled neuroplasticity, intrinsic curiosity, and `NaN` self-healing.

### Deliverables
- `sim_core/neural/shared_net.py` (`SharedSkillNet`, `32 -> 64 -> 64 -> 20+1`, survival gate `g_survival = 0.25`, hard stage masking).
- `sim_core/neural/batched_self_net.py` (unbounded 2,048-slab `GRUCell(20, 32)` + output heads, `torch.bmm` forward pass, slot reclamation, Bernoulli crossover + Gaussian mutation, `NaN`/`Inf` integrity check wired to `ErrorHealer`).
- `sim_core/neural/trainer.py` (RAM ring rollout tensors, stage-weighted intrinsic curiosity, vectorized policy + value + self-prediction loss, per-slot stage × race neuroplasticity LR, grad clipping).
- `sim_core/neural/social_learning.py` (parental care/teaching, peer observation, World Library reads, tradition adoption).
- `sim_core/tools/bench_tensors.py` (10,000-agent latency, slab growth & RAM profiler).

### Acceptance Tests (`tests/test_batched_neural_unbounded.py`)
- [ ] **Unbounded Slab Growth:** Spawning `2,500` agents cleanly expands capacity from `2,048` to `4,096` without losing existing weights or GRU hidden states.
- [ ] **10,000-Agent Benchmark:** `uv run python -m sim_core.tools.bench_tensors --agents 10000 --steps 50` averages under `25 ms` per forward pass and uses under `250 MB` RAM for neural tensors.
- [ ] `INFANT` agents assign exact `0.0` probability to locked `ADULT` actions (`GIVE_FAMILY_ALLOWANCE`, `MARKET_WTC_ORDER`, `PROPERTY_BUY_OR_SELL`, `DEFEND_OR_ATTACK`).
- [ ] Injecting `NaN` into one agent's GRU hidden state is caught and restored by `ErrorHealer` without corrupting other slots.

---

## Phase 3: Headless Unbounded 5-Race Civilization Core
**Goal:** Run a complete multi-generational 5-race civilization headlessly via `MockWorldAdapter`—verifying cross-species pregnancy, Age-10 mixed-race patronage choice, Dragon metamorphosis & deterrence, Demon generational Dragon deterrence & out-group hostility prior, Divine Family & 5-Sister Councils, realistic crying/comforting, naming, Elder Council World Library, bordered polities & Neutral Free Cities, double-entry economy & inflation, probate/escheatment, Judiciary, and pure end-of-day atomic saves.

### Deliverables
- `sim_core/bridge/base.py` & `sim_core/bridge/mock_adapter.py`.
- `sim_core/divine/hierarchy.py` (World Goddess + 5 Racial God-Mothers, custom naming, personality vectors, Divine Energy/cooldowns, Non-Aggression Covenant, Oracles `1–3`/race) & `sim_core/divine/sister_council.py` (1-on-1 & 5-Sister Council dialogue, Divine Truces, World Goddess mediation).
- `sim_core/society/naming.py` (racial/gender/cultural phoneme birth names, dynasties, adult self-naming & epithets).
- `sim_core/society/borders.py` (explicit non-overlapping `16×16m` chunk borders, 5-tier `SETTLEMENT_APPEAL` & `NEUTRAL_FREE_CITY` appeals).
- `sim_core/society/seasons.py`, `sim_core/society/rumors.py`, `sim_core/society/morality.py`.
- `sim_core/society/economy.py` (double-entry closed-loop World Bank & transfers) & `sim_core/society/wtc_market.py` (order book + $M/Q$ inflation).
- `sim_core/society/property.py` (`16×16m` parcels, buy/sell/rent, deterministic probate & settlement/wilderness escheatment).
- `sim_core/society/politics.py` (`VILLAGE -> TOWN -> CITY -> STATE -> NATION`, Neutral Free Cities, Kings, Elections, Wars).
- `sim_core/society/religion.py` (birth imprinting, strict routing to God-Mother/World Goddess only, intent-scaled prayer gains, inactivity decay, Popes, congregational altar prayers with Prayer Head).
- `sim_core/society/library.py` (Two-Book Governance: `world_library` + `divine_codex` with Option B split write authority).
- `sim_core/society/judiciary.py` & `sim_core/society/traditions.py`.
- `sim_core/lifecycle.py` (race-specific gestation, cross-species 50% conception / 60% birth survival, Age-10 mixed-race patronage choice + tie-break, Dragon metamorphosis, injury/illness, root-cause infant distress/crying, gradual comforting, stage gates, permanent death).
- `sim_core/engine.py` (Multi-Tier LOD scheduler, World Goddess day-end atomic commit trigger, `speed 1x..60x`, graceful `SIGINT`/`SIGTERM` shutdown).
- `sim_core/tools/soak_test.py` (1,500-agent 5-race headless soak + atomic end-of-day & corruption-rewind verifier).

### Acceptance Tests (`tests/test_races_gender_pregnancy_dragon_morph.py`, `tests/test_divine_hierarchy_patronage_and_councils.py`, `tests/test_lifecycle_crying_and_naming.py`, `tests/test_economy_double_entry_inflation.py`, `tests/test_politics_borders_library_religion.py`)
- [x] **Cross-Species Mating & Gestation:** Across 1,000 seeded cross-species pairings, empirical conception rate converges to `~50%`, birth survival converges to `~60%` (stillbirths log `BIRTH_COMPLICATION` with zero tensor slot allocated), and gestation duration matches the mother's `RaceProfile.gestation_days`.
- [x] **Age-10 Mixed-Race Patronage Choice:** Mixed-race child remains uncommitted until biological age 10; active choice locks target God-Mother; non-choice auto-allocates higher affinity; exact tie escalates to **World Goddess** to assign and logs decree.
- [x] **Dragon Metamorphosis & Deterrence:** Provoked Adult Dragon shifts `HUMANOID_DRAGON -> TRUE_DRAGON` (`SELF_DEFENSE`, zero domestic crime), emits fear aura, drains stamina at `1.8x`, reverts when threat clears, and witnesses spread Rumor Packets.
- [x] **Divine Family & Non-Aggression Covenant:** Mortals cannot pray directly to God; offensive rival-civilian miracle by a God-Mother is blocked by `WorldGoddessCritic` (`covenant_rebukes += 1`) and triggers Sister Council / World Goddess mediation; Divine Truce blocks wartime boosts.
- [x] **Realistic Crying & Comforting:** Hungry/injured infant crosses `distress >= 0.45` (`crying=True`); parent comforting reduces distress gradually, but infant keeps crying until hunger/injury is actually resolved.
- [ ] **Dynamic Faith & Altar Prayers:** Earnest prayer increases `faith_devotion` more than parent-directed prayer; `> 2` days without praying decays affinity; `10` mortals at an altar emit **1 unified congregational message** spoken by the Prayer Head (prioritizing Oracle → Cleric → Elder).
- [ ] **Two-Book Governance & Bordered Appeals:** Mortal World Library proposal passes Elders (`>50%`) → 1 God-Mother approval starts 1-day objection window → commits if `<3` objections; blocked if `>=3/5` objections (appealable to Goddess/God); 0 approvals in 30 days auto-expires; World Goddess + 1 Daughter succeeds; 3/5 Daughters alone succeeds; 2/5 Daughters fails; Divine Codex non-mechanical decrees require World Goddess + 3/5 Daughters; parameter overrides proposed by Goddess (alone) or 5/5 Daughters to God, applied only by God; Settlement appeal succeeds only when pop/parcel/treasury thresholds are met with non-overlapping borders; multi-racial City (`>= 2` races at `>= 15%`) qualifies for `NEUTRAL_FREE_CITY` (`war_exempt = True`).
- [ ] **Closed-Loop Conservation, Inflation & Escheatment:** Total credits across all accounts + World Bank reserve remain strictly conserved across 600 ticks; Winter + war borrowing raises WTC `CPI`; heirless settlement death escheats parcel to treasury, wilderness death flips to `UNCLAIMED`.
- [ ] **1,500-Agent 5-Race Soak + Atomic Rewind:** `uv run python -m sim_core.tools.soak_test --ticks 600 --agents 1500 --verify-atomic-rewind` passes with zero errors and verifies zero mid-day disk writes.

---

## Phase 4: Rich God Console CLI, WebSocket Binary Bridge & DuckDB Analytics
**Goal:** Deliver full terminal divine control, deity naming, `speed 1x..60x` fast-forwarding, real-time vs. AFK God Ledger delivery, DuckDB analytics queries, and the Python WebSocket server ready for Godot 4.7.2.

### Deliverables
- `sim_core/god_console/cli.py` (`rich` interactive terminal implementing all v3.0 commands: `status`, `pop`, `fatalities`, `crimes`, `nations`, `borders`, `elections`, `religions`, `deities`, `council`, `elders`, `wtc`, `bank`, `parcel`, `traditions`, `library`, `ledger`, `inspect`, `name_deity`, `spawn`, `bless`, `curse`, `smite`, `war`, `coronate`, `appoint_pope`, `decree`, `speed`, `pause`, `resume`, `step`, `save`, `rewind`, `shutdown`).
- `sim_core/bridge/godot_ws_bridge.py` (`websockets` server on `ws://127.0.0.1:8765`, broadcasting binary `PackedFloat32Array` bulk positions at `5–10 Hz` + JSON `BUBBLE_SYNC`, `WORLD_TIME_WEATHER`, `SIGN_UPDATE`, `ALTAR_BEACON`, `DIVINE_HUD_MESSAGE`, and handling `GOD_STATE`, `GOD_LIBRARY_EDIT`, and `GOD_COMMAND`).

### Acceptance Tests
- [ ] When `GodPresenceTracker` is `AWAY`, World Goddess & God-Mother messages stay strictly in RAM and flush cleanly into `data/god_ledger/day_XXXXX.md` at end-of-day; when `ACTIVE`, they stream immediately.
- [ ] Mock WebSocket client receives binary `PackedFloat32Array` frames for `10,000` agents (`240 KB/frame`) with under `2 ms` serialization latency, and sending `GOD_LIBRARY_EDIT` updates Python RAM cleanly without touching SQLite mid-day.
- [ ] `speed 20x` accelerates headless simulation cleanly and drops back to `speed 1x` without desyncing day counters.

---

## Phase 5: Interactive Toolchain/Asset Setup & Godot 4.7.2 Client (Vertical Slices A, B, C)
**Goal:** Provision external tools and CC0 assets interactively with the user, then build the stylized anime-fantasy **Godot 4.7.2 (Vulkan)** 3D Reality Bubble + Orbital God Map tuned for the Radeon 780M.

### Step 5.0: Interactive Software & Asset Acquisition (User-Confirmed)
Run `uv run python scripts/interactive_toolchain_setup.py`. With explicit user confirmation at each step:
1. Verify/install **Blender** (`sudo dnf install blender`), **Godot 4.7.2** (Linux x86_64), and **VRoid Studio** (via Steam/Proton).
2. Download and extract Godot addons into `godot_client/addons/`: **Terrain3D v1.1.0**, **Sky3D v2.1**, **VRM Importer & MToon Shader v2.6.1**.
3. Download and organize free CC0 packs into `godot_client/assets/`: **Quaternius** (`Characters - Fantasy Races`, `Modular Character Outfits - Fantasy`, `Universal Animation Library 1 & 2`, `Medieval Village MegaKit`, `Fantasy Props MegaKit`, `Ghibli Game Kit`, `Ultimate Stylized Nature MegaKit`, `Animated Dragon`), **KayKit** (`Dungeon Pack 1.1`), and **Kenney** (`Particle Pack`, `Audio Packs`).
4. Guide creation/export of the **7 VRoid Divine Hero `.vrm` models** using VRoid Studio's built-in **Reduce Polygons + Combine Meshes** preset (no Blender Decimate on rigged VRMs; Blender used solely for bone-parenting props/wings/horns).

### Vertical Slice A: World, Terrain3D, Sky3D & Parcel Grid
- Sculpt the 5 racial biomes + flat landmark pads in `Terrain3D v1.1.0`; export `data/world_heightmap.npy` for Python elevation sync.
- Configure `Sky3D v2.1` synced to Python's `WORLD_TIME_WEATHER` (1–2 real-hour day) with a readable moonlight/ambient floor in `WorldEnvironment`.
- Implement global `season_progress` toon shader uniform (Spring → Autumn → Winter frost) and `16×16m` parcel border decal/overlay.

### Vertical Slice B: Pooled 120-Mortal Reality Bubble, Dragon Morph & Orbital Map
- Pre-allocate `120` pooled mortal scenes (`visible = false`) from the **7 Quaternius base rigs** with stage/race bone scaling, `mortal_toon.gdshader` instance uniforms (`skin_hsv`, `cloth_primary`, `cloth_secondary`, `injury_mix`), shared `SkeletonProfileHumanoid` animations, `InfantTears` crying VFX, and **Animation LOD** (`60 Hz` / `20 Hz` / `10 Hz`).
- Wire `scripts/dragon_morph.gd` zero-stutter `HUMANOID_DRAGON` $\leftrightarrow$ `TRUE_DRAGON` visibility toggle + `MetamorphosisBurst.tscn`.
- Implement the **Orbital God Map** (`MultiMeshInstance3D`, 1 draw call for `10,000+` agents) activating above `250m` altitude, fed directly by Python's binary `PackedFloat32Array` WebSocket stream, with click-to-swoop back into 3D.

### Vertical Slice C: Institutional Landmarks, 7 VRoid Deities & In-Godot Divine HUD
- Assemble walk-in landmarks: **World Library** (clicking Lecterns opens 2D `TextEdit` modal sending `GOD_LIBRARY_EDIT` over WebSocket—never touching SQLite), **World Trade Centre** & **Courthouse** (`UPDATE_ONCE` `SubViewport` hanging signs redrawn only on `SIGN_UPDATE`), **Grand Cathedral**, and **`AltarPrayerBeacon.tscn`** skyward light pillars.
- Import the **7 VRoid Divine Heroes** (`god_avatar.vrm` with `DivineAura.tscn`, `world_goddess.vrm`, and the 5 Racial God-Mothers).
- Build `scripts/divine_hud.gd` displaying live World Goddess & God-Mother messages, Inter-Sister Council logs, `ErrorHealer` alerts, deity naming, and `speed 1x..60x` controls.

### Phase 5 Acceptance Tests
- [ ] Hybrid RTS / 3rd-person `God` camera smoothly pools `60–120` animated mortals across all 5 races within `120–160m` at stable frame rates on Radeon 780M (MSAA 2x, 2048px shadows) with zero runtime `instantiate()`/`queue_free()` stutter.
- [ ] Zooming above `250m` transitions seamlessly to the 1-draw-call `MultiMeshInstance3D` Orbital God Map showing `10,000+` moving agents and `16×16m` nation borders; clicking any city swoops smoothly back into 3D.
- [ ] Provoked Dragon morphs cleanly to `TRUE_DRAGON` with `MetamorphosisBurst`; crying infants display `InfantTears` + `cry_distress` animation; active congregational altars project `AltarPrayerBeacon`.
- [ ] Editing a World Library book in Godot's 2D modal sends `GOD_LIBRARY_EDIT` over WebSocket to Python RAM (zero direct SQLite access from Godot) and persists cleanly during the World Goddess's atomic end-of-day SHA-256 commit.
- [ ] Closing Godot flips `GodPresenceTracker` to `AWAY` (routing messages to `data/god_ledger/day_XXXXX.md`); clean shutdown (`Ctrl+C`) commits `manifest.json` (`VERIFIED`), and restarting restores all agents, deities, heightmap positions, and borders identically.