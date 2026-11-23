# Craft and Metallurgy (`craft_and_metallurgy`) — Authoring Guide

## 1. Scope & Domain Definition
The `craft_and_metallurgy` domain encompasses mineral smelting, forge fire management, iron bloom consolidation, steel tempering, bronze alloy balance, armoring, leatherwork, and fine tool fabrication. Treatises explain kiln draft dynamics, flux additions (limestone, crushed quartz), charcoal burning, water-quench cooling curves, and edge geometry.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `craft_and_metallurgy.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `smelting`: Bloomery furnaces, blast bellows, slag tapping, flux selection.
- `alloying`: Bronze (copper-tin ratios), brass, carbon steel, crucible steel.
- `forging`: Anvil work, hammer cadence, folded iron laminates, fullering.
- `tempering`: Oil vs brine quench, thermal color reading, annealing.
- `toolcraft`: Saws, chisels, plowshares, draw-knives, armor plating.

---

## 3. Tone & Voice
- **Tone:** Practical, artisanal, tactile, precise.
- **Style:** Guild master instructions, blacksmith apprentice manuals, master crafter codices.
- **Racial Considerations:**
  - *Dwarf:* Underground forge fires, heavy deep-iron tempering, runic anvil geometry.
  - *Demon:* Brimstone and volcanic slag fluxes, extreme heat resistance, obsidian edging.
  - *Human:* Adaptable bloomery setups, river-powered trip-hammers, standardized iron nails.
  - *Elf:* Cold-forged silver-leaf alloys, organic tree-sap flux, weightless balance.
  - *Beasthuman:* High-torque claw-tools, heavy horn-handled axes, sinew bindings.

---

## 4. Profession Hooks & Rigs
- Primary professions: Blacksmith, Armorer, Smelter, Toolmaker, Jeweler, Apprentice.
- Rig integration: Forge hammer strikes, bellows pumping, quenching steam VFX.

---

## 5. Mechanical Effect Bounds
- `smelting_yield_bonus`: `[0.00, +0.30]`
- `tool_durability_bonus`: `[0.00, +0.40]`
- `craft_speed_bonus`: `[-0.15, +0.30]`
- `construction_cost_reduction`: `[0.00, +0.20]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "craft_metallurgy_vol001_bloomery_limestone_flux",
    "subject": "craft_and_metallurgy",
    "target_section": "metallurgy_and_smithing",
    "fact_key": "craft_and_metallurgy.smelting.bloomery_limestone_flux",
    "title": "Limestone Flux in Clay Bloomery Smelting",
    "summary": "Addition of crushed limestone to bog iron ore charges to lower slag melting temperature and accelerate spongy iron sponge consolidation.",
    "body": "Charging the vertical clay bloomery with alternating layers of dry oak charcoal and roasted bog ore produces heavy viscous silicate slag that traps metallic iron droplets. Introducing five parts crushed limestone per hundred parts raw ore chemically binds the excess silica into fluid calcium silicate slag, which drains cleanly through the basal tap hole, yielding clean, dense iron blooms.",
    "author": "Master Smith Torvald",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["smelting", "bloomery", "flux", "limestone", "iron"],
    "prerequisites": [],
    "mechanical_effects": {
      "smelting_yield_bonus": 0.16,
      "craft_speed_bonus": 0.08
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "craft_metallurgy_vol001_plowshare_edge_chilled_iron",
    "subject": "craft_and_metallurgy",
    "target_section": "metallurgy_and_smithing",
    "fact_key": "craft_and_metallurgy.toolcraft.chilled_edge_plowshare",
    "title": "Chilled Edge Hardening for Heavy Soil Plowshares",
    "summary": "Differential chilling of cast and forged plowshare points against thick iron plates to resist abrasion in flint-heavy clay soils.",
    "body": "Plowshares drawn through rocky clay soils wear blunt within a single planting cycle if forged uniformly soft. By cooling the leading cutting edge rapidly against a damp iron anvil face while leaving the back body to air-cool, a wear-resistant white-iron shell forms at the tip while preserving malleable shock resistance in the core.",
    "author": "Aldman the Wheeler",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["toolcraft", "plowshare", "forging", "hardening", "agriculture"],
    "prerequisites": ["craft_and_metallurgy.smelting.bloomery_limestone_flux"],
    "mechanical_effects": {
      "tool_durability_bonus": 0.22
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
