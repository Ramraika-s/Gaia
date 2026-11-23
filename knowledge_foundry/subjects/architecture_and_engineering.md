# Architecture and Engineering (`architecture_and_engineering`) — Authoring Guide

## 1. Scope & Domain Definition
The `architecture_and_engineering` domain governs settlement civil construction, dimensional chunk zoning (16×16m parcels), structural load distribution, stone masonry, timber framing, vaulted arches, aqueducts, drainage channels, roads, and defensive walls.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `architecture_and_engineering.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `masonry`: Ashlar block dressing, dry-stone walling, mortar ratios, keystones.
- `timber`: Mortise-and-tenon framing, king-post trusses, cruck frames, shingle roofs.
- `hydraulics`: Gravity aqueducts, stone sluice gates, drainage culverts, wells.
- `civic_works`: Paved stone roads, bridge abutments, foundation piling, granaries.
- `parcels`: Boundary stone placement, easement corridors, chunk grading.

---

## 3. Tone & Voice
- **Tone:** Methodical, mathematical, structural, enduring.
- **Style:** Master builder treaties, mason lodge rules, civil surveyor field books.
- **Racial Considerations:**
  - *Dwarf:* Monolithic underground load-bearing arches, granite pillars, seismic dampening.
  - *Elf:* Living timber arbor-shaping, cantilevers woven through ancient trees, light vaults.
  - *Human:* Adaptable lime mortar, modular timber-framed civic halls, tiered aqueducts.
  - *Beasthuman:* Dense log-and-earth ramparts, turf-roofed communal longhouses, thermal earth-berms.
  - *Demon:* Basalt cliff-carving, cantilevered obsidian balconies over thermal vents.

---

## 4. Profession Hooks & Rigs
- Primary professions: Stonemason, Carpenter, Civil Architect, Surveyor, Quarryman, Builder.
- Rig integration: Mallet and chisel strikes, plumb-line measuring, stone hauling.

---

## 5. Mechanical Effect Bounds
- `structural_integrity_bonus`: `[0.00, +0.35]`
- `construction_cost_reduction`: `[0.00, +0.25]`
- `winter_hardiness`: `[0.00, +0.25]`
- `defense_bonus`: `[0.00, +0.20]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "arch_eng_vol001_pozzolanic_hydraulic_mortar",
    "subject": "architecture_and_engineering",
    "target_section": "civil_engineering",
    "fact_key": "architecture_and_engineering.masonry.pozzolanic_mortar_mix",
    "title": "Pozzolanic Volcanic Ash Hydraulic Mortar",
    "summary": "Combining calcined slaked lime with finely ground reactive volcanic ash to create water-impermeable mortar that sets underwater and resists freezing cycles.",
    "body": "Standard lime mortar dissolves under constant stream flow and flakes apart when moisture freezes inside masonry seams. Blending two parts reactive volcanic ash with one part slaked quicklime and three parts clean river sand initiates an irreversible chemical crystallization that hardens even when fully submerged, creating permanent joints for canal locks, deep foundations, and harbor piers.",
    "author": "Chief Architect Caelum",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["masonry", "mortar", "hydraulic", "foundations", "stone"],
    "prerequisites": [],
    "mechanical_effects": {
      "structural_integrity_bonus": 0.20,
      "winter_hardiness": 0.12
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "arch_eng_vol001_king_post_timber_truss",
    "subject": "architecture_and_engineering",
    "target_section": "civil_engineering",
    "fact_key": "architecture_and_engineering.timber.king_post_roof_truss",
    "title": "King-Post Truss and Tie-Beam Span",
    "summary": "Triangulated timber framing utilizing a central vertical tension king-post to support clear-span roofs over wide public halls without interior columns.",
    "body": "Covering wide market squares and communal guildhalls previously required dense forests of central pillars that obstructed movement. The king-post truss anchors principal rafters into a horizontal oak tie-beam with pinned mortise-and-tenon joints, converting downward roof weight into lateral tension, safely spanning sixteen-meter parcel widths with zero central columns.",
    "author": "Master Carpenter Brand",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["timber", "carpentry", "roof", "truss", "framing"],
    "prerequisites": [],
    "mechanical_effects": {
      "structural_integrity_bonus": 0.15,
      "construction_cost_reduction": 0.10
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
