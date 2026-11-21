# RACES_AND_BIOLOGY_SPEC.md — The 5 Races, Binary Gender, Sub-Lineages, Cross-Species Pregnancy, Dragon Metamorphosis & Inter-Racial Dynamics 

## 1. Core Biological Invariants (`sim_core/races.py`)
All mortal agents across the civilization adhere to three foundational biological contracts:

1. **Strict Binary Gender (`Gender = Literal["BOY", "GIRL"]`):**
   - Every mortal is born as either `BOY` or `GIRL` via a 50/50 deterministic RNG roll on `BIRTH`.
   - Displayed naturally by developmental stage (`Boy`/`Girl` for `INFANT`/`CHILD`; `Man`/`Woman` for `ADULT`/`ELDER`), driving cultural naming (`sim_core/society/naming.py`) and Godot modular hair/tunic presets.
   - Mating and conception strictly require opposite biological genders (`P1.gender != P2.gender`), enforced by `WorldGoddessCritic`.
2. **Extensible `RaceProfile` Multiplier Layer (Zero Neural Tensor Bloat):**
   - Racial biology, lifespans, gestation durations, neuroplasticity, combat power, seasonal resilience, and 3D bone scaling live in a deterministic **`RACE_REGISTRY`** (`sim_core/races.py`) rather than hardcoding race-specific dimensions into `SharedSkillNet` or `BatchedAgentSelfNet`.
   - This keeps neural checkpoints 100% compatible across all 5 races, Beasthuman sub-lineages, mixed-heritage offspring, and any future races added later.
3. **1-to-1 Divine Patronage:**
   - Each of the 5 races is watched over by its own **Racial God-Mother** (one of the 5 Daughters of God & the World Goddess; see `docs/simulation/DIVINE_HIERARCHY_SPEC.md`).

---

## 2. The 5 Races & Anime-Fantasy Profiles

### 2.1 Master Multiplier Table

| Race / Sub-Lineage | Base Max HP (`ADULT`) | Lifespan Mult ($L$) | Gestation (Game Days) | Breeding Cooldown Mult | Neuroplasticity Mult | Winter Resistance | Godot Base Rig & Adult Scale | Preferred Biome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`HUMAN`** | `100` | `1.0x` | **`1.5`** | `1.0x` | **`1.15x`** | `1.0x` | `base_human.glb` (`1.00x`) | Plains / Grasslands / Rivers |
| **`ELF`** | `95` | **`3.0x`** | **`4.0`** | `2.5x` | `1.00x` | `1.15x` | `base_elf.glb` (`1.06x`) | Dense Ancient Forests |
| **`DRAGON`** | **`280`** (Humanoid) / **`650`** (True) | **`6.0x`** | **`7.0`** | **`5.0x`** | `0.85x` | **`1.80x`** | `base_dragon_humanoid.glb` (`1.05x`) $\leftrightarrow$ `base_dragon_true.glb` (`3.80x`) | Volcanic / Alpine Mountain Crags |
| **`BEASTHUMAN: CAT_KIN`** | `90` | `1.0x` | **`1.2`** | `1.1x` | `1.05x` | `1.05x` | `base_beasthuman_agile.glb` (`0.98x`) | Forest Edges / Cities / Savanna |
| **`BEASTHUMAN: DWARF`** | `125` | `1.5x` | **`2.2`** | `1.4x` | `0.95x` | **`1.60x`** | `base_beasthuman_heavy.glb` (`0.75x H / 1.15x W`) | Mountain Foothills / Deep Mines |
| **`BEASTHUMAN: WOLF_KIN`** | `115` | `1.1x` | **`1.4`** | `1.1x` | `1.00x` | `1.35x` | `base_beasthuman_agile.glb` (`1.02x`) | Steppe / Taiga / Frontier |
| **`BEASTHUMAN: BARBARIAN / BEAR_KIN`** | `145` | `1.1x` | **`1.8`** | `1.2x` | `0.95x` | `1.45x` | `base_beasthuman_heavy.glb` (`1.18x H / 1.25x W`) | Northern Steppe / Highlands |
| **`DEMON`** | **`120`** | **`2.8x`** | **`4.0`** | `2.2x` | `1.05x` | **`1.50x`** | `base_demon.glb` (`1.08x`) | Volcanic / Ashland Crags & Obsidian Chasms |

*(Gestation durations scale proportionally to each race's lifespan and the 28-Game-Day calendar year; configurable in `sim_core/config.py`.)*

---

### 2.2 Detailed Racial Characteristics & Neural Priors
Trait priors bias initial founder and newborn `traits` (`[caution, sociability, ambition, loyalty, rule_respect, faith_devotion]`), while lifelong backpropagation and genetic mutation ($\mathcal{N}(0, 0.08)$) still allow rare individual exceptions.

#### 1. Humans (`HUMAN`)
- **Biology & Learning:** Baseline lifespan (`1.0x`), fast gestation (`1.5` days), fastest demographic growth, and highest neuroplasticity (`1.15x`), allowing Human societies to adapt rapidly to market shocks, warfare, and new World Library techniques.
- **Trait Priors:** `ambition +0.25`, `sociability +0.15`, `caution 0.0`, `loyalty 0.0`, `rule_respect +0.05`.
- **Social & Political Style:** Prolific builders, merchants, and bankers. Politically volatile—rapidly form Republics, Monarchies, WTC trading guilds, and frontier colonies.

#### 2. Elves (`ELF`)
- **Biology & Learning:** Long-lived (`3.0x` lifespan) with longer gestation (`4.0` days) and slow, deliberate population growth (`2.5x` breeding cooldown). Natural skill bonuses in `forage` (`+25%`), `self_care` (`+20%`), and `teach` (`+25%`).
- **Trait Priors:** `caution +0.20`, `loyalty +0.30`, `rule_respect +0.20`, `ambition -0.10`, `sociability` (high `+0.25` toward Elves, guarded `-0.20` baseline initial trust toward outsiders until proven reliable).
- **Social & Political Style:** Strong **in-group cohesion**—naturally cluster into forested Elven enclaves (`Sylvan Halls`), fiercely defend woodland borders against outsiders cutting timber, and accumulate deep multi-generational World Library scholarship.

#### 3. Dragons (`DRAGON`)
- **Biology & Learning:** Ancient lifespan (`6.0x`), longest gestation (`7.0` days), very rare births (`5.0x` breeding cooldown), immense natural durability and combat strength, and high environmental resilience (`1.80x` Winter resistance).
- **Trait Priors:** `caution +0.15`, `loyalty +0.35` (to Dragon kin/sanctuary), `ambition -0.25` (low desire to conquer outside lands), `sociability -0.25` (reclusive, non-interventionist by default).
- **Peaceful Non-Interventionist Nature:** Baseline unprovoked aggression is strongly suppressed. Dragons prefer living peacefully among themselves in isolated mountain sanctuaries and ignoring outside mortal politics—**with rare individual exceptions** emerging organically through genetic mutation or personal life experience (e.g., an ambitious Dragon visiting a Neutral Free City to trade, or a vengeful Dragon holding a grudge).

#### 4. Beasthuman (`BEASTHUMAN` — Umbrella Race with Sub-Lineages)
All Beasthuman sub-lineages share **one Racial God-Mother**, share full intra-race compatibility, and embody classic anime-fantasy diversity:
- **`CAT_KIN`:** Fast gestation (`1.2` days), high movement speed (`1.20x`), elevated curiosity and `forage`/`scout` efficiency (`+20%`), agile urban traders and forest scouts.
- **`DWARF`:** Longer gestation (`2.2` days), stocky build (`0.75x H / 1.15x W`), extreme `mine_stone` (`+35%`), `craft` (`+35%`), and `build` (`+25%`) mastery, high Winter resistance (`1.60x`), fierce guild/property loyalty (`rule_respect +0.25`, `loyalty +0.30`).
- **`WOLF_KIN`:** Gestation `1.4` days, high pack coordination (`loyalty +0.35`, `sociability +0.20` within clan), fast pursuit/scouting (`1.12x` speed), strong border patrols.
- **`BARBARIAN` / `BEAR_KIN`:** Gestation `1.8` days, high stamina and base health (`145`), strong cold resistance (`1.45x`), honor-driven frontier settlers and formidable melee defenders (`defend +25%`).

#### 5. Demons (`DEMON` — Unified Race, No Sub-Lineages)
- **Biology & Learning:** Lifespan `2.8x` (between Elf and Dragon), gestation `4.0` days, robust demonic constitution (`120` HP), high combat and magic/crafting proficiency, and strong winter resistance (`1.50x` native to volcanic/ashland crags).
- **Trait Priors & Emergent Temperament:**
  - `ambition +0.20`, `caution +0.10`, `loyalty +0.20`, `rule_respect -0.10`.
  - **Out-Group Hostility Bias:** Baseline initial suspicion and aggression bias toward non-Demon races, subject to per-agent Gaussian variation ($\mathcal{N}(0, 0.08)$) and lifetime reinforcement so peaceful, diplomatic, and trade-oriented Demons still emerge organically (preserving the NO global `good_vs_evil` scalar invariant).
  - **Generational Dragon Deterrence:** Because Dragons possess overwhelming apex strength (`650` HP in True Dragon form), Demons carry a strong learned/generational caution bias (`dragon_deterrence_bias`) and actively avoid provoking Dragons unless forced by immediate self-defense.
  - **High Reverence for `gm_demon`:** Demonstrates elevated baseline devotion/affinity toward the Demon God-Mother (`gm_demon`).
- **Social & Political Style:** Forgers of volcanic obsidian weapons, masters of abyssal metallurgy and dark enchanting. Form hierarchical volcanic strongholds and disciplined martial clans that selectively engage in external trade at the WTC.

---

## 3. Dragon Metamorphosis & Dragon Deterrence Mechanics

### 3.1 `HUMANOID_DRAGON` $\leftrightarrow$ `TRUE_DRAGON` State Machine
Every `ADULT` or `ELDER` Dragon maintains a live `dragon_form: Literal["HUMANOID_DRAGON", "TRUE_DRAGON"]` state (infants and children remain in `HUMANOID_DRAGON` form while maturing):

| Property | `HUMANOID_DRAGON` (Default) | `TRUE_DRAGON` (Metamorphosis) |
| :--- | :--- | :--- |
| **Godot Rig & Scale** | `base_dragon_humanoid.glb` (`1.05x`, folded wings/horns/tail) | `base_dragon_true.glb` (`3.80x`, 4-legged winged dragon) |
| **Combat & Mobility** | Strong humanoid fighter (`280` HP, `1.0x` walk) | Overwhelming apex power (`650` HP, `3.2x` attack, aerial flight `2.4x` speed) |
| **Stamina Burn** | `1.0x` normal | **`1.8x`** continuous drain while transformed |
| **Social Aura** | Peaceful; safe to enter Neutral Free Cities & WTC halls without panic | Emits a **`40m` Fear/Awe Aura** causing non-dragons with low bravery to flee and raising nearby infant `distress` |

#### Transformation Triggers (Deterministic + Neural)
A Dragon shifts from `HUMANOID_DRAGON` $\rightarrow$ `TRUE_DRAGON` when **any** of the following occur:
1. **Intentional Provocation:** Directly attacked/damaged (`SELF_DEFENSE`), Dragon kin harmed (`DEFENDING_KIN_OR_TOWN`), or hostile armed outsiders trespass onto a Dragon sanctuary parcel and refuse to leave.
2. **Active War Defense:** Defending Dragon borders during an `ACTIVE_WAR`.
3. **Long-Range Flight:** Traveling across mountain chasms or distances `> 250m` outside dense non-dragon cities.
4. **Rare Outlier Personality:** An individual Dragon whose mutated/learned `ambition` or aggression exceeds extreme thresholds voluntarily triggers `DEFEND_OR_ATTACK` in `TRUE_DRAGON` form.

#### Automatic Reversion
Shifts back to `HUMANOID_DRAGON` once no hostile threat remains within `48m` for `30` consecutive ticks, OR when `stamina < 15%`. In Godot 4.7.2, both meshes share a single `AgentRoot` pool node so switching forms toggles visibility, swaps the collision capsule, and fires `MetamorphosisBurst.tscn` with zero frame stutter.

### 3.2 Emergent "Dragon Deterrence" ("Don't Poke the Sleeping Giant")
- Because Dragons are peaceful unless provoked, there is **no hardcoded rule** stopping a Human or Beasthuman King from declaring war on a Dragon mountain sanctuary.
- However, any raiding party that provokes a sanctuary triggers `TRUE_DRAGON` counterattacks (`SELF_DEFENSE` / `DEFENDING_KIN_OR_TOWN`—legally justified, zero domestic crime).
- Surviving raiders flee home carrying high-salience **Rumor Packets** (*"A True Dragon leveled the vanguard at Ashpeak"*), and Elders eventually author **World Library** entries warning against Dragon border aggression—so over generations, mortal nations organically learn to respect Dragon sovereignty.

---

## 4. Mating, Race-Specific Pregnancy & Cross-Species Reproduction

### 4.1 Universal Opposite-Gender Compatibility (Cross-Species Allowed)
All 5 races (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`) **can mate with each other**, provided all biological and social prerequisites hold (validated by `WorldGoddessCritic`):
- **Strict Binary Gender Rule:** `P1.gender != P2.gender` (strictly one `BOY` and one `GIRL`).
- **Readiness:** Both are `ADULT`, alive, within `5m`, disjoint `parent_ids`, not currently pregnant (`mother.pregnant_ticks_remaining == 0`), `health >= 70%` of `max_health`, `hunger >= 60`, `breeding_cooldown == 0`, mutual `affinity >= 0.6`, and `trust >= 0.5`.
- **Dragon Mating Constraint:** Dragons must be in `HUMANOID_DRAGON` form when mating with non-dragon races.

### 4.2 Conception & Birth Survival Probabilities

| Pairing Type | Conception Chance (Woman Becomes Pregnant) | Offspring Birth Survival Chance | Notes |
| :--- | :--- | :--- | :--- |
| **Same Race** (incl. Beasthuman sub-lineages, e.g. `CAT_KIN` + `DWARF`) | **`100%`** (`1.00`) | **`95%`–`100%`** (baseline; reduced only by severe maternal starvation, illness, or injury) | Standard intra-species biology |
| **Different Species / Cross-Species** (`P1.race != P2.race`, e.g. `HUMAN` + `ELF`, `HUMAN` + `DRAGON`, `ELF` + `BEASTHUMAN`) | **`50%`** (`0.50`) | **`60%`** (`0.60`) | Biological incompatibility creates real conception and perinatal risk |

- **Failed Conception (`50%` roll on cross-species mating):** The woman does not become pregnant; both partners receive a short recovery cooldown (`0.25x` standard cooldown) so they do not spam mating proposals every tick.
- **Failed Birth Survival (`40%` risk on cross-species birth):** When gestation completes and the survival roll fails, **no neural tensor slot is allocated**. The stillbirth is committed via `WorldGoddessCritic` as a perinatal fatality (`cause="BIRTH_COMPLICATION"`, `stage_at_death="INFANT"`), incrementing the settlement's infant mortality index and applying realistic grief/distress to the parents (without triggering any criminal record).

### 4.3 Race-Specific Pregnancy (Gestation) Mechanics
Once conception succeeds, the female (`GIRL`) enters a tracked **pregnancy state** in RAM (`pregnant_ticks_remaining`, `father_id`, `is_cross_species_pregnancy`):
- **Gestation Duration:** Determined strictly by the **mother's** `RaceProfile.gestation_days` converted to sim ticks (`gestation_days * TICKS_PER_GAME_DAY`):
  - `CAT_KIN`: `1.2` days | `WOLF_KIN`: `1.4` days | `HUMAN`: `1.5` days | `BARBARIAN`/`BEAR_KIN`: `1.8` days | `DWARF`: `2.2` days | `DEMON`: `4.0` days | `ELF`: `4.0` days | `DRAGON`: `7.0` days.
- **Maternal Metabolic Cost:** During pregnancy, the mother experiences `1.15x` hunger drain and `0.90x` movement speed—encouraging partners, kin, and settlement welfare to keep her fed and sheltered.
- **Maternal Mortality:** If the mother dies before `pregnant_ticks_remaining` reaches `0`, the pregnancy ends immediately with her death.
- **Delivery (`BIRTH` Commit):** When `pregnant_ticks_remaining == 0`, the engine evaluates the birth survival roll (`0.60` if `is_cross_species_pregnancy`, else baseline). On survival, `WorldGoddessCritic` commits `BIRTH`, allocates a neural slot, and spawns the `INFANT`.

### 4.4 Offspring Inheritance, Phenotype Blending & Age-10 Mixed-Race Patronage Choice
- **Dominant Race & Sub-Lineage:**
  - **Same-Race:** Inherits the shared `race` (and for `BEASTHUMAN`, 50/50 RNG inherits one parent's `sub_lineage`) and is immediately placed under that race's **Racial God-Mother** (`patron_godmother_slot`).
  - **Cross-Species (Mixed-Race Child):** Inherits dominant biological `race` (and `sub_lineage`, if applicable) via a **50/50 RNG roll** between mother and father—determining the child's 3D base rig and `RaceProfile` multipliers—while recording the other parent's race in `secondary_heritage_race`.
- **Mixed-Race God-Mother Patronage Rule (Age 10 Biological Milestone):**
  - Biological age maps cleanly across all racial lifespans via `biological_age_years = (age_days / (6.0 * L)) * 18.0` (so `ADULT` = 18 biological years, and **10 years old** = `3.33 * L` game days, midway through `CHILD`).
  - **Under Age 10:** A mixed-race child starts with `patron_godmother_slot = None` (uncommitted). Both parental God-Mothers watch over the child, and the child accumulates separate `godmother_affinities[gm_slot]` scores driven by parental devotion, local settlement culture, and childhood prayers.
  - **At Age 10 (`PATRON_CHOICE` Milestone):**
    1. **Voluntary Choice:** The child chooses between the two parental God-Mothers (via `AgentSelfNet` preference + affinity) and submits a `PATRON_CHOICE` commit to `WorldGoddessCritic`.
    2. **Auto-Allocation on Non-Choice:** If the child does not actively choose within the decision window (`1.0` game day), the engine automatically assigns the child to whichever of the two parental God-Mothers has the **higher `godmother_affinities` score**.
    3. **World Goddess Tie-Breaker:** If the two affinities are tied (`|aff_a - aff_b| < 1e-4`), the decision escalates to the **World Goddess (Wife of God)**, who selects one of the two God-Mothers for the child (weighing settlement harmony and racial balance) and records the decree.
- **Visual Phenotype (`mortal_toon.gdshader`):**
  - **`skin_hsv` (`vec3`):** Midpoint of `P1.skin_hsv` and `P2.skin_hsv` + `±8%` bounded Gaussian mutation so families and mixed-heritage children visibly resemble both parents.
  - **`dynasty_surname`:** Inherited from parents.
  - **Clothing Tints (`cloth_primary`, `cloth_secondary`):** Dynamically driven by the agent's current **Nation/Settlement banner colors** (or **Religion robes** for Clerics/Popes).

---

## 5. Racial Economic Niches, Cultural Friction & Neutral Free Cities

### 5.1 Comparative Advantage on the World Trade Centre (WTC)
Distinct racial skill bonuses naturally drive **inter-racial trade** rather than isolated autarky:
- **Dwarves (`BEASTHUMAN`):** Dominate `stone`, `iron`, and `tools` production—supplying weapons, building materials, and mining gear to the WTC.
- **Elves (`ELF`):** Dominate `food`, forest herbs, and sustainable timber—becoming critical suppliers during harsh Winters.
- **Humans (`HUMAN`):** Dominate WTC logistics, World Bank finance, urban construction, and high-velocity commerce.
- **Dragons (`DRAGON`):** Control rare high-altitude mountain ores and ancient knowledge—trading occasionally in `HUMANOID_DRAGON` form for refined goods or peace accords.
- **Demons (`DEMON`):** Dominate obsidian metallurgy, dark enchanting, advanced weaponry, and resilient ashland masonry—trading for food, fine textiles, and alchemical elixirs.

### 5.2 Cultural Friction & Neutral Free Cities
- **Natural Friction:** Human expansion into Elven forests, Dwarf mining disputes with mountain Dragons, Demon territorial assertiveness in ashland crags, or Beasthuman clan border raids create organic diplomatic tensions that also spill upward into **Inter-Sister Council** debates among the 5 Racial God-Mothers.
- **Neutral Free Cities:** Any `CITY` holding significant living populations of **`>= 2` races** (each `>= 15%` of city pop) may submit a `SETTLEMENT_APPEAL(requested_status="NEUTRAL_FREE_CITY")` to the **World Goddess**. Approved Neutral Free Cities:
  - Are legally barred from declaring offensive wars (`war_exempt = true`).
  - Serve as ideal neutral hosts for **WTC Regional Hubs**, **World Library Branches**, and multi-racial communities where inter-racial families and peaceful `HUMANOID_DRAGON` citizens live safely side-by-side.

---

## 6. Python Registry Contract (`sim_core/races.py`)

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

Gender = Literal["BOY", "GIRL"]
RaceId = Literal["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
BeasthumanSubLineage = Literal["CAT_KIN", "DWARF", "WOLF_KIN", "BARBARIAN", "BEAR_KIN"]
DragonForm = Literal["HUMANOID_DRAGON", "TRUE_DRAGON"]

CROSS_SPECIES_CONCEPTION_CHANCE: float = 0.50
CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE: float = 0.60

class RaceProfile(BaseModel):
    race_id: RaceId
    sub_lineage: Optional[BeasthumanSubLineage] = None
    patron_godmother_slot: str             # "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"
    base_max_health: float = 100.0
    lifespan_multiplier: float = 1.0
    gestation_days: float = 1.5            # Pregnancy duration in Game Days (mother's race)
    breeding_cooldown_mult: float = 1.0
    neuroplasticity_mult: float = 1.0
    winter_resistance: float = 1.0
    movement_speed_mult: float = 1.0
    adult_scale_height: float = 1.0
    adult_scale_width: float = 1.0
    can_metamorphose: bool = False
    true_dragon_health: float = 650.0
    true_dragon_scale: float = 3.8
    skill_affinities: dict[str, float] = Field(default_factory=dict)
    trait_priors: dict[str, float] = Field(default_factory=dict)
    compatible_breeding_races: list[RaceId] = Field(
        default_factory=lambda: ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
    )
```