# Tactics and Warfare (`tactics_and_warfare`) — Authoring Guide

## 1. Scope & Domain Definition
The `tactics_and_warfare` domain governs the martial preservation, territorial defense, and strategic offense of settlements, kingdoms, and free cities. Treatises cover defensive fortifications, gatehouse defense, archer positioning, perimeter sentry routes, anti-siege logistics, cohort formations, night watches, and defensive counter-charges.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `tactics_and_warfare.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `fortification`: Walls, ramparts, bastions, sally ports, ditches.
- `siege`: Murder holes, boiling pitch, battering ram deterrence, trench works.
- `patrol`: Sentry cycles, lantern signals, border watch posts, alarm beacons.
- `formation`: Shield walls, pike hedges, staggered archer ranks, skirmish screen.
- `logistics`: Field rations, baggage trains, arrow replenishment, muster points.

---

## 3. Tone & Voice
- **Tone:** Dispassionate, empirical, vigilant, commanding.
- **Style:** Military manual, watch commander's doctrine, garrison captain's instructions.
- **Racial Considerations:**
  - *Dwarf:* Heavy stone bastions, subterranean choke points, overlapping crossbow lanes.
  - *Elf:* Tree-canopy archery screens, silent skirmish lines, wind-reading bow craft.
  - *Dragon (Humanoid):* High-ground thermal observation, aerial perimeter sweeps.
  - *Beasthuman:* Rapid flanking, scent-tracking sentry relays, ambush packs.
  - *Demon:* Coordinated terror assaults, vanguard shock discipline, volcanic terrain ambushes.

---

## 4. Profession Hooks & Rigs
- Primary professions: Guard, Sentry, Garrison Captain, Watchman, Shield-Bearer, Scout, Archer.
- Rig integration: Soldier / Knight rigs, watchtower animation hooks, formation march cycles.

---

## 5. Mechanical Effect Bounds
- `defense_bonus`: `[0.00, +0.30]`
- `patrol_efficiency`: `[0.00, +0.35]`
- `combat_power_multiplier`: `[-0.15, +0.25]`
- `attrition_reduction`: `[0.00, +0.25]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "tactics_warfare_vol001_murder_holes",
    "subject": "tactics_and_warfare",
    "target_section": "military_tactics",
    "fact_key": "tactics_and_warfare.siege.gate_murder_holes",
    "title": "Murder Holes and Transverse Gate Defense",
    "summary": "Engineering and tactical employment of overhead murder holes in vaulted gatehouse passageways to break battering rams and breach attempts.",
    "body": "When invaders force outer wooden iron-studded gates, they enter the transverse vaulted killing tunnel before the portcullis. Overhead ceiling slots, spaced at one-meter intervals, allow defending sentries to pour boiling pitch, heated sand, and downward thrusts of boar-spears directly onto the ram crews. This position denies siege crews shield roofs and breaks enemy momentum.",
    "author": "Captain Vane of the Iron Gate",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["fortification", "gate_defense", "murder_hole", "siege"],
    "prerequisites": [],
    "mechanical_effects": {
      "defense_bonus": 0.14,
      "attrition_reduction": 0.08
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "tactics_warfare_vol001_sentry_lantern_signals",
    "subject": "tactics_and_warfare",
    "target_section": "military_tactics",
    "fact_key": "tactics_and_warfare.patrol.lantern_signal_cadence",
    "title": "Dual-Lantern Perimeter Sentry Relay",
    "summary": "Codified shuttered lantern rhythms enabling perimeter boundary watchtowers to verify post status every quarter-hour without alerting hostile scouts.",
    "body": "Perimeter outposts across fifteen-meter borders communicate via dual brass shuttered lanterns. A steady horizontal sweep followed by two rapid vertical flashes signals an all-clear post. Absence of response within thirty pulses triggers the immediate sounding of horn relays and muster of town-guard reaction squads.",
    "author": "Sergeant Kaelen",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["patrol", "sentry", "signals", "watchtower"],
    "prerequisites": [],
    "mechanical_effects": {
      "patrol_efficiency": 0.18
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
