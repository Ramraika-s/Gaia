# Natural History and Geography (`natural_history_and_geography`) — Authoring Guide

## 1. Scope & Domain Definition
The `natural_history_and_geography` domain covers cartography, elevation gradients, regional biomes, river drainage basins, weather forecasting (rain, snowstorms, seasonal thermal fronts), wild fauna behavior, mineral veins, and survival navigation across unexplored wilderness.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `natural_history_and_geography.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `cartography`: Triangulation bearings, contour surveying, landmark pacing.
- `weather`: Barometric cloud interpretation, seasonal frost forecasts, wind cycles.
- `biomes`: Alpine crags, river deltas, dense temperate woods, volcanic badlands.
- `fauna`: Pack-hunting wolf tactics, migratory waterfowl flyways, river salmon runs.
- `geology`: Outcrop identification, quartz-vein tracing, alluvial gold panning.

---

## 3. Tone & Voice
- **Tone:** Exploratory, observant, descriptive, survivalist.
- **Style:** Surveyor's field journal, naturalist's compendium, trailblazer's route log.
- **Racial Considerations:**
  - *Dragon:* Aerial panoramic terrain mapping, thermal draft navigation over ridges.
  - *Beasthuman:* Scent-gradient trail tracking, wilderness shelter construction, animal tracking.
  - *Elf:* Deep forest canopy navigation, star-sighting, botanical landmarking.
  - *Dwarf:* Underground cavern echo-sounding, stratum identification, fault-line safety.
  - *Human:* River barge navigation, topographic road surveys, coastal tide charts.

---

## 4. Profession Hooks & Rigs
- Primary professions: Cartographer, Scout, Forester, Ranger, Naturalist, Miner.
- Rig integration: Sighting through brass alidade, drawing parchment maps, inspecting compass.

---

## 5. Mechanical Effect Bounds
- `patrol_efficiency`: `[0.00, +0.30]`
- `winter_hardiness`: `[0.00, +0.30]`
- `spoilage_reduction`: `[0.00, +0.20]`
- `attrition_reduction`: `[0.00, +0.25]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "nat_geo_vol001_cloud_anvil_storm_prediction",
    "subject": "natural_history_and_geography",
    "target_section": "cartography_and_beasts",
    "fact_key": "natural_history_and_geography.weather.anvil_cloud_squall_warning",
    "title": "Towering Anvil Clouds and Sudden Gale Prediction",
    "summary": "Reading flattened high-altitude cirrus anvil cloud formations to alert mountain patrols and river barges two hours prior to violent squalls.",
    "body": "When hot valley air collides with chilled mountain ridge winds, cumulus clouds rapidly boil upward into dark towering columns. When the flat, fibrous anvil top spreads against the upper sky, sudden torrential rain, hail, and gale-force wind gusts will sweep the valley within two hours. Recognizing this signature allows shepherds to pen livestock and river barges to moor before the storm strikes.",
    "author": "Chief Surveyor Oakhaven",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["weather", "cartography", "storm", "navigation", "squall"],
    "prerequisites": [],
    "mechanical_effects": {
      "attrition_reduction": 0.18,
      "patrol_efficiency": 0.12
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "nat_geo_vol001_triangulation_plane_table_survey",
    "subject": "natural_history_and_geography",
    "target_section": "cartography_and_beasts",
    "fact_key": "natural_history_and_geography.cartography.triangulation_plane_table",
    "title": "Baseline Triangulation Using the Mounted Plane Table",
    "summary": "Measuring long settlement borders and mountain passes with calibrated sightlines from a measured baseline to eliminate pacing errors.",
    "body": "Measuring rugged parcels with pacing chains introduces cumulative distortion across hills and ravines. Laying out a flat baseline of precisely one hundred paces, leveled on firm ground, allows surveyors to aim a brass sighting rule at prominent church spires and mountain peaks from both ends. Drawing the intersecting sightlines on parchment directly scales true geographic distances without clambering over cliffs.",
    "author": "Surveyor Roderick",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["cartography", "surveying", "triangulation", "borders", "geography"],
    "prerequisites": [],
    "mechanical_effects": {
      "patrol_efficiency": 0.15
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
