# Agriculture and Botany (`agriculture_and_botany`) — Authoring Guide

## 1. Scope & Domain Definition
The `agriculture_and_botany` domain encompasses agrarian subsistence, soil chemistry, four-field crop rotation, irrigation canals, seed selection, herbal foraging, orchard grafting, livestock pasturage, and granary storage. Treatises teach techniques to maximize harvest yield and stave off seasonal famine across cold winters.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `agriculture_and_botany.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `crops`: Grains (spelt, rye, barley), pulses (lentils, beans), tubers, root cellaring.
- `soil`: Nitrogen-fixing legumes, marling, manure composting, green manure plowing.
- `irrigation`: Terraced gravity canals, raised ridge beds, retention ponds.
- `herbalism`: Medicinal roots, wild berry cultivation, drying herbs, tea brewing.
- `storage`: Silo ventilation, ash-coating against weevils, grain fumigation with dried herbs.

---

## 3. Tone & Voice
- **Tone:** Patient, seasonal, earth-attuned, observant.
- **Style:** Agrarian almanacs, monastic herbal codices, elder farmer wisdom scrolls.
- **Racial Considerations:**
  - *Elf:* Tree-canopy orchards, perennial forest farming, symbiotic fungus cultivation.
  - *Beasthuman:* High-yield pasture management, berry foraging trails, root-crop caching.
  - *Dwarf:* Subterranean mushroom beds, moisture-condensing moss gardens, root cellars.
  - *Human:* Four-field crop rotation, horse-drawn harrows, river-valley irrigation channels.
  - *Demon:* Ash-fertilized volcanic vine terraces, geothermal greenhouse trenches.

---

## 4. Profession Hooks & Rigs
- Primary professions: Farmer, Herbalist, Miller, Orchardist, Forager, Granary Keeper.
- Rig integration: Scythe reaping, hoe weeding, basket gathering, seed scattering.

---

## 5. Mechanical Effect Bounds
- `crop_yield_bonus`: `[0.00, +0.35]`
- `spoilage_reduction`: `[0.00, +0.40]`
- `winter_hardiness`: `[0.00, +0.30]`
- `fertility_rate_bonus`: `[0.00, +0.15]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "agri_botany_vol001_four_field_clover_rotation",
    "subject": "agriculture_and_botany",
    "target_section": "agronomy_and_herbalism",
    "fact_key": "agriculture_and_botany.soil.four_field_clover_rotation",
    "title": "Four-Field System with Red Clover Cover",
    "summary": "Eliminating fallow wastage by cycling winter grain, spring barley, clover meadow, and root turnips across four contiguous parcels.",
    "body": "Traditional two-field systems leave half the arable land barren every season to recover nitrogen. By dividing land into four parcels and rotating winter wheat, spring legumes, deep-root red clover for livestock grazing, and winter turnips, the soil remains continuously energized with atmospheric nitrogen. This cycle eliminates fallow waste and provides rich winter feed for draft oxen.",
    "author": "Elder Harvester Maren",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["agriculture", "crop_rotation", "soil", "clover", "harvest"],
    "prerequisites": [],
    "mechanical_effects": {
      "crop_yield_bonus": 0.24,
      "winter_hardiness": 0.10
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "agri_botany_vol001_elevated_granary_lime_lining",
    "subject": "agriculture_and_botany",
    "target_section": "agronomy_and_herbalism",
    "fact_key": "agriculture_and_botany.storage.elevated_lime_granary",
    "title": "Elevated Stilted Granary with Quicklime Pest Barrier",
    "summary": "Building timber grain stores on stilted mushroom cap stones with dry lime floor dusting to block rodent climbing and fungal dampness.",
    "body": "Grain stored directly on earth floors rots within two moons from ground dampness and weevil infestation. Mounting granary sill beams atop inverted smooth stone mushroom pillars prevents rodents from scaling the walls. Lining the cedar plank floor with dry slaked lime and dried tansy flowers desiccates insect larvae and preserves stored seed wheat through severe winters.",
    "author": "Miller Jon",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["storage", "granary", "spoilage", "pest_control", "winter"],
    "prerequisites": [],
    "mechanical_effects": {
      "spoilage_reduction": 0.28
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
