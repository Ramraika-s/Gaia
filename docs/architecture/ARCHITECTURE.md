# ARCHITECTURE.md — Unbounded Topology, Cognitive LOD, Godot 4.7.2 Reality Bubble, WebSocket Binary Bridge, Atomic Daily 2PC & Self-Healing 

## 1. High-Level Process Topology
All services run locally on Fedora Linux 45 (KDE Plasma on Wayland) bound strictly to `127.0.0.1` (zero public exposure). Moving from Minecraft/Mineflayer to **Godot 4.7.2 (Vulkan)** collapses the architecture into **two lean native processes**:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                 PROCESS 1: PYTHON SIM CORE (UNBOUNDED AGENTS)                │
│  ┌───────────────────────┐   ┌─────────────────────────┐   ┌──────────────┐  │
│  │ Batched World Engine  │◄─►│ Slab-Grown Tensor Brain │   │ God Console  │  │
│  │ • Multi-Tier LOD      │   │ • SharedSkillNet (MLP)  │   │ • Rich CLI   │  │
│  │ • NumPy Spatial Grid  │   │ • 2048-Slab torch.bmm   │   │ • Presence   │  │
│  │ • Heightmap (.npy)    │   │   + GRUCell Memory      │   │   Tracker    │  │
│  │ • Reality Bubble Mgr  │   │ • Plasticity Trainer    │   │ • Speed Ctrl │  │
│  │ • Self-Healing Solver │   └─────────────────────────┘   └───────┬──────┘  │
│  └──────────┬────────────┘                                         │         │
│             │ CommitProposal / Prayers / Sister Council            │         │
│             ▼                                                      ▼         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │     WORLD GODDESS CRITIC (Wife of God) + 4 RACIAL GOD-MOTHERS          │  │
│  │  • Atomic End-of-Day 2PC (SQLite WAL + SHA-256 .pt/.db + manifest.json │  │
│  │    + data/god_ledger/day_XXXXX.md)  ◄── DuckDB (Read-Only Analytics)   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Native WebSocket (ws://127.0.0.1:8765)
                                       │ • JSON: Events, Prayers, UI, Morphs, Edits
                                       │ • Binary PackedFloat32Array: 10k+ Positions
┌──────────────────────────────────────▼───────────────────────────────────────┐
│        PROCESS 2: GODOT 4.7.2 CLIENT (VULKAN — RADEON 780M TUNED)            │
│  • Terrain3D v1.1.0 + Sky3D v2.1 + Global Toon/Season Shaders                │
│  • 3D Reality Bubble: 60–120 Pre-Allocated Pooled Mortals (~120–160m)        │
│  • Unified Orbital God Map: MultiMeshInstance3D (10,000+ in 1 draw call)     │
│  • 6 Bespoke VRoid Divine Heroes + Dragon Metamorphosis Toggle               │
│  • Diegetic SubViewport Signs (UPDATE_ONCE) + 2D Library Modal + Divine HUD  │
└──────────────────────────────────────▲───────────────────────────────────────┘
                                       │ Hybrid Free-Fly RTS / 3rd-Person Avatar
                            [YOU: Visible "God" Avatar]
```

> **Single Source of Truth Rule:** Python owns 100% of live simulation state in RAM during the game day, and the **World Goddess** owns the sole SQLite writer. **Godot NEVER opens or writes directly to `data/civilization.db`.** All in-world edits (such as editing a World Library book in Godot's 2D modal or freezing the WTC) travel over WebSocket to Python, mutate RAM immediately (`bypass_god_check=True`), and persist atomically at end-of-day.

---

## 2. Unbounded Population & Multi-Tier Cognitive LOD
There is **no hard `MAX_AGENTS` ceiling**. Population grows and contracts naturally via food supply, winter scarcity, housing/parcels, injury/illness, racial lifespans, and warfare:
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
The `10,000m × 10,000m` world is experienced seamlessly inside **one Godot 4.7.2 application**—eliminating the need for a separate browser map or Java server:

### 3.1 Live 3D Reality Bubble (`60–120` Pooled Mortals)
- **Hybrid God Camera & Avatar:** Fly freely in RTS mode or drop down into 3rd-person `god_avatar.glb` (`is_god = true`). Godot streams the God Avatar/Camera `(x, y, z)` to Python at `10 Hz`.
- **Materialization Hysteresis (Prevents Thrashing):**
  - **Materialize (`POOL_ASSIGN`):** Living agents within **`120–160m`** (configurable, default `140m`) of God's camera are assigned to Godot's **pre-allocated pool of `120` mortal scenes** (prioritized by proximity, active combat/metamorphosis, and divine interaction). Never call `instantiate()` / `queue_free()` mid-flight.
  - **Dematerialize (`POOL_RELEASE`):** Agents exceeding **`185m`** (hysteresis buffer) return to `visible = false` in the pool and continue seamlessly in Python tensor simulation.
- **Radeon 780M Animation LOD:**
  - `0–45m`: Full `60 Hz` skeletal animation & particle updates.
  - `45–100m`: Throttled to `20 Hz`.
  - `100–160m`: Throttled to `10 Hz`.
- **Dragon Metamorphosis & Biological Scaling:**
  - Every mortal rig applies deterministic bone scaling by `stage` (`INFANT 0.45x`, `CHILD 0.75x`, `ADULT 1.0x`, `ELDER 0.94x`) and `RaceProfile` (`ELF 1.06x`, `DWARF 0.75x H / 1.15x W`, `BARBARIAN 1.18x H / 1.25x W`).
  - Dragon pool nodes parent both `base_dragon_humanoid` and `base_dragon_true` (`3.8x`) under a shared `AgentRoot`; metamorphosis simply toggles visibility, fires `MetamorphosisBurst` particles, and swaps the collision capsule with zero frame stutter.

### 3.2 Unified Orbital God Map (`MultiMeshInstance3D`)
- When God zooms the RTS camera above **`250m` altitude**, Godot smoothly cross-fades the 3D Reality Bubble into the **Orbital God Map**:
  - A single **`MultiMeshInstance3D`** renders all **10,000+ living agents** as color-coded dots/banners (filterable by Race, Nation, Religion, or Life Stage) in **1 draw call** driven directly by Python's binary position stream.
  - Ground shader overlays display explicit `16×16m` parcel borders, Nation territories, active war fronts, WTC trade routes, and CPI inflation heatmaps.
  - **Click-to-Swoop:** Clicking any city, altar beacon, or agent smoothly descends the camera straight back into the 3D Reality Bubble at that coordinate.

---

## 4. Python ↔ Godot WebSocket Bridge (`sim_core/bridge/godot_ws_bridge.py`)
Godot's built-in `WebSocketPeer` connects directly to Python's `websockets` server on `ws://127.0.0.1:8765`—requiring zero C++ GDExtension compilation on Fedora 45. Traffic is split into **two frame types** for maximum performance:

### 4.1 Raw Binary Frames (`PackedFloat32Array` — High Frequency)
GDScript decodes raw float buffers in microseconds without pure-GDScript MessagePack overhead.
- **Orbital / Bulk Position Frame (Python → Godot, `5–10 Hz`):**
  - Contiguous `float32` stride of `6` floats per active agent: `[slot_id, x, y, z, yaw, packed_flags]` (where `packed_flags` bit-packs `race`, `stage`, `crying`, `dragon_true_form`, `in_combat`, `praying`).
  - At 10,000 agents, one frame is `240 KB` over loopback (`< 0.5 ms` transfer & decode).

### 4.2 JSON Control & Event Frames (Low Frequency)
Used for discrete structured payloads:
- **Python → Godot:**
  - `BUBBLE_SYNC`: Metadata for newly pooled agents (`agent_id`, `display_name`, `race`, `sub_lineage`, `gender`, `stage`, `hsv_palette`, `cloth_colors`, `attachments`, `action_anim`, `injured`, `illness`, `crying`).
  - `WORLD_TIME_WEATHER`: Current `day`, `time_of_day (0..24000)`, `season_progress (0..4)`, and weather state for `Sky3D v2.1` + global shader uniform.
  - `SIGN_UPDATE`: Triggers `UPDATE_ONCE` redraw on WTC Live Price/CPI signs and Courthouse Wanted Notices.
  - `ALTAR_BEACON`: Spawns/clears a vertical light pillar (`GPUParticles3D`) at an active congregational altar.
  - `DIVINE_HUD_MESSAGE`: Live messages from the **World Goddess**, **4 Racial God-Mothers**, Sister Council summaries, and `ErrorHealer` alerts.
- **Godot → Python:**
  - `GOD_STATE`: God Avatar/Camera `(x, y, z)`, altitude, `avatar_visible`, and `presence_active = true`.
  - `GOD_LIBRARY_EDIT`: Submitted from Godot's 2D `TextEdit` modal; Python applies it in RAM (`bypass_god_check=True`) and queues for atomic end-of-day commit.
  - `GOD_COMMAND`: In-world divine actions (`bless`, `smite`, `wtc freeze`, `wtc tariff`, `decree`, `name_deity`, `speed`).

---

## 5. Terrain3D Heightmap Sync & NumPy Spatial Hash Grid (`sim_core/spatial/`)
- **Heightmap Sync (`sim_core/spatial/heightmap.py`):** After sculpting the 4 racial biomes in `Terrain3D v1.1.0`, export the terrain elevation map once as a single float32 array (`data/world_heightmap.npy`, ~4–16 MB in RAM). Python performs $O(1)$ bilinear elevation and slope lookups so distant tensor-simulated agents never walk through cliffs or spawn underground when entering the Reality Bubble. Inside the bubble, Godot snaps materialized rigs to `terrain.data.get_height(pos)`.
- **NumPy Spatial Hash Grid (`sim_core/spatial/hash_grid.py`):**
  - Partitions the `10,000m × 10,000m` world into **`16m × 16m` logical parcels** (`cx = floor(x / 16)`, `cz = floor(z / 16)`, `parcel_id = f"{cx}_{cz}"`), aligning 1:1 with SQLite land deeds, explicit non-overlapping `VILLAGE`/`TOWN`/`CITY`/`STATE`/`NATION` borders, and Godot's ground border decal/shader overlay.
  - Updated each tick in `< 1 ms`. Neighbor search, crying-infant caretaker detection, parcel/border lookup, witness detection, and Reality Bubble candidate selection all execute in **$O(1)$ average time**.

---

## 6. In-World Interactive Institutions & Visual Hooks (`godot_client/`)
Detailed asset specs live in `docs/architecture/GODOT_CLIENT_AND_ASSETS_SPEC.md`. Architecturally:
- **World Trade Centre (WTC) & Courthouse Signs:** Rendered diegetically onto 3D hanging signs via `SubViewport` → `ViewportTexture` with `render_target_update_mode = UPDATE_ONCE`. Redrawn **only** when Python emits a `SIGN_UPDATE` civic tick packet.
- **World Library (RBAC Enforced):** Clicking a Library Lectern or Bookshelf opens a clean 2D Godot `TextEdit` modal populated from Python RAM. Only `God` can directly save edits via `GOD_LIBRARY_EDIT`; mortal edits must pass `> 50%` consensus of the **Council of Appointed Elders (max 2 Elders per Nation)**.
- **Sky3D Day/Night & Seasonal Sync:** `Sky3D v2.1` syncs to Python's `REAL_SECONDS_PER_GAME_DAY` with a tuned moonlight/ambient floor in `WorldEnvironment` so nights remain clearly readable during 1–2 real-hour days.

---

## 7. Time, Real-Time Day Pacing & Tick Scheduling
Default `REAL_SECONDS_PER_GAME_DAY = 5400`s (1.5 real hours, tunable `3600–7200`s). God Console and Godot HUD support `speed 1x..60x` for fast-forwarding headless or paused-3D simulations.

| Loop | Frequency (at `1x`) | Scope & Latency Target |
| :--- | :--- | :--- |
| **Godot Visual / Render Loop** | 60 FPS (Vulkan) | 60–120 pooled 3D mortals (with Animation LOD) OR 1-draw-call Orbital Map |
| **Batched Tensor Cognitive Tick** | 2 Hz (500 ms) | Tier-0 (2 Hz), Tier-1 (1 Hz), Tier-2 (0.25 Hz) via slab-grown `torch.bmm` + `GRUCell` (~10–15 ms at 10k) |
| **Neural Backprop Batch** | Every 32 sim ticks | Vectorized policy + value + self-prediction + curiosity loss over RAM rollout tensors |
| **Civic, WTC, Divine & Political Tick** | Every 60 sim ticks (~30 s) | WTC order-book clearing, $M/Q$ inflation, Bank interest, Judiciary rulings, Rumor decay, Sister Council checks, `SIGN_UPDATE`, RAM watermark |
| **End-of-Day Atomic Commit (World Goddess)** | Once per Game Day (every 1–2 real hrs) OR clean shutdown | All-or-nothing SQLite WAL transaction + SHA-256 `.pt`/`.db` snapshot + `manifest.json` + `god_ledger/day_XXXXX.md` |
| **Seasonal & Election Check** | Every 7 Game Days (1 Season) / 28 Days (1 Year) | Advance 4-Season cycle (sync `season_progress` uniform); trigger Republic elections & Pope conclaves |

---

## 8. Pure End-of-Day Atomic Persistence (World Goddess), Corruption Rewind & DuckDB Analytics
There is **no 15-minute crash journal** and **no per-tick disk writing**. All live positions, vitals, GRU hidden states, rumors, prayers, sisterly dialogues, and verdicts remain strictly in RAM during the game day.

### 8.1 All-or-Nothing End-of-Day Two-Phase Commit (`sim_core/persistence/checkpoints.py`)
Executed exclusively by the **World Goddess** at the final tick of Game Day $D$ (or on `save` / `shutdown`):
1. **Pause Ticks Briefly (< 20 ms):** Freeze RAM tensors, pending SQLite queue, and `god_ledger_buffer` at exact `(day, tick)`.
2. **Phase 1 — Atomic SQLite WAL Transaction (`data/civilization.db`):**
   - Configured with `journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`.
   - Execute all daily World-Goddess-approved deltas inside a single `BEGIN IMMEDIATE ... COMMIT` block. If **any** error occurs, execute `ROLLBACK` immediately (zero partial corruption) and route to `ErrorHealer`.
3. **Phase 2 — Synchronized Daily Files + SHA-256 Checksums:**
   - Write `data/checkpoints/day_{D:05d}.pt.tmp` (`SharedSkillNet`, slab-grown `BatchedAgentSelfNet` weights + `H` + `free_slots`, RNG states, `money_supply_m`, `world_bank_reserve`).
   - Create synchronized SQLite online backup `data/checkpoints/day_{D:05d}.db.tmp`.
   - Write `data/god_ledger/day_{D:05d}.md.tmp` and update `data/god_ledger/latest.md.tmp`.
   - Compute **SHA-256** hashes for `.db.tmp` and `.pt.tmp`, call `os.fsync()`, and atomically `os.replace()` all `.tmp` files to final paths.
4. **Phase 3 — Commit Manifest Last (`data/checkpoints/manifest.json`):**
   - Atomically write `manifest.json` (`{day, tick, season, db_path, db_sha256, pt_path, pt_sha256, ledger_path, status: "VERIFIED"}`) **only after Phases 1–2 succeed**. Retain the last `7` verified daily snapshots.

### 8.2 Automatic Corruption Rewind & DuckDB Read-Only Analytics
- **Startup Rewind:** On startup (`resume`), recompute SHA-256 of the latest `.db` and `.pt` against `manifest.json`. If missing, truncated, or mismatched, **automatically rewind** to the most recent `VERIFIED` daily snapshot, restore both `.db` and `.pt`, and log a `[CORRUPTION_REWIND]` alert to the World Goddess, God Console, and God Ledger.
- **DuckDB Read-Only Analytics:** Run multi-generational historical queries without locking the live writer:
  ```sql
  ATTACH 'data/civilization.db' AS civ (TYPE sqlite, READ_ONLY);
  SELECT race, season, cause, COUNT(*) FROM civ.fatalities GROUP BY race, season, cause;
  ```

---

## 9. Self-Healing Error Solver (`sim_core/resilience/healer.py`) & God Ledger Pipeline
### 9.1 Intelligent Error Recovery (Supervised by the World Goddess)
Every tick stage, neural batch, double-entry transfer, WebSocket frame, and end-of-day commit is wrapped in structured `try/except` boundaries routed to `ErrorHealer.handle(exc, context)`:

| Fault Class | Automated Self-Healing Recovery |
| :--- | :--- |
| `TENSOR_NAN_INF` | Restore only the affected slot(s) from the last verified daily `.pt` snapshot (or parent/race mean), reset `H[slot] = 0`, log `SELF_HEALED_TENSOR`. |
| `ECONOMY_CONSERVATION_DRIFT` | Roll back offending transfer via double-entry journal, verify closed-loop sum, return `FAILURE` to actor. |
| `COORD_OUT_OF_BOUNDS` | Clamp `(x, y, z)` to nearest valid parcel inside world border and re-query `heightmap.npy` elevation. |
| `WS_BRIDGE_DROP` | Retry/accept Godot reconnect cleanly; pause Reality Bubble streaming while keeping Python RAM simulation intact. |
| `SQLITE_COMMIT_FAIL` | Roll back entire daily transaction; retry once after lock check; preserve RAM queue and alert God via World Goddess. |
| `AGENT_REPEAT_FAULT` | Quarantine the single faulty slot (`quarantined[slot] = True`, release from Godot pool) so one agent never crashes the civilization. |

- **Escalation Guard:** If the **exact same `fault_class` triggers more than 5 times in one game day**, stop silently patching it, pause only the affected subsystem, and emit a `[CRITICAL]` alert to the World Goddess, Godot Divine HUD / CLI (if active), and `god_ledger`.

### 9.2 God Presence Tracker & Divine Communication Pipeline (`sim_core/divine/god_ledger.py`)
- **Strict Routing:** Mortals **cannot** pray directly to God. Mortals pray to their **Racial God-Mother** or the **World Goddess**. God receives messages **only** from the **World Goddess** and the **4 Racial God-Mothers** (including escalated mortal prayers/gratitude, congregational altar calls spoken by a **Prayer Head**, Inter-Sister Council discussions, and `ErrorHealer` alerts).
- **Active Mode (God connected in Godot 4.7.2 or Rich CLI):** Messages stream **in real time** to the In-Godot Divine Family HUD and God Terminal while also buffering in RAM.
- **Away Mode (AFK):** Everything buffers strictly in RAM during the game day and is flushed atomically by the **World Goddess** at end-of-day into `data/god_ledger/day_XXXXX.md` + `latest.md` so God can review every divine report, sisterly conversation, milestone, and auto-healed anomaly upon returning.