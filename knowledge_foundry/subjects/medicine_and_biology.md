# Medicine and Biology (`medicine_and_biology`) — Authoring Guide

## 1. Scope & Domain Definition
The `medicine_and_biology` domain covers mortal healing, wound irrigation, splinting fractures, herbal poultices, fever diagnosis, clean water hygiene, childbirth support, contagion quarantine, and the physiological differences across the 5 races.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `medicine_and_biology.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `wound_care`: Boiled linen dressings, honey salves, stitched incisions, cautery.
- `pharmacology`: Willow bark extracts (febrifuge), poppy infusions, garlic broths.
- `hygiene`: Boiling drinking water, latrine isolation, lime-washing sickrooms.
- `obstetrics`: Midwifery techniques, cross-species gestation care, infant colic soothing.
- `racial_biology`: Dragon scales and thermal shock, Elf metabolic longevity, Dwarf bone density.

---

## 3. Tone & Voice
- **Tone:** Compassionate, clinical, rigorous, life-preserving.
- **Style:** Healer's clinical notes, apothecary recipe scrolls, midwife handbooks.
- **Racial Considerations:**
  - *Elf:* Rapid cellular regeneration, susceptibility to blight poisons, longevity medicine.
  - *Dwarf:* Heavy pulmonary stone-dust clearing, dense skeleton fracture splints.
  - *Demon:* High fever tolerance, abyssal wound cauterization, toxin neutralization.
  - *Dragon:* Scale molt maintenance, respiratory lung valve cooling after fire exhalation.
  - *Beasthuman:* Accelerated muscle recovery, keen scent-based trauma diagnosis.

---

## 4. Profession Hooks & Rigs
- Primary professions: Physician, Apothecary, Midwife, Herbal Healer, Infirmary Nurse.
- Rig integration: Grinding mortar and pestle, bandaging limbs, boiling cauldron infusions.

---

## 5. Mechanical Effect Bounds
- `healing_rate_bonus`: `[0.00, +0.40]`
- `infection_resistance`: `[0.00, +0.50]`
- `fertility_rate_bonus`: `[0.00, +0.20]`
- `winter_hardiness`: `[0.00, +0.25]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "med_bio_vol001_raw_honey_wound_dressing",
    "subject": "medicine_and_biology",
    "target_section": "healing_and_anatomy",
    "fact_key": "medicine_and_biology.wound_care.raw_honey_salve",
    "title": "Raw Meadow Honey and Boiled Linen Wound Dressings",
    "summary": "Application of unheated meadow honey beneath boiled linen bandages to draw moisture from infected lesions and accelerate tissue closure.",
    "body": "Combat lacerations bound with dirty cloth fester rapidly into mortal gangrene. Washing open wounds with boiled spring water and packing them with unheated mountain honey creates an osmotic barrier that desiccates bacterial colonies while keeping healing flesh moist. Bandages must be boiled in lye water and dried in direct sunlight prior to wrapping.",
    "author": "Healer Saphira",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["medicine", "wound_care", "honey", "infection", "healing"],
    "prerequisites": [],
    "mechanical_effects": {
      "healing_rate_bonus": 0.22,
      "infection_resistance": 0.28
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "med_bio_vol001_willow_bark_salicin_decoction",
    "subject": "medicine_and_biology",
    "target_section": "healing_and_anatomy",
    "fact_key": "medicine_and_biology.pharmacology.willow_bark_decoction",
    "title": "White Willow Bark Decoction for Fever and Ague",
    "summary": "Simmering dried inner white willow bark into a bitter tea to reduce high fevers and relieve debilitating joint pain during winter epidemics.",
    "body": "When cold autumn rains bring fever shaking and aching bones across the settlement, harvest the bitter green inner bark of mature white willow trees. Slowly simmering two handfuls in four pints of clean water until reduced by half extracts active salicin compounds. Administered in small warm cups thrice daily, it breaks high fevers without upsetting the patient's stomach.",
    "author": "Apothecary Timothy",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["pharmacology", "herbalism", "fever", "willow_bark", "medicine"],
    "prerequisites": [],
    "mechanical_effects": {
      "healing_rate_bonus": 0.15,
      "winter_hardiness": 0.12
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
