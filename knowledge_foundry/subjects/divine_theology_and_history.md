# Divine Theology and History (`divine_theology_and_history`) — Authoring Guide

## 1. Scope & Domain Definition
The `divine_theology_and_history` domain encompasses cosmology, the Divine Hierarchy (God as creator, World Goddess as universal mediator and critic, and the 5 Racial God-Mothers as patron daughters), altar liturgy, prayer devotion mechanics, the Non-Aggression Covenant, and the Two-Book Governance rules.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `divine_theology_and_history.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `hierarchy`: God, World Goddess, the 5 Daughters, mortal oracles, prayer heads.
- `covenants`: Non-Aggression Covenant, age-10 mixed-race patronage choice, divine truces.
- `liturgy`: Altar consecration, congregational incense rites, faith renewal, hymns.
- `scripture`: The Two-Book doctrine, World Library laws, Divine Codex decrees.
- `pantheon`: Racial patron traits (`gm_human`, `gm_elf`, `gm_dragon`, `gm_beasthuman`, `gm_demon`).

---

## 3. Tone & Voice
- **Tone:** Reverent, sacred, mythic, doctrinal, transcendent.
- **Style:** Sacred scripture, liturgical canon, high-temple historical chronicles.
- **Racial Considerations:**
  - *Human:* Zealous altar congregations, communal singing, widespread shrines.
  - *Elf:* Sacred tree grove communions, whispering wind prayers to `gm_elf`.
  - *Dragon:* Solitary mountaintop altars, solemn oaths of ancient fire to `gm_dragon`.
  - *Beasthuman:* Tribal totemic carvings, ancestor blessings via `gm_beasthuman`.
  - *Demon:* Fierce abyssal covenant loyalty, solemn discipline rites honoring `gm_demon`.

---

## 4. Profession Hooks & Rigs
- Primary professions: Priest, High Oracle, Prayer Head, Temple Scribe, Monk.
- Rig integration: Kneeling in prayer, raising holy censor, blessing congregation.

---

## 5. Mechanical Effect Bounds
- `faith_devotion_bonus`: `[0.00, +0.30]`
- `divine_favor_generation`: `[0.00, +0.25]`
- `civil_stability_bonus`: `[0.00, +0.25]`
- `healing_rate_bonus`: `[0.00, +0.15]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "divine_theo_vol001_consecration_of_altar_foci",
    "subject": "divine_theology_and_history",
    "target_section": "divine_covenants_and_rites",
    "fact_key": "divine_theology_and_history.liturgy.altar_foci_consecration",
    "title": "Consecration of the Central Altar Focus and Prayer Head Communion",
    "summary": "Laying blessed granite focus stones beneath temple altars to harmonize mortal prayer resonance and channel faith to the racial patron God-Mother.",
    "body": "When mortals pray in scattered fields, their voices rise as dispersed whispers. Consecrating a dedicated stone altar with fragrant cedar smoke and holy spring water anchors a tangible spiritual focus. When an appointed Prayer Head leads the assembly in unison, faith devotion generates steady spiritual communion that replenishes the racial God-Mother's divine grace.",
    "author": "High Priestess Althea",
    "author_type": "DIVINE",
    "era_tier": 1,
    "tags": ["theology", "altar", "prayer", "faith", "liturgy"],
    "prerequisites": [],
    "mechanical_effects": {
      "faith_devotion_bonus": 0.22,
      "divine_favor_generation": 0.15
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "divine_theo_vol001_covenant_of_sisterly_truce",
    "subject": "divine_theology_and_history",
    "target_section": "divine_covenants_and_rites",
    "fact_key": "divine_theology_and_history.covenants.sisterly_divine_truce",
    "title": "The Covenant of the Divine Truce and Sisterly Restraint",
    "summary": "The sacred inter-sister treaty preventing racial God-Mothers from smiting rival civilian settlements and establishing mutual restraint.",
    "body": "Lest divine daughters lay waste to the mortal realms in fraternal disputes, the World Goddess inscribed the Non-Aggression Covenant into the Divine Codex. No God-Mother may strike down unarmed civilians of a sister's faith. When mortal kingdoms wage war, patron deities may bolster their champions with courage and warding winds, but direct cataclysms are strictly forbidden under penalty of divine banishment.",
    "author": "Oracle Vespera",
    "author_type": "DIVINE",
    "era_tier": 1,
    "tags": ["theology", "covenant", "divine_codex", "godmother", "truce"],
    "prerequisites": [],
    "mechanical_effects": {
      "civil_stability_bonus": 0.20
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
