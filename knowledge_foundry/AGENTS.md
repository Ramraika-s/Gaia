# AGENTS.md — Knowledge Foundry Master Authoring Rules

## 1. Purpose & System Identity
The **Knowledge Foundry** is the canonical authoring repository for the **Gaia v4.0 AI Civilization Engine**. It provides a self-contained, standalone authoring environment where human authors and AI agents can author, curate, and review high-quality reference books for the `world_library` without needing to inspect low-level simulation or engine code.

Books authored here represent mortal craftsmanship, divine decrees, scientific treatises, economic ledgers, philosophical discourses, and military manuals that directly influence autonomous agents across the 5 races (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`).

---

## 2. Fundamental Authoring Invariants

1. **Tone & Setting (Stylized Anime-Fantasy Realism):**
   - Ground all texts in a cohesive anime-fantasy world with tangible physical, biological, and magical laws.
   - Maintain a scholarly, dignified, didactic, or empirical voice appropriate for the topic and author.
   - Respect the 5 races, their racial traits, developmental gates, and divine patron lineages.

2. **Absolute Ban on Modern Anachronisms:**
   - **Zero modern or real-world technological terms.**
   - Strictly forbidden words include (but are not limited to): `internet`, `smartphone`, `electricity`, `nuclear`, `wikipedia`, `steam engine`, `computer`, `silicon`, `plastic`, `wifi`, `television`, `satellite`, `diesel`, `gasoline`, `robotics`, `semiconductor`, `quantum`, `laser`, `microchip`, `transistor`, `nanotech`.
   - The Stage 0 validator will immediately **HARD_FAIL** any entry containing these terms or modern idioms.

3. **Strict Entry Limits per File (Hard Cap `<= 30` Entries):**
   - Every staged JSON file must contain between **1 and 30 entries** (`1 <= len(entries) <= 30`).
   - Any file containing 0 entries or more than 30 entries will be rejected at Stage 0 schema validation.
   - Aim for cohesive thematic volumes of **8 to 15 entries** per file.

4. **File Naming & Directory Placement:**
   - Place all staging packs in the appropriate subject directory under `data/knowledge/<subject>/`.
   - File naming convention:
     - Reference works: `vol_XXX_<snake_case_theme>.json` (e.g., `vol_001_gate_defense_and_patrols.json`).
     - Mortal or character treatises: `scribe_<author_name>_<topic>.json` or `tract_<author_name>_<theme>.json`.
   - Never write directly to `data/knowledge/_merged_archive/` or `data/knowledge/_mortal_authored/`.

5. **Never Edit `data/civilization.db` Directly:**
   - Authors, scripts, and AI agents must **never** modify the SQLite database directly.
   - Changes enter `world_library` exclusively through `scripts/knowledge_merge.py` (which routes through `WorldGoddessCritic`) or the in-simulation Mortal Book Petition governance pipeline (`sim_core/society/library.py`).

6. **Mandatory Pre-Submission Review:**
   - Always run the review tool before requesting a merge:
     ```bash
     uv run python scripts/knowledge_review.py
     ```
   - All packs must pass with **0 blocks** (`HARD_FAIL`, `HARD_DUPLICATE`, `LEXICAL_DUPLICATE`, `SEMANTIC_DUPLICATE`).

---

## 3. The 10 Canonical Subjects

Every book and entry belongs to exactly one of the 10 canonical subjects:

| # | Subject Identifier | Domain Scope | Primary Professions / Rigs |
|---|---|---|---|
| 1 | `tactics_and_warfare` | Sieges, skirmishes, fortifications, patrol routes, logistics | Soldier, Guard, Commander, Watchman |
| 2 | `craft_and_metallurgy` | Smelting, forging, alloy tempering, toolcraft, jewelry | Blacksmith, Armorer, Goldsmith, Artisan |
| 3 | `architecture_and_engineering` | Stonemasonry, aqueducts, arches, timber framing, roads | Mason, Architect, Carpenter, Engineer |
| 4 | `agriculture_and_botany` | Crop rotation, soils, herbalism, irrigation, granaries | Farmer, Herbalist, Forester, Miller |
| 5 | `medicine_and_biology` | Wound care, poultices, fever diagnosis, hygiene, anatomy | Physician, Apothecary, Midwife, Healer |
| 6 | `economics_and_trade` | Price clearing, credit, double-entry ledgers, caravans, tariffs | Merchant, Banker, Clerk, Caravan Master |
| 7 | `law_and_governance` | Restitution torts, evidentiary proof, councils, charters | Magistrate, Judge, Elder, Chancellor |
| 8 | `philosophy_and_culture` | Logic, ethics, burial rites, theater, culinary arts, holidays | Scholar, Bard, Monk, Philosopher |
| 9 | `natural_history_and_geography` | Biomes, waterways, mountain crags, beast behavior, seasons | Explorer, Cartographer, Ranger, Scout |
| 10 | `divine_theology_and_history` | God, World Goddess, 5 God-Mothers, holy covenants, altars | Priest, Oracle, Scribe, Inquisitor |

---

## 4. Entry Structure & Addressing

Each entry inside a pack must adhere strictly to `KnowledgeEntry`:
- **`entry_id`**: Globally unique string formatted as `<subject>_<author_or_source>_<snake_id>` (e.g. `tactics_warfare_vol001_murder_holes`).
- **`fact_key`**: Dot-notation string `<subject>.<subtopic>.<concept>` (e.g. `tactics_and_warfare.siege.gate_murder_holes`).
- **`target_section`**: The target subsection in the World Library (e.g. `military_tactics`, `metallurgy`, `macroeconomics`).
- **`title`**: Concise, evocative title (max 100 characters).
- **`summary`**: A 1-to-3 sentence synthesis of the concept and its practical implications (100–400 characters).
- **`body`**: A detailed scholarly treatise explaining historical origin, underlying principles, step-by-step instructions, and edge cases (300–2,500 characters).
- **`mechanical_effects`**: Dictionary mapping bounded game parameters to numeric deltas (e.g. `{"defense_bonus": 0.12}`).
- **`prerequisites`**: List of prerequisite `fact_key` identifiers required before an agent can study or practice this technique.
- **`supersedes`**: List of older `fact_key` or `entry_id` strings that this entry explicitly obsoletes and replaces.
- **`distinct_from`**: List of closely related `fact_key` or `entry_id` strings that this entry is intentionally distinct from (bypasses Stage 3 semantic duplicate flags).

---

## 5. Preventing & Resolving Duplicates

1. **Search Before Authoring:** Check existing entries in `world_library` and staged files to verify your proposed concept is truly novel.
2. **Explicit Specialization:** Give entries distinct contexts, methods, materials, or target races rather than generic restatements.
3. **Using `supersedes`:** If an entry is an intentional upgrade, revised edition, or doctrinal replacement of an existing entry, list the superseded entry ID in `supersedes: ["<entry_id_or_fact_key>"]`.
4. **Using `distinct_from`:** If two entries discuss related concepts (e.g., *Cast Bronze Smelting* vs. *Crucible Steel Refinement*) and share similar vocabulary, add the related entry key to `distinct_from: ["<related_entry_id>"]` to instruct the Stage 3 validator that the semantic similarity is intentional.
