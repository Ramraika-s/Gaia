# Gaia — Persistent Unbounded Multi-Race AI Civilization Engine

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/badge/toolchain-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Godot 4.7.2](https://img.shields.io/badge/godot-4.7.2-478cbf.svg)](https://godotengine.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/pytest-109%20passed-success.svg)](tests/)

**Gaia v4.0** is a persistent, local-first, stylized anime-fantasy AI civilization simulation with **no hard population cap**, scaling organically from initial founders to **10,000+ autonomous neural-network agents** across **5 distinct races** (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN` with 4 sub-lineages, and `DEMON`) and **2 biological genders** (`BOY` / `GIRL`).

The entire civilization runs natively on **Fedora Linux 45** (KDE Plasma on Wayland) tuned for the **AMD Ryzen 7 8840HS** CPU and **Radeon 780M** iGPU (32GB DDR5 RAM). It pairs a high-throughput Python simulation core with a stunning **Godot 4.7.2 (Forward+ Vulkan)** 3D client connected over an ultra-low-latency WebSocket bridge (`ws://127.0.0.1:8765`).

---

## ✦ System Architecture & Topology

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PROCESS 1: PYTHON SIMULATION CORE (sim_core/)                   │
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                    4-PILLAR HYBRID COGNITIVE CORE                              │   │
│   │  • Pillar 1: 3-Tier Hierarchical Neural Brain                                 │   │
│   │    - Tier 1: SharedLivingNet (Universal survival & reflex MLP)                 │   │
│   │    - Tier 2: ProfessionNetRegistry (10 professions Lv. 1-10 + book mechanics)  │   │
│   │    - Tier 3: BatchedAgentSelfNet (2048-slab torch.bmm + GRUCell working memory)│   │
│   │  • Pillar 2: 8 Semantic Speech Acts (GREET, WARN_PRICE_SPIKE, SHARE_BOOK...)   │   │
│   │  • Pillar 3: 10-D PersonalityVector & MoodState Action Logit Modulators        │   │
│   │  • Pillar 4: Grounded MemoryRAGIndex (Strict known_books Asymmetry)            │   │
│   │             + SleepCycleConsolidator                                           │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                           │                                            │
│   ┌────────────────────────┐  ┌───────────▼───────────┐  ┌─────────────────────────┐   │
│   │ Closed-Loop Economy    │  │ Divine Family Engine  │  │ Two-Book Governance     │   │
│   │ • World Bank (issuer)  │  │ • 6 Autonomous Deities│  │ • World Library         │   │
│   │ • WTC Fisher CPI       │  │ • Sister Councils     │  │   (Mortal Scholarship)  │   │
│   │ • HousingMarketEngine  │  │ • Divine Agenda Engine│  │ • Divine Codex          │   │
│   │ • GearEconomy          │  │ • Optional llama.cpp  │  │   (Decrees & Overrides) │   │
│   └────────────────────────┘  └───────────┬───────────┘  └─────────────────────────┘   │
│                                           │                                            │
│   ┌───────────────────────────────────────▼────────────────────────────────────────┐   │
│   │                 WORLD GODDESS CRITIC & PERSISTENCE GUARANTEE                   │   │
│   │  • RBAC Validation Matrix & CriticVerdict Emitter                              │   │
│   │  • ErrorHealer (Self-Healing Solver with 5-faults/day escalation guard)        │   │
│   │  • Atomic End-of-Day 2PC (SQLite WAL + SHA-256 .pt/.db + manifest.json)        │   │
│   │  • God Ledger Pipeline (data/god_ledger/day_XXXXX.md + latest.md)              │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ WebSocket (ws://127.0.0.1:8765)
                                            │ • Binary PackedFloat32Array (24 B/agent)
                                            │ • Discrete JSON Sync Events & UI Modals
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                    PROCESS 2: GODOT 4.7.2 3D CLIENT (godot_client/)                    │
│                                                                                        │
│  • Concentric 8km × 8km World: Ring 0 Acropolis, Ring 1 Cities, Ring 2 Frontier        │
│  • TerrainHeightSampler: 1024×1024 HeightMapShape3D Physics Parity (0.00m error)      │
│  • GrassChunkManager: Dynamic 85m Ring MultiMeshInstance3D Wind Sway Foliage           │
│  • 3D Reality Bubble: 60–120 Pooled Rigs, Zero-T-Pose HumanoidAnimator & Visual Sockets│
│  • Orbital God Map: MultiMeshInstance3D 10,000+ Agents in 1 Draw Call (> 250m)         │
│  • CharacterBody3D God Avatar: WASD, Sprint, Crouch, Flight [F], Jump, Audio Footsteps │
│  • UI Modals: TwoBookModal [L], DialogueModal [E], GodConsoleOverlay [` / F1], HUD     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ✦ Key Systems & Features

### 1. The 5 Races & Biology
- **5 Playable Races:** `HUMAN` (adaptive, 1.0x lifespan, rapid learning), `ELF` (ancient, 3.0x lifespan, sylvan crafts), `DRAGON` (apex, 6.0x lifespan, humanoid default with provoked `TRUE_DRAGON` metamorphosis), `BEASTHUMAN` (umbrella race with `CAT_KIN`, `DWARF`, `WOLF_KIN`, and `BARBARIAN`/`BEAR_KIN` sub-lineages), and `DEMON` (volcanic crafters, 2.8x lifespan, generational Dragon deterrence, out-group prior).
- **Strict Binary Biological Gender:** Exactly `BOY` and `GIRL`.
- **Cross-Species Mating:** Different species may mate in humanoid forms with **50% conception chance**, **60% birth survival**, and mother-race gestation duration (`1.2` to `7.0` game days).
- **Age-10 Mixed-Race Choice:** Mixed-race children remain uncommitted until biological age 10 (`3.33 * L` game days), when they dedicate to one parental God-Mother; ties escalate to the World Goddess.
- **Root-Cause Crying:** Infants cry when `distress >= 0.45` from real hunger, injury, cold, or caretaker absence; parents comfort them gradually (`COMFORT_OR_CARE_CHILD`) with zero magic mute buttons.

### 2. The 4-Pillar Hybrid Cognitive Core
1. **3-Tier Hierarchical Neural Brain:**
   - **Tier 1 (`SharedLivingNet`):** Universal physical survival, foraging, and reflex baseline MLP.
   - **Tier 2 (`ProfessionNetRegistry`):** 10 distinct professions (`KNIGHT`, `CITY_GUARD`, `FARMER`, `MERCHANT`, `BLACKSMITH`, `BUILDER`, `SCHOLAR`, `CLERIC`, `HUNTER`, `CITIZEN`) scaling from Apprentice (Lv. 1) to Grandmaster (Lv. 10) driven by book knowledge.
   - **Tier 3 (`BatchedAgentSelfNet`):** Contiguous `2,048`-slot dynamically grown PyTorch slab tensors (`torch.bmm` + manual `GRUCell` working memory, executing 10,000 agents in **~15.0 ms** on CPU with **under 235 MB RAM**).
2. **8 Semantic Speech Acts:** `GREET`, `WARN_PRICE_SPIKE`, `TRADE_OFFER`, `SHARE_BOOK_LORE`, `REPORT_CRIME`, `PRAYER_CALL`, `COURT`, `POLITICAL_DEBATE` over physical 8m acoustic radius with short diegetic utterances.
3. **10-D Personality & Mood:** `caution`, `sociability`, `ambition`, `loyalty`, `rule_respect`, `faith_devotion`, `curiosity`, `aggression`, `frugality`, `compassion` coupled with dynamic `MoodState` (`joy`, `anger`, `fear`, `gloom`, `calm`) modulating action logits.
4. **Grounded Memory RAG & Consolidation:** `MemoryRAGIndex` enforcing strict `known_books` information asymmetry (mortals only know books they or their mentors read), paired with `SleepCycleConsolidator` stabilizing neural plasticity during sleep.

### 3. Concentric 4-Ring World Geography (`8km × 8km`)
- **Ring 0 — Imperial Acropolis (`r = 0..340m`):**
  - Grand Divine Palace atop the `32m` central plateau (`PALACE_CENTER = (0, 32, 0)`).
  - Main Palace Gate flanked by **Twin Guardian Dragons** (`x = ±12m, y = 32m, z = 38m`) enforcing a 3-state access machine (`BYPASS`, `HALT_AND_REQUEST`, `TRESPASS`/`HOSTILE`) and a 24-Knight Battalion.
  - Outer Imperial Plaza at `24m` hosting the World Library, World Trade Centre, High Courthouse, Grand Cathedral, and World Goddess Sanctum.
- **Ring 1 — Pentagonal Gated Cities (`r = 1,150m`, `72°` spacing):**
  - **Sylvanor** (Elf, `1150m, 0m`), **Aurelia** (Human, `355m, 1094m`), **Fenris Hold** (Beasthuman, `-930m, 676m`), **Malakor** (Demon, `-930m, -676m`), **Drakonis Spire** (Dragon, `355m, -1094m`).
  - Each city features a central God-Mother Palace, `240m` curtain wall, 4 gates, residential streets, and City Guard shifts.
- **Ring 2 — Frontier Wilderness (`r = 1,500..3,300m`):**
  - Open pioneer frontier where mortals build cottages and organically cluster into emergent `VILLAGE`s.
- **Ring 3 — Ocean & Outer Islets (`r = 3,300..4,000m`):**
  - Coastal waters, defensive cliffs, and outer maritime boundary.

### 4. Two-Book Governance & Divine Family Hierarchy
- **Divine Family:**
  - **God (Admin / You):** Bestows names on deities, enters 3D world as visible God Avatar (`is_god = true`), sole unrestricted write authority over `divine_codex` live engine-parameter overrides.
  - **World Goddess (Wife of God):** Global critic (`WorldGoddessCritic`), sole owner of atomic daily 2PC save and `data/god_ledger/day_XXXXX.md`, mediator of her 5 daughters.
  - **5 Racial God-Mothers:** Patron deities governing Ring 1 Palaces, participating in 1-on-1 and 5-Sister Councils, with finite Divine Energy and Non-Aggression Covenant bounds.
- **Two-Book Governance:**
  - **`world_library` (Scholarship):** Mortal proposals pass Council of Appointed Elders (`> 50%`) → 1 God-Mother approval starts 1-day objection window → commits if `< 3` objections; Goddess + 1 Daughter may edit directly; 3/5 Daughters alone may edit directly; God may edit directly anytime.
  - **`divine_codex` (Decrees & Engine Overrides):** God owns sole direct authority. Goddess + 3/5 Daughters may commit text decrees. Parameter overrides must be submitted by Goddess (alone) or 5/5 Daughters to God for approval.

### 5. Closed-Loop Economy, Housing & Gear
- **Double-Entry Credit Conservation:** World Bank is the sole issuer; every credit transfer (`debit(sender)` + `credit(receiver)`) is strictly conserved with **0.000000 credit drift**.
- **WTC Market:** Continuous order-book exchange clearing commodities with Fisher Ideal CPI real inflation tracking ($M_t / Q_t$).
- **Housing Market:** Autonomous home purchases, in-place tier upgrades (Tier 1 Cottage $\rightarrow$ Tier 2 Townhouse $\rightarrow$ Tier 3 Manor), probate inheritance cascades, and escheatment.
- **Gear Economy:** Crafted outfits, tools/weapons (`SWORD`, `HOE`, `PICKAXE`, `HAMMER`, `TOME`), and accessories (`HOOD`, `PAULDRONS`, `LANTERN`) visually equipped on mortal rigs in the Reality Bubble.

### 6. Local LLM Integration (`llama.cpp` + Qwen3.5)
- Optional async local LLM divine brain powered by `Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf` via `llama-server`.
- Strict single-slot lock (`-np 1`), reasoning `<think>` block stripping, structured JSON schema parsing, and `WorldGoddessCritic` fail-closed gating.
- Rich, state-grounded offline fallback generator ensuring the simulation is 100% operational even without a running LLM.

### 7. Knowledge Foundry & Deduplication Pipeline
- Self-contained authoring environment with 10 canonical subject categories.
- 3-Stage Cascaded Deduplication Engine: Stage 0 (Schema & Anti-Anachronism), Stage 1 (Hash & Fact-Key), Stage 2 (Lexical 3-Gram Fuzzy), Stage 3 (Semantic Vector Cosine $\ge 0.88$ + Opposing Mechanical Conflicts).
- Sandboxed **Celestial Lore Harvester** (`scripts/celestial_ingest.py`) distilling raw text into verified JSON packs with automatic archaic phrasing transformation.

---

## ✦ Quick Start

### 1. Prerequisites & Environment Setup
Fedora Linux 45 (or any modern Linux distribution) with Python version management handled strictly via **`uv`**:

```bash
# 1. Clone repository
cd ~/Desktop/Gaia

# 2. Run automated uv setup (pins Python 3.12 & syncs all dependencies)
bash scripts/setup_uv_env.sh

# 3. Verify environment
uv run python --version   # Must output Python 3.12.x
uv run ruff check sim_core tests scripts
uv run pytest --tb=short -q  # Runs all 109 unit & regression tests
```

### 2. Launching the Simulation

#### Option A: Full Live World (Python Core + Godot 4.7.2 Client)
```bash
# Launches Simulation Engine (1,500 initial agents), starts WebSocket bridge,
# auto-detects local llama-server, and opens the Godot 3D client:
uv run python scripts/launch_gaia.py --agents 1500 --speed 1.0
```

#### Option B: Live World with Explicit Offline Fallback (No Local LLM)
```bash
# Explicitly runs with zero LLM overhead using state-grounded deterministic fallback:
uv run python scripts/launch_gaia.py --agents 1500 --no-llm
```

#### Option C: Headless Fast-Forwarding / Testing
```bash
# Runs headlessly without launching the Godot graphical client:
uv run python scripts/launch_gaia.py --agents 1500 --headless --max-ticks 1200 --speed 20.0
```

### 3. Knowledge Foundry Workflow

```bash
# 1. Ingest raw text lore into a staged knowledge pack (offline or with local LLM):
uv run python scripts/celestial_ingest.py \
  --input lore_notes.txt \
  --subject agriculture_and_botany \
  --author "Master Agronomist"

# 2. Audit all staged packs using the 3-Stage Deduplication Engine:
uv run python scripts/knowledge_review.py

# 3. Test merge in dry-run mode (zero database changes):
uv run python scripts/knowledge_merge.py --dry-run

# 4. Atomically merge verified packs into the live World Library:
uv run python scripts/knowledge_merge.py --commit
```

### 4. Running Benchmarks & Soak Tests

```bash
# 10,000-Agent Slab-Grown Neural Tensor Forward-Pass Benchmark (< 25 ms/step on CPU):
uv run python -m sim_core.tools.bench_tensors --agents 10000 --steps 50

# 1,500-Agent 5-Race Headless Soak Test + Double-Entry Conservation & Atomic Rewind Check:
uv run python -m sim_core.tools.soak_test --ticks 600 --agents 1500 --verify-atomic-rewind
```

---

## ✦ In-Game God Avatar & Camera Controls

When the Godot 4.7.2 client is active:

| Key / Input | Action | Mode / Context |
| :--- | :--- | :--- |
| `Tab` | Toggle Camera Mode | Switches between **3rd-Person God Avatar** and **Orbital RTS Mode** |
| `W`, `A`, `S`, `D` | Movement | Avatar moves relative to camera yaw; RTS pans across terrain |
| `Shift` (Hold) | Sprint | Accelerates Avatar walk speed from `8.0 m/s` to `18.0 m/s` |
| `Space` | Jump / Ascend | Ground: Jumps with dust particle VFX; Flight: Ascends vertically |
| `Ctrl` or `C` | Crouch / Descend | Ground: Smooth capsule crouch (`1.1m`); Flight: Descends vertically |
| `F` | Toggle Divine Flight | Toggles flight physics on/off in 3rd-person Avatar mode |
| `Alt` (Hold) | Release Mouse Capture | Unlocks mouse cursor to click on-screen buttons or HUD |
| `Left-Click` | Interact / Recapture | Clicks UI buttons, inspects mortals, or re-captures mouse look |
| `Right-Click` (Hold)| Orbit Camera | Rotates view angle around focus target in Orbital RTS Mode |
| `Mouse Wheel` | Camera Zoom | Zooms spring-arm in 3rd-person (`2.5–15m`) or RTS altitude (`20–800m`) |
| `E` | Context Interaction | Talks to nearby Deity/Mortal ([DialogueModal](godot_client/scripts/ui/dialogue_modal.gd)) or interacts with Library Lectern |
| `L` | Two-Book Governance Modal | Opens [TwoBookModal](godot_client/scripts/ui/two_book_modal.gd) (World Library & Divine Codex tabs) |
| `B` | Toggle Parcel Borders | Toggles visual `16×16m` parcel chunk grid & color-coded polity borders |
| `` ` `` (Backtick) / `F1` | In-Game God Console | Toggles [GodConsoleOverlay](godot_client/scripts/ui/god_console_overlay.gd) command prompt |

---

## ✦ Master Documentation Index

For comprehensive technical specifications, refer to [docs/INDEX.md](docs/INDEX.md):

- [Master Documentation Index](docs/INDEX.md)
- **Architecture:**
  - [System Architecture & Topology](docs/architecture/ARCHITECTURE.md)
  - [Godot 4.7.2 Client & Asset Specification](docs/architecture/GODOT_CLIENT_AND_ASSETS_SPEC.md)
  - [Concentric World Geography & Settlements](docs/architecture/WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md)
  - [4-Pillar Hybrid Cognitive Core & Local LLM Specification](docs/architecture/HYBRID_COGNITIVE_AND_LLM_SPEC.md)
  - [Closed-Loop Economy, Housing & Gear Specification](docs/architecture/ECONOMY_HOUSING_AND_GEAR_SPEC.md)
  - [WebSocket Protocol & Binary Frame Reference](docs/architecture/WEBSOCKET_PROTOCOL_SPEC.md)
- **Simulation:**
  - [Divine Family Hierarchy & Governance](docs/simulation/DIVINE_HIERARCHY_SPEC.md)
  - [Neural Brains, Aging & Lifecycle](docs/simulation/NEURAL_AND_LIFECYCLE_SPEC.md)
  - [Races, Biology & Dragon Metamorphosis](docs/simulation/RACES_AND_BIOLOGY_SPEC.md)
  - [Society, Economy & Two-Book Governance](docs/simulation/SOCIETY_AND_GOVERNANCE_SPEC.md)
- **Data & Persistence:**
  - [Data Schemas, SQLite WAL & World Goddess Critic](docs/data/DATA_SCHEMA_AND_WORLD_GODDESS.md)
- **Roadmap & Guides:**
  - [Implementation Roadmap & Milestones](docs/roadmap/IMPLEMENTATION_ROADMAP.md)
  - [Player & Operator Handbook](docs/guides/PLAYER_AND_OPERATOR_GUIDE.md)
  - [Knowledge Foundry Authoring Rules](knowledge_foundry/AGENTS.md)
  - [Knowledge Deduplication Playbook](knowledge_foundry/DEDUPE_AND_REVIEW_PLAYBOOK.md)
