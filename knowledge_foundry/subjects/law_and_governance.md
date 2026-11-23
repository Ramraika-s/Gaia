# Law and Governance (`law_and_governance`) — Authoring Guide

## 1. Scope & Domain Definition
The `law_and_governance` domain encompasses judicial trials, statutory jurisprudence, civil charters, CombatContext defense doctrines, restitution torts (replacing blood-feuds with graded wergild damages), council representation, municipal bylaws, and settlement elevation criteria.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `law_and_governance.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `judiciary`: Witness oath rules, burden of proof, combat context evaluation, magistrate trial benches.
- `torts`: Property damage appraisal, battery compensation scales, livestock trespass restitution.
- `charters`: Free City neutrality covenants, village-to-town elevation charters, guild monopolies.
- `citizenship`: Dynastic land inheritance, probate escheatment, resident alien rights.
- `councils`: Elder quorum voting, Two-Book proposal drafting, mayoral elections.

---

## 3. Tone & Voice
- **Tone:** Impartial, solemn, authoritative, procedural.
- **Style:** Legal codes, judicial benchbooks, statutory acts, town charters.
- **Racial Considerations:**
  - *Elf:* Long-horizon environmental covenants, customary elder arbitration.
  - *Dwarf:* Rigid written statute books, immutable clan contracts, debt oaths.
  - *Demon:* Strict evidentiary tribunals, harsh penalties for breach of oath, combat duel protocols.
  - *Beasthuman:* Kin council circles, territory boundary markings, pack arbitration.
  - *Human:* Tiered magistrate courts, representative elder councils, written charters.

---

## 4. Profession Hooks & Rigs
- Primary professions: Magistrate, Judge, Clerk, Bailiff, Town Elder, Chancellor.
- Rig integration: Gavel striking, scroll unrolling, swearing witness oaths.

---

## 5. Mechanical Effect Bounds
- `judicial_accuracy`: `[0.00, +0.35]`
- `civil_stability_bonus`: `[0.00, +0.30]`
- `reputation_bonus`: `[0.00, +0.25]`
- `trade_fee_reduction`: `[0.00, +0.15]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "law_gov_vol001_contextual_combat_immunity",
    "subject": "law_and_governance",
    "target_section": "jurisprudence_and_torts",
    "fact_key": "law_and_governance.judiciary.combat_context_immunity",
    "title": "Mandatory Inquiry into Combat Context and Self-Defense Immunity",
    "summary": "Prohibiting homicide convictions when the accused acted under verified SELF_DEFENSE, DEFENDING_KIN, or ACTIVE_WAR circumstances.",
    "body": "Early tribunals imposed automatic exile upon anyone who shed blood, ignoring whether the defendant was an unprovoked aggressor or a victim defending their children. Codified contextual jurisprudence requires magistrates to examine physical evidence and credible witnesses to establish CombatContext prior to verdict. Verified self-defense confers total civil and criminal immunity, preventing retaliatory vendettas.",
    "author": "Chief Justice Theodoric",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["judiciary", "law", "self_defense", "combat_context", "justice"],
    "prerequisites": [],
    "mechanical_effects": {
      "judicial_accuracy": 0.25,
      "civil_stability_bonus": 0.18
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "law_gov_vol001_graded_restitution_wergild",
    "subject": "law_and_governance",
    "target_section": "jurisprudence_and_torts",
    "fact_key": "law_and_governance.torts.graded_property_restitution",
    "title": "Graded Restitution Tariffs for Bodily Harm and Property Trespass",
    "summary": "Substituting endless dynastic blood-feuds with audited monetary restitution schedules enforced by town bailiffs.",
    "body": "Unregulated blood-feuds quickly decimate growing settlements as families avenge injuries with counter-murders. Enacting codified restitution schedules assigns precise silver valuations to broken bones, lost livestock, and charred storehouses. When damages are audited by the magistrate and transferred via bank draft, the injured party must declare full reconciliation under penalty of outlawry.",
    "author": "Magistrate Sula",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["torts", "restitution", "civil_code", "damages", "feud_prevention"],
    "prerequisites": ["law_and_governance.judiciary.combat_context_immunity"],
    "mechanical_effects": {
      "civil_stability_bonus": 0.22,
      "judicial_accuracy": 0.15
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
