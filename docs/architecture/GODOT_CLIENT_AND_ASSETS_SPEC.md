# GODOT_CLIENT_AND_ASSETS_SPEC.md — Godot 4.7.2 Renderer, Anime-Fantasy Asset Pipeline, Shaders, VFX/SFX & UI 

## 1. Visual Direction & Radeon 780M Performance Budget
The 3D client is built in **Godot 4.7.2 (Vulkan on Fedora Linux 45 / Wayland)** and tuned specifically for the **AMD Radeon 780M iGPU** inside the HP EliteBook 845 G11 (32 GB DDR5 RAM).

- **Visual Style:** **Stylized Anime-Fantasy Hybrid.** Bespoke anime deities created in **VRoid Studio** (via Steam/Proton) share the world with stylized low-poly mortals, creatures, and walk-in architecture from **Quaternius** and **KayKit** (all CC0). A unified lightweight Godot toon/cel-shading spatial shader ensures deities and mortals visually belong to the same world.
- **Renderer Defaults:**
  - **Standard Mode:** Godot **Forward+** renderer, **MSAA 2x**, **Shadow Atlas `2048px`**, SDFGI disabled (use lightweight Baked/Dynamic DirectionalLight + ambient sky light).
  - **High-Density Mode:** Switch to Godot **Mobile** renderer if targeting locked `60 FPS` with `150+` simultaneously visible rigged agents.
- **3D Reality Bubble Budget (`60–120` Pooled Mortals):**
  - Materialize `60–120` fully rigged, animated mortals inside a **`120–160m` radius** (default `140m`, dematerialization hysteresis `185m`) around God's hybrid camera (free-fly RTS + drop-down 3rd-person `God` Avatar).
  - **Strict Node Pooling:** Pre-allocate the `120` mortal rig scenes at startup (`visible = false`) and recycle them via `POOL_ASSIGN` / `POOL_RELEASE`—**never** call `instantiate()` or `queue_free()` mid-flight.
  - **Animation LOD:**
    - `0–45m`: Full `60 Hz` skeletal animation, spring bones, and particle updates.
    - `45–100m`: Throttled to `20 Hz` animation ticks.
    - `100–160m`: Throttled to `10 Hz` animation ticks.
- **Unified Orbital God Map (`MultiMeshInstance3D`):**
  - Zooming the RTS camera above **`250m` altitude** cross-fades the Reality Bubble into an Orbital Planet View rendering **10,000+ living agents** as color-coded dots/banners in **1 draw call** (`MultiMeshInstance3D`), overlaid with `16×16m` parcel borders, Nation territories, war fronts, and CPI inflation heatmaps. Clicking any city, altar beacon, or agent smoothly swoops back down into 3D.

> **Architectural Rule (No Direct SQLite Access):** Godot is strictly a thin viewport and interactive UI client. **Godot must NEVER open or write directly to `data/civilization.db`.** Every in-world edit (World Library modal save, WTC freeze, divine decree) sends a JSON message over WebSocket to Python (`ws://127.0.0.1:8765`), which updates RAM immediately (`bypass_god_check=True`) and commits atomically at end-of-day via the **World Goddess**.

---

## 2. Core Godot 4.7.2 Addons (All Free / MIT)

| Need | Exact Addon / Tool | Source | Role & Tuning Notes |
| :--- | :--- | :--- | :--- |
| **3D Terrain & Foliage** | **Terrain3D v1.1.0** (GDExtension) | Godot Asset Store / `github.com/TokisanGames/Terrain3D` | GPU clipmap heightmap supporting up to 32 texture sets (4 racial biomes × seasonal variants) and GPU foliage instancing with 10 LODs. |
| **Dynamic Sky & Seasons** | **Sky3D v2.1** | Godot Asset Store / `github.com/TokisanGames/Sky3D` | Rotating sun, moon phases, Milky Way, clouds, fog, and `TimeOfDay` hooks synced directly to Python's `REAL_SECONDS_PER_GAME_DAY` (1–2 real hours). **Required fix:** configure a subtle moonlight/ambient floor in `WorldEnvironment` so nights are never pitch-black. |
| **Anime VRM & Toon Shader** | **VRM Importer & MToon Shader v2.6.1** | Godot Asset Library (`asset/5222`) | C++ GDExtension importing VRoid `.vrm` deities straight into Godot 4 with spring-bone hair/robe physics and anime MToon shading. |
| **Python ↔ Godot Bridge** | Built-in **`WebSocketPeer`** | Native in Godot 4.7.2 | Connects to Python `websockets` on `ws://127.0.0.1:8765` with zero C++ compilation on Fedora 45. Uses JSON for discrete events/UI and raw binary **`PackedFloat32Array`** frames for 10,000+ positions (faster than pure-GDScript MessagePack). |

### Terrain3D Heightmap & `16×16m` Parcel Sync
1. Sculpt the 4 racial biomes and flat terraced pads for institutional landmarks in `Terrain3D`.
2. Export the terrain elevation map once as a float32 array (`data/world_heightmap.npy`, ~4–16 MB) so Python (`sim_core/spatial/heightmap.py`) performs $O(1)$ elevation lookups for distant agents.
3. Map logical parcels 1:1 to `chunk_x = floor(x / 16)`, `chunk_z = floor(z / 16)` (`parcel_id = f"{cx}_{cz}"`), projecting settlement and nation borders onto the terrain via a lightweight ground decal or Terrain3D shader overlay.

---

## 3. World, Biomes & Distinct Racial Architecture (Walk-In Interiors, CC0)
All environment packs below are free (**CC0**) and ship in `.gltf` / `.glb` / `.fbx` formats ready for Godot 4:

| Requirement | Exact Free Pack(s) | Adaptation for 4 Races, Seasons & Landmarks |
| :--- | :--- | :--- |
| **4-Season Nature & Harvestables** | **Quaternius: Ghibli Game Kit** + **Ultimate Stylized Nature MegaKit** | Trees, berry bushes, crops, boulders, grass, and flowers. Drive seasonal transitions (Spring green → Autumn amber → Winter frost-white) via a single shader uniform (`global uniform float season_progress`) so only 1 mesh set is needed per tree/plant. |
| **Human (Stone/Timber) & Tier 1–3 Houses** | **Quaternius: Medieval Village MegaKit** (300+ modular pieces) | Walls include built-in exterior and interior faces plus snapping roofs, doors, stairs, windows, and vines—used for walk-in Tier 1–3 houses, Courthouses, and Town Halls. |
| **Dragon (Obsidian Halls), Cathedrals & Bank Vault** | **KayKit: Dungeon Pack 1.1** (200+ modular pieces) | Modular stone walls, pillars, stairs, ceilings, banners, chests, and doors. Tint the gradient atlas texture to dark obsidian + glowing lava/gold trim for Dragon mountain sanctuaries, and pale marble/gold for Grand Cathedrals and the World Bank Vault. |
| **Elf (Sylvan/Marble) & Beasthuman (Lodges)** | **Quaternius: Medieval Village MegaKit** + **Ghibli Game Kit** | Kitbash in Godot: tint timber/plaster modular walls pale ivory + drape with vines/cherry/birch trees for Elven Sylvan Halls; use dark log/wood walls + fur/bone/campfire props for Beasthuman Lodges and Dwarf stone halls. |
| **World Library, Council Chamber & WTC Stalls** | **Quaternius: Fantasy Props MegaKit** (200+ models) | Bookshelves, lecterns, books, scrolls, tables, chairs (2 Council seats per Nation), crates, market stalls, tools, weapons, and potions for walk-in interiors. |
| **Abandoned Ruins & `16×16m` Property Markers** | **KayKit: Dungeon Pack 1.1** + **Medieval Village MegaKit** | Broken walls, rubble pillars, and boundary stones that toggle dynamically when a wilderness parcel escheats to `UNCLAIMED` ruins. |

---

## 4. The 7 Bespoke Divine Hero Models (VRoid Studio + Blender Pipeline)
Because only **7 Divine Hero Models** exist, they use bespoke anime proportions created via **VRoid Studio** (free on Steam via Proton on Fedora 45):

| Entity | Model File | Visual Design & Distinct Features | Key Animations |
| :--- | :--- | :--- | :--- |
| **1. God (You / Admin)** | `god_avatar.vrm` | Regal, ethereal sovereign/traveler in celestial attire; golden halo + ground-light `DivineAura` shader (`is_god = true`). | `idle_float`, `walk`, `fly`, `gesture_bless`, `gesture_smite`, `read_book` |
| **2. World Goddess (Wife of God)** | `world_goddess.vrm` | Towering cosmic matriarch (`1.15x` scale) in flowing white-and-gold celestial robes, starry veil/crown, floating astrolabe/scroll prop. | `idle_hover`, `walk_graceful`, `write_ledger`, `mediate_council`, `world_blessing` |
| **3. Human God-Mother** | `gm_human.vrm` | Crowned protector in royal blue-and-silver robes carrying a balanced scale/lantern; expressive posture. | `idle`, `hover_walk`, `bless_mortal`, `council_talk`, `sigh_restraint` |
| **4. Elf God-Mother** | `gm_elf.vrm` | Tall sylvan maiden with long pointed ears, emerald leaf-woven gown, living vine crown, glowing spirit wisps. | `idle`, `glide`, `nature_heal`, `council_talk`, `forest_ward` |
| **5. Dragon God-Mother** | `gm_dragon.vrm` | Composed draconic empress in humanoid-dragon form—crimson/obsidian scales, curved horns, sweeping wings, glowing amber eyes. | `idle`, `hover_walk`, `wing_flare`, `council_talk`, `dragon_roar` |
| **6. Beasthuman God-Mother** | `gm_beasthuman.vrm` | Proud guardian deity with fox/wolf ears, fur-trimmed tribal regalia, golden claw gauntlets. | `idle`, `prowl_walk`, `rally_pack`, `council_talk`, `bestow_strength` |
| **7. Demon God-Mother** | `gm_demon.vrm` | Sovereign infernal matriarch in obsidian/crimson regalia, curved horns, dark flame/bat wings, runic catalyst. | `idle`, `hover_walk`, `rally_fury`, `council_talk`, `demon_strike` |

### Strict VRoid → Blender → Godot Rules
1. **Use VRoid's Built-In Optimizer (NO Blender Decimate):** Export each deity from VRoid Studio using its built-in **Reduce Polygons + Combine Meshes** preset (~`8,000–12,000` triangles). **Never** apply Blender's `Decimate` modifier to a rigged `.vrm`, as it corrupts weight painting and facial blendshapes. Seven hero deities at ~10k tris have negligible GPU cost on the Radeon 780M.
2. **Blender Bone-Parenting Only (`sudo dnf install blender`):** Import `.vrm` via the free **VRM Add-on for Blender** solely to parent external props/appendages (horns, wings, ears, gauntlets, astrolabe, lantern) onto existing `Head`, `Chest`, or `Hand` bones, then re-export as `.vrm` (preserving MToon materials & spring-bone physics).
3. **Animations:** Source from **Mixamo** or **Quaternius Universal Animation Library** retargeted onto `SkeletonProfileHumanoid`.

---

## 5. The 7 Base Mortal Rigs, Shared Skeleton, Metamorphosis & Uniqueness Shader
All `60–120` pooled mortals are driven by **7 lightweight base rigs** (`600–1,200` triangles each) sharing one humanoid skeleton across all humanoid races:

| Asset Slot | Exact Free Source (CC0) | Setup & Scaling Notes |
| :--- | :--- | :--- |
| `base_human.glb`, `base_elf.glb` & `base_demon.glb` | **Quaternius: Characters - Fantasy Races** + **Modular Character Outfits - Fantasy** | Universal Humanoid Rig. Scale `base_elf` to `1.06x` with pointed ears; scale `base_demon` to `1.08x` with horn attachments; toggle `BOY`/`GIRL` hair and tunic presets. |
| `base_dragon_humanoid.glb` | **Quaternius: Characters - Fantasy Races** (Dragonborn base) | Same Universal Humanoid Rig; attach folded back-wings in Blender. Default peaceful Dragon form (`1.05x`). |
| `base_dragon_true.glb` | **Quaternius: Animated Dragon** (Ultimate Monsters Pack) | Lightweight rigged `.glb` (`3.8x` scale) with 8 built-in animations (`Flying_Idle`, `Fast_Flying`, `Headbutt`, `Death`, etc.). |
| `base_beasthuman_agile.glb` & `base_beasthuman_heavy.glb` | **Quaternius: Characters - Fantasy Races** (Orc/Goblin/Humanoid bases) | Same Universal Humanoid Rig. Bone-scale presets: `CAT_KIN`/`WOLF_KIN` (`0.98x`), `DWARF` (`0.75x H / 1.15x W`), `BARBARIAN`/`BEAR_KIN` (`1.18x H / 1.25x W`). |
| **Shared Animation Library** | **Quaternius: Universal Animation Library (1 & 2)** | 120–250+ CC0 animations (`idle`, `walk`, `run`, `crawl_infant`, `cry_distress`, `comfort_child`, `forage`, `mine`, `build`, `pray_kneel`, `attack`, `flee`, `sleep`). Retarget once via `SkeletonProfileHumanoid`. |
| **~15 Modular Attachments** | **Quaternius: Fantasy Props MegaKit** + **KayKit: Dungeon Pack** | Hairstyles, beards, animal ears/tails, crowns, cleric hoods/staves, scholar glasses/scrolls, swords/tools, bandages mounted on `BoneAttachment3D` (`Head`, `Back`, `Hips`, `Hand`). |

### Runtime Uniqueness & Dragon Metamorphosis
1. **Biological Stage Bone-Scaling:**
   - `INFANT`: `0.45x` height + `1.25x` chibi head ratio; activates `InfantTears` particle emitter and `cry_distress` animation whenever `crying == true`.
   - `CHILD`: `0.75x` height.
   - `ADULT`: `1.00x` height (multiplied by `RaceProfile.adult_scale`).
   - `ELDER`: `0.94x` height + slight spine slouch offset + silver/white hair tint override.
2. **Zero-Stutter Dragon Metamorphosis (`scripts/dragon_morph.gd`):**
   - Dragon pool slots parent both `base_dragon_humanoid` and `base_dragon_true` under a single `AgentRoot`. Switching `HUMANOID_DRAGON` $\leftrightarrow$ `TRUE_DRAGON` toggles node visibility, fires `MetamorphosisBurst`, and swaps the collision capsule in `< 0.1 ms`.
3. **Per-Instance Shader Uniforms (`shaders/mortal_toon.gdshader`):**
   - Use **one shared `ShaderMaterial`** with 4 per-instance uniforms so Godot batches draw calls cleanly without duplicating materials:
     ```glsl
     instance uniform vec3 skin_hsv;        // Inherited from parents ±8% mutation
     instance uniform vec3 cloth_primary;   // Nation / Settlement / Church banner color
     instance uniform vec3 cloth_secondary; // Accent trim / Dynasty color
     instance uniform float injury_mix;     // Blends bandage/blood/shiver overlay when injured/ill
     ```

---

## 6. Hybrid Diegetic UI, 2D Modals & In-Godot Divine Family HUD
1. **Diegetic 3D Signs (`UPDATE_ONCE` SubViewports):**
   - WTC Live Price & CPI Inflation Boards and Courthouse Wanted Notices render onto 3D hanging signs via `SubViewport` → `ViewportTexture`.
   - Set `render_target_update_mode = SubViewport.UPDATE_ONCE` on all sign viewports and trigger a redraw **only** when Python emits a `SIGN_UPDATE` civic tick event (every ~30s), preserving Radeon 780M fillrate.
2. **World Library 2D Modal (`scripts/library_modal.gd`):**
   - Clicking a Library Lectern or Bookshelf opens a clean 2D Godot `TextEdit` modal showing the canonical volume, author, and Council of Elders approval stamp.
   - When `God` clicks **Save**, Godot emits `{"type": "GOD_LIBRARY_EDIT", ...}` over WebSocket to Python (never touching SQLite directly).
3. **In-Godot Divine Family & God Ledger HUD (`scripts/divine_hud.gd`):**
   - Collapsible side overlay displaying real-time messages from the **World Goddess** and **4 Racial God-Mothers** (escalated mortal prayers, congregational altar Prayer Head reports, Inter-Sister Council debates, and `ErrorHealer` alerts), plus quick controls for `speed 1x..60x`, deity naming, and toggling the Orbital Map.
   - Opening/closing the Godot client automatically toggles `GodPresenceTracker` in Python so away-time messages route cleanly to `data/god_ledger/day_XXXXX.md`.

---

## 7. Particle VFX & Free CC0 Sound Effects
- **6 Reusable Native `GPUParticles3D` Scenes** (textured with **Kenney Particle Pack CC0**):
  1. `WeatherParticles.tscn`: Attached above God's camera for seasonal rain, winter snow, and autumn leaves.
  2. `InfantTears.tscn`: Mounted on `Head` bone when `crying == true`.
  3. `DragonFireBreath.tscn`: Mounted on `base_dragon_true` jaw bone during combat.
  4. `MetamorphosisBurst.tscn`: Fire/smoke burst masking Dragon form swaps.
  5. `DivineAura.tscn`: Rising golden motes + ground light decal for `god_avatar.vrm` (`is_god = true`).
  6. `AltarPrayerBeacon.tscn`: Subtle vertical skyward light pillar over any Altar currently hosting a congregational prayer (`>= 3` mortals under a Prayer Head), visible while flying.
- **Free CC0 Audio Packs:**
  - **Kenney Audio Packs (CC0):** UI clicks, footsteps, impacts, and inventory sounds.
  - **OpenGameArt RPG Sound Pack (CC0) & Fantasy Sound Effects Library:** Coins, hammers, sword clashes, divine blessings, and dragon roars.
  - **Freesound.org (filtered CC0):** Loopable seasonal wind, forest birds, winter blizzard, distant crowd prayers, and crackling hearths.
  - **Sonniss GDC Annual Free Audio Bundle:** Optional high-fidelity environmental ambiences.

---

## 8. Fedora 45 Setup & Vertical Slice Build Order
1. **Install Native Tools:**
   ```bash
   sudo dnf install blender
   # Install Godot 4.7.2 (Linux x86_64) + VRoid Studio via Steam (Proton)
   ```
2. **Download Free Packs into `godot_client/addons/` and `godot_client/assets/`:**
   - Addons: `Terrain3D v1.1.0`, `Sky3D v2.1`, `VRM Importer & MToon Shader v2.6.1`.
   - Assets: Quaternius (`Characters - Fantasy Races`, `Modular Character Outfits - Fantasy`, `Universal Animation Library 1 & 2`, `Medieval Village MegaKit`, `Fantasy Props MegaKit`, `Ghibli Game Kit`, `Ultimate Stylized Nature MegaKit`, `Animated Dragon`), KayKit (`Dungeon Pack 1.1`), Kenney (`Particle Pack`, `Audio Packs`).
3. **Build in 3 Vertical Slices (Phase 5 of `IMPLEMENTATION_ROADMAP.md`):**
   - **Slice A (World & Terrain):** `Terrain3D` 4 biomes + export `data/world_heightmap.npy` + `Sky3D` (with night ambient floor) + global `season_progress` shader + `16×16m` parcel border overlay.
   - **Slice B (Reality Bubble & Orbital Map):** Pre-allocated pool of `120` mortals from the 6 base rigs, stage/race bone scaling, `mortal_toon.gdshader` instance uniforms, Animation LOD, Dragon metamorphosis toggle, and `MultiMeshInstance3D` Orbital Map driven by Python's binary `PackedFloat32Array` WebSocket feed.
   - **Slice C (Landmarks, Deities & UI):** Snap together the World Library (with 2D `TextEdit` modal routed to Python), WTC (`UPDATE_ONCE` SubViewport boards), Grand Cathedral, Courthouse, `AltarPrayerBeacon`, the 7 VRoid Divine Heroes, and the In-Godot Divine Family HUD.