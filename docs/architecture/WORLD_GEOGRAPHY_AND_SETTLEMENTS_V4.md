# WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md — Concentric World Geography, Ring Architecture & Settlement Topography

## 1. Overview & Coordinate Space
Gaia v4.0 features an **$8\text{km} \times 8\text{km}$ concentric anime-fantasy world** centered at the origin $(0, 0, 0)$ and bounded within $[-4000\text{m}, 4000\text{m}]$ along the horizontal $X$ and $Z$ axes:
- **World Bounding Extents:** $X \in [-4000, 4000]$, $Z \in [-4000, 4000]$.
- **Elevation Coordinate ($Y$):** $Y = 0.0\text{m}$ defines universal `SEA_LEVEL`. Mountain peaks reach $+110.0\text{m}$; ocean floors dip to $-25.0\text{m}$.
- **Heightmap Resolution:** $1024 \times 1024$ 32-bit float array (`data/world_heightmap.npy`), providing an exact $7.8125\text{m}$ grid step with bilinear interpolation in Python for $O(1)$ elevation lookups matching Godot's `HeightMapShape3D`.
- **Chunk Parcels:** The world is partitioned into explicit $16\text{m} \times 16\text{m}$ parcels (`cx`, `cz` in $[-250, 250]$), used for deeds, taxation, zoning, and border arbitration.

```text
                                [ RING 3: OCEAN & ISLETS ]
                                   (r = 3300m .. 4000m)
                   ─────────────────────────────────────────────────
                               [ RING 2: FRONTIER WILDERNESS ]
                                   (r = 1500m .. 3300m)
                   ─────────────────────────────────────────────────
                            [ RING 1: PENTAGONAL GATED CITIES ]
                                (r = 1150m, 72° radial spacing)
                   ─────────────────────────────────────────────────
                                 [ RING 0: IMPERIAL ACROPOLIS ]
                         Palace Plateau (32m) | Institutional Plaza (24m)
                                         (0, 0, 0)
```

---

## 2. Ring 0: Imperial Acropolis & Grand Divine Palace ($r = 0..340\text{m}$)

The sacred focal point of Gaia, where God, the World Goddess, the High Judiciary, and the World Bank preside over mortal civilization:

### 2.1 The Grand Divine Palace Plateau ($r = 0..140\text{m}$)
- **Center & Elevation:** Centered at $(0.0, 32.0, 0.0)$ upon a raised marble and granite plateau at elevation $+32.0\text{m}$.
- **Architecture:** Columned neoclassical-anime basilica with open celestial courtyards, crystalline arches, reflecting pools, and stained glass.
- **Main Palace Gate:** Located at $(0.0, 32.0, 38.0)$, fronted by a grand marble stairway leading down to the Outer Plaza.
- **Twin Guardian Dragons:**
  - Stationed at the Palace Gate portico:
    - **Gilded Guardian Dragon:** Positioned at $(-12.0, 32.0, 38.0)$, facing South.
    - **Silver Guardian Dragon:** Positioned at $(+12.0, 32.0, 38.0)$, facing South.
  - Ancient True Dragons pledged to the World Goddess. Possess $650\text{HP}$ each, repel violent intruders, and inspect approaching petitioners.
- **24 Palace Knights Battalion (`PALACE_KNIGHT`):**
  - Elite division of high-discipline mortal knights stationed along the perimeter balustrades, gatehouse, and audience chamber.
  - Guard the World Goddess and enforce palace entry protocols.

### 2.2 Palace Entry State Machine (`sim_core/world/settlements.py`)
Random mortals cannot freely breach the Grand Divine Palace without an audience pass:
1. **Petitioning (`PalaceEntryRequest`):**
   - Mortal approaches the Palace Gate and submits a petition citing their reason (e.g. *Audience on Royal Succession*, *Judiciary Appeal*, *Divine Blessing*).
   - Python registers the request with mortal attributes (`faith_devotion`, `criminal_count`, `title`).
2. **Adjudication (`PalaceDecision`):**
   - Evaluated by the **World Goddess** (or **God** via the Godot UI modal):
     - `GRANT`: Emits a `PalacePass` valid for 240 ticks (10 game minutes); gates open and knights stand down.
     - `DENY`: Gate remains locked; knights instruct the petitioner to depart.
     - `ESCORT`: Knights escort the petitioner directly to the audience dais under armed guard.
3. **Unauthorized Trespass:**
   - Forcing entry without a valid pass triggers immediate alarm: Guardian Dragons emit a terrifying roar, knights draw enchanted blades, and a `TRESPASS` criminal record is filed in the High Judiciary.

### 2.3 Outer Institutional Plaza ($r = 140..340\text{m}$)
Surrounding the palace plateau at elevation $+24.0\text{m}$ lies the central administrative hub of planetary civilization:
- **High Court of the Judiciary:** Marble hall where planetary trials, interstate treaties, and treason cases are adjudicated.
- **World Bank Central Vault:** Massive reinforced obsidian and steel edifice where planetary credit balances and currency reserves are kept.
- **Great Library Central Lectern:** Open rotunda housing the master physical copies of the **World Library** and **Divine Codex**.
- **Grand Amphitheater:** Semicircular forum where Inter-Sister Council resolutions are announced to mortal ambassadors.

---

## 3. Ring 1: The Pentagonal Gated Cities ($r = 1,150\text{m}$)

At a radius of $1,150\text{m}$ from the origin, arranged at exact $72^\circ$ radial intervals, stand the 5 ancestral racial capitals. Each city is fortified by a circular curtain wall of radius $240.0\text{m}$:

| City Name | Native Race | Center $(X, Z)$ | Elevation ($Y$) | Angle | Patron God-Mother Palace | Architectural Style |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Sylvanor** | `ELF` | $(+1150.0, 0.0)$ | $+28.0\text{m}$ | $0^\circ$ (East) | Sylvanor Palace (`gm_elf`) | Living bioluminescent wood, graceful spires, arboreal bridges |
| **Aurelia** | `HUMAN` | $(+355.37, +1093.71)$ | $+18.0\text{m}$ | $72^\circ$ (South-East) | Aurelia Palace (`gm_human`) | White stone, terracotta roof tiles, high belltowers, busy canals |
| **Fenris Hold** | `BEASTHUMAN` | $(-930.37, +675.95)$ | $+24.0\text{m}$ | $144^\circ$ (South-West) | Fenris Hold Palace (`gm_beasthuman`) | Timber bastions, carved totems, stone forges, communal longhouses |
| **Malakor** | `DEMON` | $(-930.37, -675.95)$ | $+42.0\text{m}$ | $216^\circ$ (North-West) | Malakor Palace (`gm_demon`) | Basalt battlements, obsidian towers, ash-brick walls, sulfur braziers |
| **Drakonis Spire** | `DRAGON` | $(+355.37, -1093.71)$ | $+68.0\text{m}$ | $288^\circ$ (North-East) | Drakonis Spire Palace (`gm_dragon`) | Massive megalithic masonry, mountain crags, open roost terraces |

### 3.1 City Fortifications & Modular Prefabs
Every Ring 1 city features a complete urban ecosystem rendered via Godot's `CitiesAndBuildingsManager.gd`:
- **4 Cardinal Gates:** North, South, East, and West gates with heavy portcullises and archer towers.
- **Curtain Walls:** Segmented stone wall prefabs ($16\text{m}$ spans) linking gates into an impenetrable ring.
- **Housing Tiers:**
  - `HOUSE_T1_COTTAGE`: Single-family starter homes with thatched or shingle roofs.
  - `HOUSE_T2_TOWNHOUSE`: Two-story brick/timber residences with glass windows and workshops.
  - `HOUSE_T3_MANOR`: Expansive walled manors with courtyards and servant quarters.
- **Commercial & Civic Facilities:**
  - `SHOP_MARKET`: Open bazaar stalls trading food, grain, and textile goods.
  - `SHOP_BLACKSMITH`: Smelting kilns and anvil forges producing tools and armor.
  - `SHOP_TAVERN`: Multi-story social gathering hubs for rumor exchange and courtship.
- **City Guards Battalion (`CITY_GUARD`):**
  - Stationed along gatehouses and street intersections, maintaining municipal order and suppressing crime.

---

## 4. Ring 2: Frontier Wilderness ($r = 1,500..3,300\text{m}$)

The broad frontier expanse spanning between the Ring 1 urban curtain walls and the coastal shelf:
- **Biomes:** Dense ancient pine and oak forests, rolling grasslands, craggy foothills, peat bogs, and river basins.
- **Resource Deposits:** Wild game herds, berry thickets, timber stands, limestone outcrops, and iron veins.
- **Frontier Homesteads & Pioneer Cottages:**
  - Ambitious citizens leave crowded Ring 1 cities to clear wilderness plots and build self-sufficient pioneer cottages (`is_frontier = true`).
  - Strict double-entry land purchases: pioneers buy unclaimed parcels from regional state authorities or settle frontier boundaries.
- **Emergent Village Clustering:**
  - When $\ge 5$ pioneer cottages cluster within $120\text{m}$ of one another, the residents hold an assembly and petition the World Goddess for formal **`VILLAGE`** status.
  - Upon approval, the cluster gains an explicit border, shared granary, and local headman.

---

## 5. Ring 3: Ocean & Islets ($r = 3,300..4,000\text{m}$)

The outer perimeter of the world disk:
- **Shoreline & Shelf:** Elevation slopes gently down from $+4.0\text{m}$ at $r = 3,300\text{m}$ to $0.0\text{m}$ (`SEA_LEVEL`) at $r = 3,450\text{m}$, continuing into a deep marine shelf ($Y = -12.0\text{m}$ to $-25.0\text{m}$).
- **Water Shading:** Rendered via Godot's `WaterStylized.gdshader` featuring depth-based color gradients, shoreline foam rings, and stylized caustic refractions.
- **Outlying Islets:**
  - Scattered volcanic and coral islets sit between $r = 3,600\text{m}$ and $3,900\text{m}$.
  - Host hermit altars, ancient ruin lecterns, rare alchemy reagents, and secluded dragon roosts.

---

## 6. Road Network & Regional Weather Cells

### 6.1 Paved Highway & Radial Road Network
- **Imperial Avenues (Radial):** Five $12\text{m}$-wide paved stone highways radiate directly from the Ring 0 Outer Plaza to the primary inward gates of each Ring 1 city.
- **Inter-City Trade Roads (Pentagonal):** Broad dirt-and-gravel trade routes connect adjacent Ring 1 cities directly (e.g. Sylvanor $\leftrightarrow$ Aurelia $\leftrightarrow$ Fenris Hold $\leftrightarrow$ Malakor $\leftrightarrow$ Drakonis Spire $\leftrightarrow$ Sylvanor), forming an outer ring route for merchant caravans.
- **Frontier Tracks:** Emergent desire-paths formed by frequent mortal footsteps connecting Ring 1 gates to Ring 2 pioneer clusters.

### 6.2 Regional Weather Cells
The $8\text{km} \times 8\text{km}$ world is divided into **4 distinct macro weather cells** updated once per sim tick:
- **North-East (Dragon Highlands):** Frequent alpine gales, freezing rain, and mountain blizzards.
- **North-West (Demon Ashland):** Heavy volcanic ash fall, dark overcast, and dry thermal updrafts.
- **South-West (Beasthuman Steppe):** Variable continental weather, sudden autumn storms, and crisp winter frosts.
- **South-East / East (Human & Elven Valleys):** Temperate maritime climate, gentle spring rain, and warm summer sunshine.
- **Godot Weather Synchronization:** Weather cell state is packed into the `WORLD_TIME_WEATHER` WebSocket frame, smoothly updating volumetric fog density, cloud cover, and precipitation particle systems in `SkyWeatherController.gd`.
