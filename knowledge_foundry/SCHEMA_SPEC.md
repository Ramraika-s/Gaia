# SCHEMA_SPEC.md — Knowledge Foundry JSON Schema & Effects Specification

## 1. Overview
All knowledge packs staged in `data/knowledge/` must be valid JSON files conforming to the `KnowledgePack` schema. A pack consists of a collection of 1 to 30 `KnowledgeEntry` objects.

---

## 2. Pydantic v2 Schema Definition

```python
from typing import Literal
from pydantic import BaseModel, Field

class KnowledgeEntry(BaseModel):
    entry_id: str = Field(
        ...,
        pattern=r"^[a-z0-9_]{4,64}$",
        description="Unique identifier, snake_case (e.g. tactics_warfare_vol001_murder_holes)"
    )
    subject: Literal[
        "tactics_and_warfare",
        "craft_and_metallurgy",
        "architecture_and_engineering",
        "agriculture_and_botany",
        "medicine_and_biology",
        "economics_and_trade",
        "law_and_governance",
        "philosophy_and_culture",
        "natural_history_and_geography",
        "divine_theology_and_history"
    ]
    target_section: str = Field(
        ...,
        min_length=2,
        max_length=48,
        description="World Library section (e.g. military_tactics, metallurgy, macroeconomics)"
    )
    fact_key: str = Field(
        ...,
        pattern=r"^[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+$",
        description="Dot-notation key: <subject>.<subtopic>.<concept>"
    )
    title: str = Field(..., min_length=4, max_length=120)
    summary: str = Field(..., min_length=40, max_length=500)
    body: str = Field(..., min_length=150, max_length=4000)
    author: str = Field(..., min_length=2, max_length=64)
    author_type: Literal["DIVINE", "MORTAL", "SYSTEM", "UNKNOWN"] = "MORTAL"
    era_tier: int = Field(default=1, ge=1, le=5)
    tags: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    prerequisites: list[str] = Field(default_factory=list, max_length=10)
    mechanical_effects: dict[str, float] = Field(default_factory=dict)
    supersedes: list[str] = Field(default_factory=list)
    distinct_from: list[str] = Field(default_factory=list)

class KnowledgePack(BaseModel):
    pack_id: str | None = None
    entries: list[KnowledgeEntry] = Field(..., min_length=1, max_length=30)
```

---

## 3. Field Specifications & Constraints

### 3.1 `entry_id`
- Regex: `^[a-z0-9_]{4,64}$`
- Must be globally unique across all packs and the live `world_library`.
- Recommended format: `<subject_short>_<pack_id_or_author>_<concept_slug>`.
- Example: `tactics_vol001_murder_holes`, `craft_vol001_bloomery_smelting`.

### 3.2 `fact_key`
- Regex: `^[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+$`
- Exactly three dot-separated components:
  1. `<subject>`: Must match or closely correspond to the subject (e.g. `tactics_and_warfare`).
  2. `<subtopic>`: Functional category (e.g. `siege`, `smelting`, `irrigation`, `torts`).
  3. `<concept>`: The specific doctrine, recipe, or theorem (e.g. `murder_holes`, `bloomery`, `levee_sluice`).
- Example: `tactics_and_warfare.siege.gate_murder_holes`.

### 3.3 `target_section`
Allowed canonical section names in the World Library:
- `military_tactics` (maps to `tactics_and_warfare`)
- `metallurgy_and_smithing` (maps to `craft_and_metallurgy`)
- `civil_engineering` (maps to `architecture_and_engineering`)
- `agronomy_and_herbalism` (maps to `agriculture_and_botany`)
- `healing_and_anatomy` (maps to `medicine_and_biology`)
- `commerce_and_banking` (maps to `economics_and_trade`)
- `jurisprudence_and_torts` (maps to `law_and_governance`)
- `arts_and_ethics` (maps to `philosophy_and_culture`)
- `cartography_and_beasts` (maps to `natural_history_and_geography`)
- `divine_covenants_and_rites` (maps to `divine_theology_and_history`)

Custom sub-sections (e.g. `naval_tactics`, `alloy_craft`, `court_procedure`) are permitted if they match `^[a-z0-9_]{2,48}$`.

### 3.4 `tags`
- Array of 1 to 12 lowercased snake_case descriptors.
- Example: `["fortification", "gate_defense", "arrow_slit", "murder_hole"]`.

---

## 4. Mechanical Effects Catalog & Bounding Rules

Mechanical effects grant gameplay bonuses or modifiers to settlements, guilds, or practicing agents. All values must be bounded within conservative multipliers to maintain economic and martial balance.

| Effect Key | Bounded Range | Description |
|---|---|---|
| `defense_bonus` | `[-0.30, +0.30]` | Settlement defensive wall/gate resilience modifier |
| `combat_power_multiplier` | `[-0.25, +0.25]` | Unit tactical combat strength bonus |
| `patrol_efficiency` | `[0.00, +0.35]` | Crime detection and perimeter response speed |
| `craft_speed_bonus` | `[-0.20, +0.35]` | Workshop fabrication rate |
| `smelting_yield_bonus` | `[0.00, +0.30]` | Metal recovery percentage per unit ore |
| `tool_durability_bonus` | `[0.00, +0.40]` | Lifespan of forged tools and weapons |
| `construction_cost_reduction` | `[0.00, +0.25]` | Material requirement reduction for buildings |
| `structural_integrity_bonus` | `[0.00, +0.35]` | Building durability and earthquake/siege resistance |
| `crop_yield_bonus` | `[-0.20, +0.35]` | Harvest output per acre |
| `spoilage_reduction` | `[0.00, +0.40]` | Granary spoilage and rot mitigation rate |
| `winter_hardiness` | `[0.00, +0.35]` | Frost and cold weather survival bonus |
| `healing_rate_bonus` | `[0.00, +0.40]` | Wound and injury recovery velocity |
| `infection_resistance` | `[0.00, +0.50]` | Sepsis and contagion prevention probability |
| `trade_fee_reduction` | `[0.00, +0.25]` | World Trade Centre tariff discount |
| `market_clearing_efficiency` | `[0.00, +0.30]` | Order-book bid/ask matching velocity |
| `credit_default_reduction` | `[0.00, +0.30]` | World Bank loan repayment reliability |
| `civil_stability_bonus` | `[-0.25, +0.25]` | Unrest reduction and civic satisfaction |
| `judicial_accuracy` | `[0.00, +0.35]` | Proper attribution of CombatContext vs malice |
| `faith_devotion_bonus` | `[-0.20, +0.30]` | Daily faith gain at altars and temples |
| `divine_favor_generation` | `[0.00, +0.25]` | Racial God-Mother divine energy recovery rate |

---

## 5. Duplicate Exemption Rules (`supersedes` & `distinct_from`)

The 3-stage deduplication engine evaluates both exact lexical matching and semantic vector proximity. Use these fields to clarify intentional relationships:

### 5.1 `supersedes`
- List of existing `entry_id` or `fact_key` values.
- **Effect:** If this entry matches or is semantically similar to an entry it explicitly supersedes, the deduplicator recognizes this as an authorized revision or upgrade. During merge, the older entry is archived or updated.
- **Example:** A treatise on *Hydraulic Lime Mortar* supersedes an older treatise on *Crude Clay Mud Binding*.

### 5.2 `distinct_from`
- List of related `entry_id` or `fact_key` values.
- **Effect:** If two entries discuss closely related topics (e.g. *Cold Forging of Iron* vs. *Hot Forging of High-Carbon Steel*), Stage 3 vector similarity may exceed `0.88`. Adding the other entry to `distinct_from` whitelists the pairing, preventing a false-positive `SEMANTIC_DUPLICATE` block.
