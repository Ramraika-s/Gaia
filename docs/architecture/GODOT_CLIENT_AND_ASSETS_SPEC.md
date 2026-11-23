# GODOT_CLIENT_AND_ASSETS_SPEC.md — Godot 4.7.2 Renderer, Concentric 8km World, Shaders, VFX/SFX & UI

## 1. Visual Direction & Radeon 780M Performance Budget
The 3D client is built in **Godot 4.7.2 (Vulkan on Fedora Linux 45 / Wayland)** and tuned specifically for the **AMD Radeon 780M iGPU** inside the HP EliteBook 845 G11 (32 GB DDR5 RAM).

- **Visual Style:** **Stylized Anime-Fantasy Hybrid.** Bespoke anime deities created in **VRoid Studio** (via Steam/Proton) share the world with stylized low-poly mortals, creatures, and walk-in architecture from **Quaternius** and **KayKit** (all CC0). A unified lightweight Godot toon/cel-shading spatial shader (`stylized_toon_season.gdshader`) ensures deities and mortals visually belong to the same world.
- **Renderer Defaults:**
  - **Standard Mode:** Godot **Forward+** renderer, **MSAA 2x**, **Shadow Atlas `2048px`**, SDFGI disabled (using lightweight Baked/Dynamic DirectionalLight + ambient sky light).
  - **High-Density Mode:** Switch to Godot **Mobile** renderer if targeting locked `60 FPS` with `150+` simultaneously visible rigged agents.
- **3D Reality Bubble Budget (`60–120` Pooled Mortals):**
  - Materialize `60–120` fully rigged, animated mortals inside a **`120–160m` radius** (default `140m`, dematerialization hysteresis `185m`) around God's hybrid camera (`GodCameraController`).
  - **Strict Node Pooling:** Pre-allocate the `120` mortal rig scenes at startup (`visible = false`) and recycle them via `POOL_ASSIGN` / `POOL_RELEASE`—**never** call `instantiate()` or `queue_free()` mid-flight.
  - **Animation LOD:**
    - `0–45m`: Full `60 Hz` skeletal animation, spring bones, and particle updates.
    - `45–100m`: Throttled to `20 Hz` animation ticks.
    - `100–160m`: Throttled to `10 Hz` animation ticks.
- **Unified Orbital God Map (`MultiMeshInstance3D`):**
  - Zooming the RTS camera above **`250m` altitude** cross-fades the Reality Bubble into an Orbital Planet View rendering **10,000+ living agents** as color-coded dots/banners in **1 draw call** (`MultiMeshInstance3D`), overlaid with `16×16m` parcel borders, Nation territories, war fronts, and CPI inflation heatmaps. Clicking any city, altar beacon, or agent smoothly swoops back down into 3D.

> **Architectural Rule (No Direct SQLite Access):** Godot is strictly a thin viewport and interactive UI client. **Godot must NEVER open or write directly to `data/civilization.db`.** Every in-world edit (World Library modal save, WTC freeze, divine decree) sends a JSON message over WebSocket to Python (`ws://127.0.0.1:8765`), which updates RAM immediately (`bypass_god_check=True`) and commits atomically at end-of-day via the **World Goddess**.

---

## 2. Core Godot 4.7.2 Addons & Shaders

### 2.1 Addons Overview

| Need | Exact Addon / Tool | Source | Role & Tuning Notes |
| :--- | :--- | :--- | :--- |
| **3D Terrain & Foliage** | **Terrain3D v1.1.0** (GDExtension) + Custom `TerrainManager` | Asset Library / `github.com/TokisanGames/Terrain3D` | GPU clipmap heightmap supporting up to 32 texture sets (5 racial biomes × seasonal variants) and foliage instancing. |
| **Dynamic Sky & Seasons** | **Sky3D v2.1** | Asset Library / `github.com/TokisanGames/Sky3D` | Rotating sun, moon phases, Milky Way, clouds, fog, and `TimeOfDay` hooks synced directly to Python's `REAL_SECONDS_PER_GAME_DAY` (1–2 real hours). |
| **Anime VRM & Toon Shader** | **VRM Importer & MToon Shader v2.6.1** | Godot Asset Library (`asset/5222`) | C++ GDExtension importing VRoid `.vrm` deities straight into Godot 4 with spring-bone hair/robe physics and anime MToon shading. |
| **Python ↔ Godot Bridge** | Built-in **`WebSocketPeer`** | Native in Godot 4.7.2 | Connects to Python `websockets` on `ws://127.0.0.1:8765` with zero C++ compilation on Fedora 45. Uses JSON for discrete events/UI and raw binary **`PackedFloat32Array`** frames for 10,000+ positions (24 bytes/agent). |

### 2.2 Custom Shader Pipeline

1. **`shaders/terrain_biome.gdshader`:**
   - Multi-biome procedural terrain texturing across Plains, Forest, Steppe, Basalt/Ashland, and Obsidian Crags.
   - Displaces vertex elevations directly from the `1024×1024` heightmap texture while blending slope-based cliff rock and path textures.
2. **`shaders/water_stylized.gdshader`:**
   - Stylized water surface at `SEA_LEVEL = 0.0m` featuring two-tone depth coloring, shoreline foam contouring, and subtle vertex wave undulations.
3. **`shaders/grass_sway.gdshader`:**
   - Wind sway vertex shader applied to all 3D grass mesh instances driven by wind speed and wind strength uniforms.
4. **`shaders/stylized_toon_season.gdshader`:**
   - Global cel/toon spatial shader with a global `season_progress` uniform (`0.0` Spring $\rightarrow$ `1.0` Summer $\rightarrow$ `2.0` Autumn $\rightarrow$ `3.0` Winter frost) dynamically tinting foliage and terrain.

---

## 3. World Geography & Terrain Heightmap Parity

The world is an **`8,000m × 8,000m`** (`-4000..4000m`, `1024×1024`) concentric 4-ring continent centered at `(0, 0)`:

```text
[-4000, 4000] ───────────────────────────────────────────────────────── [4000, 4000]
│                                                                                  │
│   Ring 3: Outer Ocean & Coastal Islets (r = 3,300m .. 4,000m, Sea Level = 0m)    │
│                                                                                  │
│     Ring 2: Frontier Wilderness (r = 1,500m .. 3,300m, Pioneer Cottages)         │
│                                                                                  │
│       Ring 1: Pentagonal Gated Cities (r = 1,150m, 72° Spacing)                  │
│               • Malakor (Demon, -930, -676)                                      │
│               • Fenris Hold (Beasthuman, -930, 676)                              │
│               • Aurelia (Human, 355, 1094)                                       │
│               • Sylvanor (Elf, 1150, 0)                                          │
│               • Drakonis Spire (Dragon, 355, -1094)                              │
│                                                                                  │
│         Ring 0: Imperial Acropolis (r = 0 .. 340m)                               │
│                 - 32m Palace Plateau: Grand Divine Palace & Twin Dragons         │
│                 - 24m Plaza: World Library, WTC, Courthouse, Cathedral, Sanctum  │
│                                                                                  │
[-4000, -4000] ──────────────────────────────────────────────────────── [4000, -4000]
```

### Heightmap Parity (`godot_client/scripts/terrain_height_sampler.gd`)
- Both Python (`sim_core/spatial/heightmap.py`) and Godot (`terrain_height_sampler.gd`) load the exact same float32 array (`data/world_heightmap.npy`, `1024×1024`).
- Godot constructs a `HeightMapShape3D` matching the exact terrain mesh dimensions, guaranteeing **0.00m elevation discrepancy** between physics raycasts, walking mortals, and distant simulation agents.

---

## 4. 3D Grass Chunk System (`godot_client/scripts/grass_chunk_manager.gd`)

To maintain high visual fidelity on the Radeon 780M without lagging:
- **Camera-Centered Streaming:** Maintains a dynamic ring of `MultiMeshInstance3D` grass chunks within an **`85m` radius** of God Avatar / Camera (`CHUNK_SIZE = 16.0m`, `140 blades/chunk`).
- **Dynamic Terrain Snapping:** Each blade queries `TerrainHeightSampler` to sit flush on displaced ground.
- **Exclusion Zones:** Automatically suppresses grass within Ring 1 city walls, the Acropolis plaza, road networks, and submerged areas (`y < 3.5m`).
- **Material Sharing:** All grass chunks share a single `ShaderMaterial` running `shaders/grass_sway.gdshader`.

---

## 5. Walk-In Architecture, Ring 1 Cities & Acropolis

### 5.1 Ring 0 Imperial Acropolis
- **Grand Divine Palace (`godot_client/scenes/landmarks/grand_divine_palace.tscn`):**
  - Seated on the 32m Acropolis plateau (`PALACE_CENTER = (0, 32, 0)`).
  - Main Palace Gate flanked by **Twin Guardian Dragons** (`x = ±12m, y = 32m, z = 38m`): Sovereign of Ash (Left) and Sovereign of Frost (Right).
  - Enforces a 3-state access machine (`BYPASS`, `HALT_AND_REQUEST`, `TRESPASS`/`HOSTILE`) backed by a 24-Knight Battalion.
- **Institutional Plaza (`y = 24m`, `r = 140..340m`):**
  - **World Library (`world_library.tscn`):** Lecterns open the Two-Book modal [L] for reading and drafting scholarship.
  - **World Trade Centre (`wtc_market.tscn`):** Walk-in trading hall with dynamic 3D hanging price and CPI boards.
  - **High Courthouse (`courthouse.tscn`):** Judicial hall with live criminal docket boards.
  - **Grand Cathedral (`grand_cathedral.tscn`):** Multi-faith sanctuary projecting `AltarPrayerBeacon` light pillars.
  - **World Goddess Sanctum (`world_goddess_sanctum.tscn`):** Circular celestial temple at `(0, 24, 210)`.

### 5.2 Ring 1 Pentagonal Cities & Modular Buildings
- All 5 cities are situated at `r = 1,150m` with `72°` spacing:
  - **Sylvanor** (Elf, `1150, 0`, elevation `28m`)
  - **Aurelia** (Human, `355, 1094`, elevation `18m`)
  - **Fenris Hold** (Beasthuman, `-930, 676`, elevation `24m`)
  - **Malakor** (Demon, `-930, -676`, elevation `42m`)
  - **Drakonis Spire** (Dragon, `355, -1094`, elevation `68m`)
- **Perimeter Walls & Gates:** Each city has a `240m` curtain wall with 4 defensive gatehouses (Imperial Main Gate facing Ring 0, plus 3 cardinal gates).
- **Modular Walk-In Prefabs:**
  - `HOUSE_T1_COTTAGE` (Peasant timber cottage, 150 cr upgrade cost)
  - `HOUSE_T2_TOWNHOUSE` (Two-story stone townhouse, 280 cr upgrade cost)
  - `HOUSE_T3_MANOR` (Spacious noble manor)
  - `SHOP_MARKET`, `SHOP_BLACKSMITH`, `SHOP_TAVERN` (Commercial stalls with walk-in counters)
- **Distance Streaming & Night Emissives (`cities_and_buildings_manager.gd`):**
  - Modular houses and detail props cull beyond `650m` (`HOUSE_STREAMING_DIST_SQ`) for steady 60 FPS.
  - Window materials and street lanterns smoothly interpolate emissive intensity when night falls (`night_factor > 0.3`).

---

## 6. The 7 VRoid Deities & Universal Humanoid Animator

### 6.1 The 7 Divine Hero Models
All 7 deities use bespoke anime models (`.vrm`) exported with VRoid Studio's built-in polygon reduction (~`8,000–12,000` triangles) with spring-bone hair and cloth physics:
1. **God Avatar (`god_avatar.vrm`):** Controlled directly by the player in 3rd-person avatar mode (`CharacterBody3D`, `is_god = true`) with a golden divine aura.
2. **World Goddess (`world_goddess.vrm`):** Cosmic matriarch (`1.15x` scale) in starry white-and-gold celestial robes.
3. **Human God-Mother (`gm_human.vrm`):** Royal blue-and-silver robes with balanced scales.
4. **Elf God-Mother (`gm_elf.vrm`):** Sylvan gown woven with living vines and spirit wisps.
5. **Dragon God-Mother (`gm_dragon.vrm`):** Draconic empress in humanoid form with obsidian horns, wings, and amber eyes.
6. **Beasthuman God-Mother (`gm_beasthuman.vrm`):** Fox/wolf ears and fur-trimmed tribal regalia.
7. **Demon God-Mother (`gm_demon.vrm`):** Infernal matriarch in obsidian/crimson regalia with curved horns and dark wings.

### 6.2 Universal Humanoid Animator (`godot_client/scripts/humanoid_animator.gd`)
To eliminate T-poses across all deity VRMs, Quaternius mortal rigs, and demon/dragon models:
- Caches bone indices across VRM standard humanoid and generic humanoid skeletons.
- Checks for embedded or Universal Animation Library (UAL) animation clips (`IDLE`, `WALK`, `RUN`, `CROUCH`, `JUMP`, `FLY`, `PRAY`, `DIVINE_HOVER`, `CRY`).
- When clips are absent, seamlessly executes **guaranteed procedural sinusoidal bone poses** for walking legs, swinging arms, flying floats, and prayer postures, guaranteeing **zero T-poses in any scene**.

---

## 7. Pooled Reality Bubble Rigs & Equipped Gear Sockets

### 7.1 Mortal Actor Rig (`godot_client/scripts/mortal_actor.gd`)
- Pre-allocated pool of `120` mortal scenes inside `RealityBubbleContainer`.
- Supports all 5 races and 2 genders with stage bone scaling (`INFANT 0.45x`, `CHILD 0.75x`, `ADULT 1.00x`, `ELDER 0.94x`).
- **Dragon Metamorphosis:** Parents both `base_dragon_humanoid.gltf` and `base_dragon_true.glb` under a single root; toggling form triggers `dragon_morph_controller.gd` with zero stutter.
- **Visual Sockets (`GEAR_PROPS_PATHS`):**
  - `SWORD` attached to `RightHand` socket.
  - `HOE`, `PICKAXE`, `HAMMER` attached to tool socket.
  - `TOME` attached to scholar lectern/hand socket.
  - `HOOD` attached to head outfit socket.
  - `PAULDRONS` attached to shoulder armor socket.
  - `LANTERN` attached to belt/hip socket.
- **Emotional & Status VFX:**
  - Crying tears particle emitter (`crying_particles`) + audio player (`crying_audio`) active when `crying == true`.
  - Mortal Oracle celestial aura particles (`oracle_aura_particles`).
  - Twin Dragon terror aura ring (`fear_aura_ring`).
  - Nameplate and diegetic speech bubble labels.

---

## 8. Player Controls & UI Modals

### 8.1 CharacterBody3D God Avatar (`godot_client/scripts/god_camera_controller.gd`)
- **Physics Navigation:** Uses `move_and_slide()` with capsule collision (`radius = 0.4m, height = 1.8m`), real gravity (`22.0 m/s²`), jump velocity (`8.5 m/s`), and surface-aware footstep audio (grass, stone, snow, landing impact).
- **Divine Flight Mode [F]:** Toggles gravity off, enabling smooth vertical flight controls (`Space` to ascend, `Ctrl`/`C` to descend) clamped safely above terrain.
- **Orbital RTS Mode [Tab]:** Cross-fades into an unconstrained overhead RTS camera (`20–800m` zoom) with right-click orbiting and middle-mouse panning.

### 8.2 In-Game UI Modals
1. **`TwoBookModal` [L]:**
   - Tab 1: **World Library** (viewing canonical volumes, search, and authoring new scholarship).
   - Tab 2: **Divine Codex** (viewing decrees, approving/rejecting Sister proposals, and promulgating parameter overrides).
2. **`DialogueModal` [E]:**
   - Context-aware dialogue window with deity/mortal portraits, live mood display, chat history, custom text input, and quick action buttons (`FOLLOW_GOD`, `CONVENE_COUNCIL`, `RETURN_PALACE`, World Status Report).
3. **`GodConsoleOverlay` [`` ` `` / `F1`]:**
   - In-game terminal console executing any Gaia CLI command (`pop`, `status`, `speed 20x`, `bless`, `smite`, `save`, `rewind`) directly over WebSocket.
4. **`DivineHud`:**
   - Persistent top bar showing game day, live clock, WTC CPI, 5-race population breakdown, simulation speed buttons (`Pause`, `1x`, `5x`, `20x`, `60x`), and real-time Sister Council notifications.
5. **`ParcelBorderOverlay` [B]:**
   - Projects color-coded `16×16m` parcel grids and settlement/polity boundary lines onto the terrain mesh.