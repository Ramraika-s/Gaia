# ARCHITECTURE.md — Unbounded Topology, Cognitive LOD, Godot 4.7.2 Reality Bubble, WebSocket Binary Bridge, Atomic Daily 2PC & Self-Healing

## 1. High-Level Process Topology
All services run locally on Fedora Linux 45 (KDE Plasma on Wayland) bound strictly to `127.0.0.1` (zero public exposure). The architecture is structured into **two lean native processes** (with an optional third process for local LLM inference):

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PROCESS 1: PYTHON SIMULATION CORE (sim_core/)                   │
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                    4-PILLAR HYBRID COGNITIVE CORE                              │   │
│   │  • Pillar 1: 3-Tier Hierarchical Neural Brain                                 │   │
│   │    - Tier 1: SharedLivingNet (Universal baseline survival & reflex MLP)        │   │
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
│   │  • DuckDB (Read-Only Analytical Attach)                                        │   │
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

> **Single Source of Truth Rule:** Python owns 100% of live simulation state in RAM during the game day, and the **World Goddess** owns the sole SQLite writer. **Godot NEVER opens or writes directly to `data/civilization.db`.** All in-world edits (such as editing a World Library book in Godot's 2D modal or freezing the WTC) travel over WebSocket to Python, mutate RAM immediately (`bypass_god_check=True`), and persist atomically at end-of-day.

---

## 2. Unbounded Population & Multi-Tier Cognitive LOD
There is **no hard `MAX_AGENTS` ceiling**. Population grows and contracts naturally via food supply, winter scarcity, housing availability, injury/illness, racial lifespans, and warfare:
- **Dynamic 2,048-Slot Slab Allocation:** `BatchedAgentSelfNet` (`W_ih`, `b_ih`, `W_hh`, `b_hh`, `W_out`, `b_out`, `H`) and all NumPy state arrays grow dynamically in slabs of **`2,048` slots** via `torch.cat` / `np.concatenate` whenever `free_slots` is empty.
- **Soft RAM Watermark (`psutil`):** Checked once per civic tick. If host RAM exceeds **75%**, the engine emits a `[RAM_WATERMARK]` alert to the World Goddess, God Console, Godot Divine HUD, and God Ledger without crashing or blocking births.
- **Multi-Tier Cognitive LOD Scheduler:** Keeps tick latency smooth at 10,000–50,000+ agents:

| LOD Tier | Agent Criteria | Forward-Pass Frequency | Notes |
| :--- | :--- | :--- | :--- |
| **Tier 0 (Full 3D)** | Inside Reality Bubble (`<= 160m` of God) | `2 Hz` (every tick) | Synchronized with pooled 3D rigged Godot mortals |
| **Tier 1 (Active Macro)** | Distant awake agents (working, traveling, trading, fighting) | `1 Hz` (every 2nd tick) | Staggered even/odd slot batches |
| **Tier 2 (Dormant)** | Distant sleeping, resting, or sheltered idle agents | `0.25 Hz` (every 8th tick) | Wakes immediately to Tier 1 on threat/distress/event |

---

## 3. Unified 3D Reality Bubble & Orbital God Map (Godot 4.7.2)
The `8,000m × 8,000m` concentric world is experienced seamlessly inside **one Godot 4.7.2 application**:

### 3.1 Live 3D Reality Bubble (`60–120` Pooled Mortals)
- **CharacterBody3D God Avatar & Camera:** Fly freely in RTS mode or drop down into 3rd-person `god_avatar.vrm` (`is_god = true`). Godot streams the God Avatar/Camera `(x, y, z)` to Python at `10 Hz`.
- **Materialization Hysteresis (Prevents Thrashing):**
  - **Materialize (`POOL_ASSIGN`):** Living agents within **`120–160m`** (default `140m`) of God's camera are assigned to Godot's **pre-allocated pool of `120` mortal scenes** (prioritized by proximity, active combat/metamorphosis, and divine interaction). Never call `instantiate()` / `queue_free()` mid-flight.
  - **Dematerialize (`POOL_RELEASE`):** Agents exceeding **`185m`** (hysteresis buffer) return to `visible = false` in the pool and continue seamlessly in Python tensor simulation.
- **Radeon 780M Animation LOD:**
  - `0–45m`: Full `60 Hz` skeletal animation & particle updates.
  - `45–100m`: Throttled to `20 Hz`.
  - `100–160m`: Throttled to `10 Hz`.
- **Dragon Metamorphosis & Biological Scaling:**
  - Every mortal rig applies deterministic bone scaling by `stage` (`INFANT 0.45x`, `CHILD 0.75x`, `ADULT 1.0x`, `ELDER 0.94x`) and `RaceProfile`.
  - Dragon pool nodes parent both `base_dragon_humanoid` and `base_dragon_true` (`3.8x`) under a shared root; metamorphosis toggles visibility, fires `MetamorphosisBurst` particles, and swaps the collision capsule with zero frame stutter.

### 3.2 Unified Orbital God Map (`MultiMeshInstance3D`)
- When God zooms the RTS camera above **`250m` altitude**, Godot smoothly cross-fades the 3D Reality Bubble into the **Orbital God Map**:
  - A single **`MultiMeshInstance3D`** renders all **10,000+ living agents** as color-coded dots/banners in **1 draw call** driven directly by Python's binary position stream.
  - Ground shader overlays display explicit `16×16m` parcel borders, Nation territories, active war fronts, WTC trade routes, and CPI inflation heatmaps.
  - **Click-to-Swoop:** Clicking any city, altar beacon, or agent smoothly descends the camera straight back into the 3D Reality Bubble at that coordinate.

---

## 4. Python ↔ Godot WebSocket Bridge (`sim_core/bridge/godot_ws_bridge.py`)
Godot's built-in `WebSocketPeer` connects directly to Python's `websockets` server on `ws://127.0.0.1:8765`:

### 4.1 Raw Binary Frames (`PackedFloat32Array` — High Frequency)
GDScript decodes raw float buffers in microseconds without MessagePack overhead.
- **Orbital / Bulk Position Frame (Python → Godot, `5–10 Hz`):**
  - Contiguous little-endian `float32` stride of `6` floats per active agent (24 bytes/agent):
    `[x, y, z, race_id, stage_id, packed_flags]`
  - Where `packed_flags` bit-packs `crying` (bit 0), `is_oracle` (bit 1), `true_dragon` (bit 2), `injured` (bit 3), `illness` (bit 4), `in_combat` (bit 5), `praying` (bit 6).
  - At 10,000 agents, one frame is `240 KB` over loopback (`< 0.5 ms` transfer & decode).

### 4.2 JSON Control & Event Frames (Low Frequency)
Used for discrete structured payloads:
- **Python → Godot:**
  - `BUBBLE_SYNC`: Metadata for newly pooled agents (`agent_id`, `display_name`, `race`, `sub_lineage`, `gender`, `stage`, `hsv_palette`, `cloth_colors`, `attachments`, `equipped_gear`, `short_utterance`, `crying`).
  - `DEITY_SYNC`: Live coordinates, yaw, speeds, activity states, and speech text for all 6 Deities.
  - `BUILDING_SYNC` / `BUILDING_UPDATE`: Cities, palaces, curtain walls, gates, and modular houses.
  - `BOOK_STATE_SYNC`: World Library entries, proposals, and Divine Codex records.
  - `WORLD_TIME_WEATHER`: Day, clock, season progress, and regional weather cell details.
  - `SIGN_UPDATE`: WTC commodity prices, Fisher CPI, and Courthouse docket updates.
  - `ALTAR_BEACON`: Vertical light pillar projection for active congregational prayers.
  - `DIVINE_HUD_MESSAGE`: Alerts from World Goddess, 5 God-Mothers, Sister Councils, and Healer.
  - `PALACE_ENTRY_REQUEST`: Mortal petitions at the Acropolis Main Gate.
  - `DIALOGUE_RESPONSE`: Deities and mortals replying to God conversations.
- **Godot → Python:**
  - `CLIENT_HANDSHAKE`: Initial client connection and version handshake.
  - `GOD_STATE`: God Avatar `(x, y, z)`, presence status, and camera mode.
  - `GOD_COMMAND`: Direct divine commands (`FOLLOW_GOD`, `RETURN_PALACE`, `CONVENE_COUNCIL`, `SMITE`, `BLESS`).
  - `GOD_LIBRARY_EDIT`: Direct World Library creation or amendment.
  - `GOD_CODEX_EDIT` / `GOD_CODEX_APPROVE` / `GOD_CODEX_REJECT`: Divine Codex governance actions.
  - `GOD_PALACE_DECISION`: Decisions granting, denying, or escorting mortal gate petitioners.
  - `DIALOGUE_REQUEST`: Interactive player dialogue targeting Deities or Mortals.

---

## 5. Persistence Guarantee: End-of-Day Two-Phase Commit (`sim_core/persistence/`)
Gaia enforces a **Pure End-of-Day SSD Protection Rule**:
- **Zero per-tick disk writes** and zero mid-day SQLite commits during the 1–2 real-hour game day.
- At day end (or graceful shutdown), the **World Goddess** executes an all-or-nothing atomic Two-Phase Commit:
  1. `BEGIN IMMEDIATE` on SQLite WAL database (`data/civilization.db`).
  2. Write PyTorch neural tensors (`day_XXXXX.pt`).
  3. Write daily God Ledger (`data/god_ledger/day_XXXXX.md`).
  4. Compute SHA-256 digests and write `manifest.json` last.
  5. SQLite `COMMIT` (full `ROLLBACK` on any error).
- On boot, the engine verifies SHA-256 hashes against `manifest.json`. If corrupted, it automatically rewinds to the prior verified snapshot.

---

## 6. Self-Healing Error Solver (`sim_core/resilience/healer.py`)
- Traps tensor `NaN`/`Inf`, credit conservation drift, out-of-bounds coordinates, and WebSocket drops without crashing.
- **5-Fault Escalation Guard:** If the exact same `fault_class` occurs **more than 5 times in a single game day**, the healer pauses the affected subsystem and emits a `[CRITICAL]` alert to the World Goddess and God Ledger.