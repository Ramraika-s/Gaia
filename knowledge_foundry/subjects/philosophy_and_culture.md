# Philosophy and Culture (`philosophy_and_culture`) — Authoring Guide

## 1. Scope & Domain Definition
The `philosophy_and_culture` domain encompasses ethical epistemology, logic syllogisms, communal festive traditions, burial ceremonies, poetry, theater, music, culinary traditions, and cultural memes across the 5 races.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `philosophy_and_culture.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `ethics`: Reciprocity, moral responsibility, civic duty, temperance.
- `epistemology`: Empirical observation vs intuition, skepticism, dialectics.
- `traditions`: Solstice festivals, coming-of-age tests, hearth ceremonies.
- `arts`: Choral polyphony, epic poetry meter, mural painting, tragedy plays.
- `burial`: Cremation pyres, cairn entombment, ancestor epitaph carving.

---

## 3. Tone & Voice
- **Tone:** Contemplative, eloquent, humanist, transcendent.
- **Style:** Philosophical dialogues, bardic treatises, aesthetic critiques, moral essays.
- **Racial Considerations:**
  - *Elf:* Multicentury contemplative perspectives, harmonic music, sacred grove meditations.
  - *Dwarf:* Clan ancestor memory hymns, stone-carved lineage verses, solemn ale-halls.
  - *Demon:* Will-to-mastery ethics, fierce meritocratic individualism, incandescent passion.
  - *Beasthuman:* Kinship pack solidarity, oral storytelling around bone fires, dance circles.
  - *Human:* Adaptable civic humanism, theatrical satire, seasonal holiday merrymaking.

---

## 4. Profession Hooks & Rigs
- Primary professions: Philosopher, Bard, Scribe, Sculptor, Dramatist, Monk.
- Rig integration: Lute strumming, reciting scrolls to crowds, sculpting stone busts.

---

## 5. Mechanical Effect Bounds
- `civil_stability_bonus`: `[0.00, +0.30]`
- `faith_devotion_bonus`: `[0.00, +0.25]`
- `reputation_bonus`: `[0.00, +0.25]`
- `healing_rate_bonus`: `[0.00, +0.15]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "phil_cult_vol001_dialectical_inquiry",
    "subject": "philosophy_and_culture",
    "target_section": "arts_and_ethics",
    "fact_key": "philosophy_and_culture.epistemology.socratic_dialectics",
    "title": "Dialectical Cross-Examination in Public Forums",
    "summary": "Employing structured question-and-answer debate to strip away popular superstitions and arrive at verified axiomatic truths.",
    "body": "When town councils debate public policy based purely on emotional rhetoric or loud voices, catastrophic decisions follow. Structured dialectic forces both speaker and challenger to define their terms, identify hidden contradictions, and test hypotheses against observed facts. This method transforms angry shouting matches into rigorous civic deliberation.",
    "author": "Philosopher Lysander",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["philosophy", "logic", "dialectic", "civics", "debate"],
    "prerequisites": [],
    "mechanical_effects": {
      "civil_stability_bonus": 0.16,
      "reputation_bonus": 0.10
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "phil_cult_vol001_solstice_communal_hearth_rite",
    "subject": "philosophy_and_culture",
    "target_section": "arts_and_ethics",
    "fact_key": "philosophy_and_culture.traditions.midwinter_communal_hearth",
    "title": "Midwinter Hearth Gathering and Shared Provisions",
    "summary": "Mandatory communal feast at the winter solstice where rich households share preserved fruits and spiced cider with struggling laborers.",
    "body": "Midwinter cold breeds despair and social resentment in stratified settlements. Instituting the communal hearth rite brings all citizens into the town hall to rekindle a central oak log. Wealthy landowners contribute barrels of salt meat and spiced wine, while artisans sing ballads of past survivals, renewing mutual loyalty and preventing winter riots.",
    "author": "Arch-Bard Vivienne",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["traditions", "culture", "midwinter", "feast", "harmony"],
    "prerequisites": [],
    "mechanical_effects": {
      "civil_stability_bonus": 0.20,
      "faith_devotion_bonus": 0.12
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
