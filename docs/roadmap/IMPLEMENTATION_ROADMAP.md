# IMPLEMENTATION_ROADMAP.md — Phased Build Order, Sprints & Acceptance Milestones

**Status:** Phases 0–5 and Gaia v4.0 Sprints 0–6 (including Sprint 5.5) are **100% COMPLETE and VERIFIED** across 109 pytest tests, the 10,000-agent neural benchmark, and the 1,500-agent headless soak test.

> **Execution Governance:** All implementation work adheres to the **Multi-Agent QA Execution Loop & Atomic Rollback Protocol** defined in `AGENTS.md` (Section 7).

---

## Phase 0: `uv` Python Bootstrap, `.qa_loop/` Init & Interactive Toolchain Check
**Status:** **COMPLETE**

### Deliverables
- `scripts/setup_uv_env.sh`: Pinned Python 3.12, installed CPU wheels for `torch`, `numpy`, `psutil`, `pydantic>=2.7`, `websockets`, `aiosqlite`, `duckdb`, `rich`, `pytest`, `pytest-asyncio`, `ruff`.
- `pyproject.toml`, `.python-version`, `.gitignore` (ignoring `data/`, `.qa_loop/backups/`, `.venv/`).
- `.qa_loop/precautions.json` and `.qa_loop/file_locks.json` initialized with baseline guardrails.
- `scripts/interactive_toolchain_setup.py`: Audits host availability of `blender`, `godot` 4.7.2, `steam`/`VRoid Studio`, addons, and CC0 asset packs with explicit interactive user confirmation.

### Acceptance Milestones
- [x] `uv run python --version` outputs pinned `Python 3.12.x` (isolated from system Python).
- [x] `uv run python -c "import torch, numpy, duckdb, aiosqlite, pydantic, websockets, psutil; print('OK')"` outputs `OK`.
- [x] `uv run ruff check` and `uv run pytest --tb=short -q` execute cleanly.
- [x] `.qa_loop/` backup, SHA-256 restore, and lock-violation self-check verified.

---

## Phase 1: Skeleton, Schemas, Spatial Grid/Heightmap, Self-Healer, World Goddess RBAC & Atomic Daily 2PC
**Status:** **COMPLETE**

### Deliverables
- `sim_core/config.py`: `REAL_SECONDS_PER_GAME_DAY=5400`, `SLAB_SIZE=2048`, LOD frequencies, biological age calibration, settlement appeal thresholds, seedable deterministic RNG.
- `sim_core/schemas.py` & `sim_core/races.py`: Core Pydantic v2 contracts (`Gender`, `RaceProfile`, `DragonForm`, `DivineEntityRecord`, `SisterCouncilMessage`, `DailyManifest`, `CommitProposal`, `CriticVerdict`).
- `sim_core/spatial/hash_grid.py`: Vectorized `16×16m` chunk cell index for $O(1)$ spatial queries.
- `sim_core/spatial/heightmap.py`: `data/world_heightmap.npy` loader with bilinear interpolation and fallback flat plane for headless tests.
- `sim_core/resilience/healer.py`: `ErrorHealer` covering tensor `NaN`/`Inf`, double-entry conservation drift, out-of-bounds coordinates, WebSocket drop, and the **5-faults/day `[CRITICAL]` escalation guard**.
- `sim_core/persistence/db.py`: SQLite WAL DDL + atomic `BEGIN IMMEDIATE ... COMMIT/ROLLBACK` daily executor + DuckDB read-only analytics helper.
- `sim_core/persistence/world_goddess.py`: Full `WorldGoddessCritic` RBAC and validation matrix with `CriticVerdict` emitter.
- `sim_core/divine/god_ledger.py`: `GodPresenceTracker`, strict deity-only routing to God, prayer salience grouping, daily `data/god_ledger/day_XXXXX.md` + `latest.md` writer.
- `sim_core/persistence/checkpoints.py`: World Goddess atomic Two-Phase Commit with SHA-256 `manifest.json` + automatic startup corruption rewind.
- `tests/conftest.py`: Shared local SQLite and deterministic world state fixtures.

### Acceptance Milestones
- [x] Spatial hash grid inserts and queries `10,000` coordinates in under `2 ms`; heightmap lookup runs in $O(1)$.
- [x] Same-gender mating (`BOY+BOY` or `GIRL+GIRL`) and `TRUE_DRAGON` cross-species mating are rejected by `WorldGoddessCritic`.
- [x] Random mortal attempting to edit `world_library` without `> 50%` Appointed Elder Council consensus receives `FAILURE`; Nation attempting to appoint a 3rd Elder is rejected; God (`bypass_god_check=True`) succeeds.
- [x] Double-entry `CREDIT_TRANSFER` fails with `"Insufficient funds"` if `sender.credits < amount` and never mints credits.
- [x] `JUDICIARY_RULING` attempting to convict verified `SELF_DEFENSE` or `ACTIVE_WAR` is rejected.
- [x] Injecting a simulated SQLite error mid-commit triggers full `ROLLBACK` (zero partial writes).
- [x] Bit-flipping checkpoint `.pt` causes startup loader to fail SHA-256 check, automatically rewind to prior verified day, and log `[CORRUPTION_REWIND]`.
- [x] Triggering the same `fault_class` 6 times in 1 day auto-heals the first 5 and escalates to `[CRITICAL]` on the 6th.
- [x] DuckDB read-only attach queries `civ.fatalities` and `civ.agents` without locking SQLite.

---

## Phase 2: Unbounded Slab-Grown Tensor Brains (`torch.bmm` + `GRUCell`) & Cognitive LOD
**Status:** **COMPLETE**

### Deliverables
- `sim_core/neural/shared_net.py`: `SharedSkillNet` baseline MLP with survival gate ($g_{\text{survival}} = 0.25$) and hard stage masking.
- `sim_core/neural/batched_self_net.py`: Unbounded 2,048-slab `GRUCell(20, 32)` + output heads, vectorized `torch.bmm` forward pass, slot reclamation, Bernoulli crossover + Gaussian mutation, and `NaN`/`Inf` integrity check wired to `ErrorHealer`.
- `sim_core/neural/trainer.py`: RAM ring rollout tensors, stage-weighted intrinsic curiosity, vectorized policy + value + self-prediction loss, per-slot stage × race neuroplasticity LR, grad clipping.
- `sim_core/neural/social_learning.py`: Parental care/teaching, peer observation, World Library reads, tradition adoption.
- `sim_core/tools/bench_tensors.py`: 10,000-agent latency, slab growth & RAM profiler.

### Acceptance Milestones
- [x] **Unbounded Slab Growth:** Spawning `2,500` agents cleanly expands capacity from `2,048` to `4,096` without losing existing weights or GRU hidden states.
- [x] **10,000-Agent Benchmark:** Full batched forward pass executes in **~15.01 ms/step** on CPU (well below the `< 25 ms` target) with **232.14 MB RAM** (target `< 250 MB`).
- [x] `INFANT` agents assign exact `0.0` probability to locked `ADULT` actions (`GIVE_FAMILY_ALLOWANCE`, `MARKET_WTC_ORDER`, `PROPERTY_BUY_OR_SELL`, `DEFEND_OR_ATTACK`).
- [x] Injecting `NaN` into one agent's GRU hidden state is caught and restored by `ErrorHealer` without corrupting other slots.

---

## Phase 3: Headless Unbounded 5-Race Civilization Core
**Status:** **COMPLETE**

### Deliverables
- `sim_core/bridge/base.py` & `sim_core/bridge/mock_adapter.py`.
- `sim_core/divine/hierarchy.py` (World Goddess + 5 Racial God-Mothers, custom naming, personality vectors, Divine Energy, Non-Aggression Covenant, Oracles `1–3`/race) & `sim_core/divine/sister_council.py` (1-on-1 & 5-Sister Council dialogue, Divine Truces, World Goddess mediation).
- `sim_core/society/naming.py` (racial/gender/cultural phoneme birth names, dynasties, adult self-naming & epithets).
- `sim_core/society/borders.py` (explicit non-overlapping `16×16m` chunk borders, 5-tier `SETTLEMENT_APPEAL` & `NEUTRAL_FREE_CITY` appeals).
- `sim_core/society/seasons.py`, `sim_core/society/rumors.py`, `sim_core/society/morality.py`.
- `sim_core/society/economy.py` (double-entry closed-loop World Bank & transfers) & `sim_core/society/wtc_market.py` (order book + $M/Q$ inflation).
- `sim_core/society/property.py` (`16×16m` parcels, buy/sell/rent, deterministic probate & escheatment).
- `sim_core/society/politics.py` (`VILLAGE -> TOWN -> CITY -> STATE -> NATION`, Neutral Free Cities, Kings, Elections, Wars).
- `sim_core/society/religion.py` (birth imprinting, strict routing to God-Mother/World Goddess only, intent-scaled prayer gains, inactivity decay, Popes, congregational altar prayers with Prayer Head).
- `sim_core/society/library.py` (Two-Book Governance: `world_library` + `divine_codex` with Option B split write authority).
- `sim_core/society/judiciary.py` & `sim_core/society/traditions.py`.
- `sim_core/lifecycle.py` (gestation, cross-species conception/survival, Age-10 patronage choice, Dragon morph, crying/comforting, stage gates, permanent death).
- `sim_core/engine.py` (Multi-Tier LOD scheduler, World Goddess day-end atomic commit trigger, `speed 1x..60x`, graceful `SIGINT`/`SIGTERM` shutdown).
- `sim_core/tools/soak_test.py` (1,500-agent 5-race headless soak + atomic end-of-day & corruption-rewind verifier).

### Acceptance Milestones
- [x] **Cross-Species Mating & Gestation:** Across 1,000 seeded cross-species pairings, conception converges to `~50%`, birth survival converges to `~60%`, and gestation duration matches the mother's `RaceProfile`.
- [x] **Age-10 Mixed-Race Patronage Choice:** Mixed-race child remains uncommitted until biological age 10 (`3.33 * L` days); choice locks target God-Mother; ties escalate to World Goddess.
- [x] **Dragon Metamorphosis & Deterrence:** Provoked Adult Dragon shifts `HUMANOID_DRAGON -> TRUE_DRAGON` (`SELF_DEFENSE`, zero domestic crime), emits fear aura, drains stamina at `1.8x`, reverts when threat clears.
- [x] **Divine Family & Non-Aggression Covenant:** Mortals cannot pray directly to God; offensive rival miracle blocked by `WorldGoddessCritic` (`covenant_rebukes += 1`) and triggers Sister Council mediation.
- [x] **Realistic Crying & Comforting:** Hungry/injured infant crosses `distress >= 0.45` (`crying=True`); parent comforting reduces distress gradually; crying persists until root cause is resolved.
- [x] **Dynamic Faith & Altar Prayers:** Earnest prayer increases `faith_devotion` more than parent-directed prayer; inactivity decays affinity; `>= 3` mortals at an altar aggregate into 1 unified congregational message led by Prayer Head.
- [x] **Two-Book Governance & Bordered Appeals:** Mortal World Library proposals pass Elders (`> 50%`) → God-Mother 1-day objection window → commits if `< 3` objections; Divine Codex text decrees require Goddess + 3/5 Daughters; parameter overrides proposed to God and applied only by God.
- [x] **Closed-Loop Conservation, Inflation & Escheatment:** World Bank reserve + agent balances strictly conserved with **0.000000 credit drift**; WTC CPI reflects $M/Q$; heirless settlement death escheats parcel to municipality.
- [x] **1,500-Agent 5-Race Soak + Atomic Rewind:** 1,500-agent soak test steps at **102.0 Hz (9.81 ms/tick)**, verifies zero mid-day disk writes, commits atomically, and verifies SHA-256 corruption rewind.

---

## Phase 4: Rich God Console CLI, WebSocket Binary Bridge & DuckDB Analytics
**Status:** **COMPLETE**

### Deliverables
- `sim_core/god_console/cli.py`: Rich interactive terminal implementing all inspection and intervention commands (`status`, `pop`, `fatalities`, `crimes`, `nations`, `borders`, `elections`, `religions`, `deities`, `council`, `elders`, `wtc`, `bank`, `parcel`, `traditions`, `library`, `codex`, `ledger`, `inspect`, `name_deity`, `spawn`, `bless`, `curse`, `smite`, `war`, `coronate`, `appoint_pope`, `decree`, `speed`, `pause`, `resume`, `step`, `save`, `rewind`, `shutdown`).
- `sim_core/bridge/godot_ws_bridge.py`: WebSocket server on `ws://127.0.0.1:8765`, broadcasting binary `PackedFloat32Array` orbital frames (24 bytes/agent) + JSON sync events (`BUBBLE_SYNC`, `DEITY_SYNC`, `BUILDING_SYNC`, `WORLD_TIME_WEATHER`, `SIGN_UPDATE`, `ALTAR_BEACON`, `DIVINE_HUD_MESSAGE`) and dispatching inbound commands.

### Acceptance Milestones
- [x] When `GodPresenceTracker` is `AWAY`, World Goddess & God-Mother messages stay strictly in RAM and flush into `data/god_ledger/day_XXXXX.md` at end-of-day; when `ACTIVE`, they stream immediately.
- [x] Binary `PackedFloat32Array` frames for `10,000` agents serialize in under `2 ms` (`< 240 KB/frame`); `GOD_LIBRARY_EDIT` updates Python RAM cleanly with zero mid-day disk writes.
- [x] `speed 20x` and `speed 60x` accelerate simulation cleanly and return to `speed 1x` without desyncing day counters.

---

## Phase 5: Interactive Toolchain/Asset Setup & Godot 4.7.2 Client (Vertical Slices A, B, C)
**Status:** **COMPLETE**

### Deliverables
- `scripts/interactive_toolchain_setup.py`: Audits external tools and CC0 asset packs with explicit user confirmation.
- **Vertical Slice A:** Terrain displacement, `Sky3D v2.1` day/night cycle, `season_progress` global uniform, and `16×16m` parcel border overlay (`godot_client/scripts/parcel_border_overlay.gd`).
- **Vertical Slice B:** Pooled 120-mortal Reality Bubble (`godot_client/scripts/reality_bubble_manager.gd`, `mortal_actor.gd`), zero-stutter Dragon metamorphosis toggle, and 1-draw-call `MultiMeshInstance3D` Orbital God Map (`orbital_multimesh_renderer.gd`) above 250m.
- **Vertical Slice C:** Walk-in institutional landmarks (`landmarks_manager.gd`), 7 VRoid deities, in-game Divine HUD (`divine_hud.gd`), Two-Book modal (`two_book_modal.gd`), and God Console overlay (`god_console_overlay.gd`).

### Acceptance Milestones
- [x] Hybrid RTS / 3rd-person camera smoothly pools 60–120 animated mortals across 5 races within 140m at stable frame rates on Radeon 780M (MSAA 2x, 2048px shadows) with zero mid-flight `instantiate()`/`queue_free()`.
- [x] Zooming above 250m altitude cross-fades to 1-draw-call `MultiMeshInstance3D` Orbital God Map; clicking swoops back to 3D.
- [x] Provoked Dragon morphs cleanly to `TRUE_DRAGON`; crying infants display particles and animations; active altars project `AltarPrayerBeacon`.
- [x] Editing a World Library book in Godot modal sends `GOD_LIBRARY_EDIT` over WebSocket to Python RAM (zero direct SQLite access from Godot) and commits atomically at end-of-day.
- [x] Clean shutdown (`Ctrl+C`) commits `manifest.json` (`VERIFIED`), and restarting restores all agents, deities, and borders identically.

---

## Gaia v4.0 Sprint 0: Terrain & Heightmap Parity (`1024×1024`, `8km × 8km`)
**Status:** **COMPLETE**

### Deliverables
- `scripts/generate_world_heightmap.py`: Generates the exact `1024×1024` (`-4000..4000m`) heightmap with smooth continental contours, Ring 0 plateau (`32m`), Ring 1 city anchors, Ring 2 frontier slopes, and Ring 3 ocean floor (`SEA_LEVEL = 0.0m`).
- `godot_client/scripts/terrain_height_sampler.gd`: Reads `data/world_heightmap.npy` directly, constructs a matching `HeightMapShape3D`, and exposes fast bilinear height sampling.
- `godot_client/scripts/terrain_manager.gd`: Binds displaced terrain mesh, physics collider, and `terrain_biome.gdshader` uniforms.
- `tests/test_heightmap_parity.py`: Verifies bit-for-bit elevation parity between Python and Godot height samplers across 1,000 random coordinates.

### Acceptance Milestones
- [x] Python and Godot elevation samples agree across all coordinates with **0.00m error**.
- [x] `HeightMapShape3D` physics collider perfectly aligns with visual terrain displacement.

---

## Gaia v4.0 Sprint 1: Palace Plateau & Twin Dragons
**Status:** **COMPLETE**

### Deliverables
- `godot_client/scenes/landmarks/grand_divine_palace.tscn`: Multi-tier Acropolis palace structure seated at `(0, 32, 0)`.
- Twin Guardian Dragons flanking the Main Gate (`x = ±12m, y = 32m, z = 38m`): Left (Sovereign of Ash) and Right (Sovereign of Frost) with terrifying idle poses and fear aura emitters.
- `tests/test_palace_security_and_knights.py`: Validates Acropolis positioning and Dragon visual anchors.

### Acceptance Milestones
- [x] Grand Divine Palace sits flush on the 32m central plateau with zero ground clipping.
- [x] Twin Guardian Dragons spawn symmetrically flanking the Main Palace Gate.

---

## Gaia v4.0 Sprint 2: Acropolis Security & Knight Battalion
**Status:** **COMPLETE**

### Deliverables
- `sim_core/world/palace_security.py`:
  - 3-State Entry Permission Machine (`BYPASS`, `HALT_AND_REQUEST`, `TRESPASS`/`HOSTILE`).
  - 24-Knight Palace Battalion patrolling courtyard, gates, and perimeter.
  - Mortal petition routing to God (if active) or World Goddess (delegation timeout: 30 ticks).
  - Integration with Judiciary for unauthorized trespass arrests.
- WebSocket payloads: `PALACE_ENTRY_REQUEST` and `GOD_PALACE_DECISION`.

### Acceptance Milestones
- [x] God Avatar, World Goddess, God-Mothers, and on-duty Knights bypass gate security freely.
- [x] Mortals halting in the 35m gate zone generate `PalaceEntryRequest`; unauthorized mortals crossing the 95m inner radius are arrested by Palace Knights.

---

## Gaia v4.0 Sprint 3: 5 Equidistant Gated Cities & Modular Housing
**Status:** **COMPLETE**

### Deliverables
- `sim_core/world/city_layout.py`:
  - Sylvanor (Elf, `1150m, 0m`), Aurelia (Human, `355m, 1094m`), Fenris Hold (Beasthuman, `-930m, 676m`), Malakor (Demon, `-930m, -676m`), Drakonis Spire (Dragon, `355m, -1094m`).
  - Central God-Mother Palaces, `240m` perimeter curtain walls, 4 gates each, and organized street grids.
  - Modular walk-in seed housing (Tier 1 Cottages, Tier 2 Townhouses, Tier 3 Manors, and commercial shops) with deeded `16×16m` parcels.
- `godot_client/scripts/cities_and_buildings_manager.gd`: Spawns cities and buildings, distance-streams modular houses outside 650m for 60 FPS performance, and updates night emissive windows/lanterns.
- `tests/test_five_cities_and_building_sync.py`: Verifies layout, building counts, and WebSocket synchronization.

### Acceptance Milestones
- [x] All 5 Ring 1 cities spawn at exact coordinates with matching racial architectural styles and curtain walls.
- [x] City buildings synchronize cleanly over WebSocket (`BUILDING_SYNC` and `BUILDING_UPDATE`).

---

## Gaia v4.0 Sprint 4: 4-Pillar Hybrid Cognitive Core
**Status:** **COMPLETE**

### Deliverables
- `sim_core/brains/hierarchical_brain.py`: 3-Tier Hierarchical Neural Brain composing `SharedLivingNet` (Tier 1), `ProfessionNetRegistry` (Tier 2, 10 professions Lv. 1–10), and `BatchedAgentSelfNet` (Tier 3, 2,048-slab GRU memory).
- `sim_core/brains/personality.py`: 10-D `PersonalityVector` and dynamic `MoodState` modulating action logits.
- `sim_core/brains/memory_rag.py`: Grounded `MemoryRAGIndex` with strict `known_books` information asymmetry.
- `sim_core/brains/consolidation.py`: `SleepCycleConsolidator` stabilizing neural plasticity during sleep.
- `sim_core/society/speech_acts.py`: 8 Semantic Speech Acts (`GREET`, `WARN_PRICE_SPIKE`, `TRADE_OFFER`, `SHARE_BOOK_LORE`, `REPORT_CRIME`, `PRAYER_CALL`, `COURT`, `POLITICAL_DEBATE`).
- `tests/test_hybrid_cognitive_core.py`: Benchmarks 10,000 agents in < 25 ms/step on CPU and verifies RAG asymmetry.

### Acceptance Milestones
- [x] 10,000-agent batched forward pass across 3 tiers executes in **~15.0 ms/step** on CPU with zero NaNs.
- [x] Mortals cannot utilize library knowledge unless they or their mentors have read the corresponding book.
- [x] Personality traits and mood dynamically bias action logit distributions without corrupting baseline survival.

---

## Gaia v4.0 Sprint 5: Autonomous Deities, Semantic Speech Acts & God Console Live Bridge
**Status:** **COMPLETE**

### Deliverables
- `sim_core/divine/autonomy.py`: Autonomous Divine Agenda Engine updating live coordinates, yaw, speeds, activity states, and speech text for all 6 Deities.
- `godot_client/scripts/divine_npcs_manager.gd`: Renders the 6 VRoid deities in the 3D world, interpolating their positions and playing contextual animations.
- `godot_client/scripts/god_camera_controller.gd`: Real `CharacterBody3D` God Avatar with WASD controls, sprint, crouch, flight toggle (`F`), jump, dust particles, and surface-aware footstep audio.
- `godot_client/scripts/ui/dialogue_modal.gd`: Interactive dialogue modal (`E` key) for talking to Deities and Mortals.
- `tests/test_spatial_awareness_speech_and_deity_ai.py` & `tests/test_end_to_end_live_bridge.py`.

### Acceptance Milestones
- [x] All 6 Deities execute autonomous daily schedules and respond to direct God commands (`FOLLOW_GOD`, `RETURN_PALACE`, `CONVENE_COUNCIL`).
- [x] God Avatar navigates the 3D world with full collision physics, flight, and footstep sound effects.

---

## Gaia v4.0 Sprint 5.5: Local LLM Integration (`llama.cpp` + Qwen3.5)
**Status:** **COMPLETE**

### Deliverables
- `sim_core/divine/llm_brain.py`: Async local LLM client targeting OpenAI-compatible `llama-server` running `Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf`.
- Single-slot concurrency lock (`-np 1`), reasoning `<think>` block stripping, JSON schema extraction, and `WorldGoddessCritic` fail-closed validation.
- Grounded deterministic offline fallback generator using live RAG memories, CPI, and personality traits.
- `scripts/verify_live_qwen.py`: Smoke test verifying real GGUF inference via `llama-server`.
- `tests/test_local_llm_integration.py`: Verifies think-tag stripping, JSON parsing, prompt construction, and offline fallback.

### Acceptance Milestones
- [x] Local LLM responses strip `<think>` blocks and parse structured JSON reliably.
- [x] Offline fallback seamlessly activates when `llama-server` is not running, ensuring 100% simulation uptime.

---

## Gaia v4.0 Sprint 6: Knowledge Foundry, Housing Market & Gear Economy
**Status:** **COMPLETE**

### Deliverables
- `knowledge_foundry/`: 10 canonical subject categories, authoring guidelines, schema specifications, and deduplication playbook.
- `sim_core/knowledge/dedupe.py`: 3-Stage Cascaded Deduplication Engine (Stage 0 Schema, Stage 1 Hash/Fact-Key, Stage 2 Lexical 3-Gram Fuzzy $\ge 0.82$, Stage 3 Semantic Vector Cosine $\ge 0.88$ + Conflict Detection).
- `scripts/celestial_ingest.py`: Sandboxed Celestial Lore Harvester distilling raw text into verified JSON packs.
- `scripts/knowledge_review.py` & `scripts/knowledge_merge.py`: Pre-merge review CLI and atomic World Library merge tool.
- `sim_core/society/housing_market.py`: Autonomous home purchases, in-place tier upgrades, probate inheritance cascades, and escheatment.
- `sim_core/society/gear_economy.py`: Crafted outfits, accessories, and tools/weapons with visual socket attachments on mortal rigs.
- `godot_client/scripts/grass_chunk_manager.gd`: Dynamic 85m ring MultiMeshInstance3D 3D grass system with `grass_sway.gdshader`.
- `tests/test_housing_gear_frontier_and_harvester.py` & `tests/test_knowledge_foundry_dedupe_and_merge.py`.

### Acceptance Milestones
- [x] 3-Stage deduplication cascade blocks exact and fuzzy duplicates while flagging near-duplicate warnings.
- [x] Housing market executes closed-loop credit purchases, upgrades cottages to manors, and resolves probate.
- [x] Equipped gear renders in visual sockets on mortal rigs inside the Reality Bubble.

---

## ✦ Future / v4.1+ Architectural Ideas

While Gaia v4.0 is feature-complete and verified, the following areas represent promising extensions for v4.1+:

1. **Naval Warfare & Maritime Trade (Ring 3 Expansion):**
   - Coastal dockyards in Ring 1 & Ring 2 settlements.
   - Modular sailing caravels for inter-continental trade across Ring 3 ocean islets.
   - Naval blockade mechanics affecting WTC import tariffs.
2. **Deep Seasonal Microclimates & Catastrophes:**
   - Blizzard drift simulation freezing Ring 2 frontier roads.
   - Volcanic ash plumes from Drakonis Spire and Malakor temporarily reducing crop yields across adjacent quadrants.
   - Dynamic river freezing allowing winter troop marching across frozen waterways.
3. **Multi-God Co-Op Observation (Multi-Client WebSockets):**
   - Multiple spectator God Avatars connecting over WebSocket simultaneously.
   - Shared Divine HUD with synchronized God Console interventions.
4. **VR Client Viewport (Godot OpenXR):**
   - Room-scale God view over the 8km × 8km world using Godot 4.7.2's native OpenXR integration.
   - Hand-tracking gestures for divine blessings, smites, and parcel deed drafting.