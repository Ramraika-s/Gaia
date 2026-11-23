# DEDUPE_AND_REVIEW_PLAYBOOK.md — Author Review & Verification Guide

## 1. Quick Start Workflow

Before submitting or merging any knowledge pack, follow this standard three-step sequence:

```bash
# Step 1: Run fast 3-stage pre-merge review
uv run python scripts/knowledge_review.py

# Step 2: Test merge in dry-run mode (zero database writes)
uv run python scripts/knowledge_merge.py --dry-run

# Step 3: Commit verified packs to world_library
uv run python scripts/knowledge_merge.py --commit
```

---

## 2. The 3-Stage Cascade Architecture

The review engine evaluates every staged JSON entry in `data/knowledge/` against:
1. **All other staged entries** in other files and directories.
2. **All existing entries in `world_library`** (from `data/civilization.db` or memory).

```
   Staged JSON Entry
           │
           ▼
┌─────────────────────────┐
│ Stage 0: Schema & Rules │ ──► Invalid schema, >30 entries, anachronism detected ──► [HARD_FAIL (Block)]
└─────────────────────────┘
           │ (Pass)
           ▼
┌─────────────────────────┐
│ Stage 1: Hash & ID Check│ ──► Identical normalized hash or ID/fact_key collision ──► [HARD_DUPLICATE (Block)]
└─────────────────────────┘
           │ (Pass)
           ▼
┌─────────────────────────┐
│ Stage 2: Lexical Fuzzy  │ ──► Word 3-gram & token-set similarity >= 0.82 ─────────► [LEXICAL_DUPLICATE (Block)]
└─────────────────────────┘
           │ (Pass)
           ▼
┌─────────────────────────┐
│ Stage 3: Semantic Vector│ ──► Cosine >= 0.88 ─────────────────────────────────────► [SEMANTIC_DUPLICATE (Block)]
│   & Conflict Detection  │ ──► Cosine 0.78 - 0.87 ─────────────────────────────────► [NEAR_DUPLICATE_REVIEW (Warning)]
└─────────────────────────┘ ──► Opposing mechanical effects (similarity >= 0.72) ────► [CONFLICT (Warning)]
           │ (Pass)
           ▼
       [PASSED]
```

---

## 3. Interpreting Review Results & Diagnostic Codes

### 3.1 `HARD_FAIL` (Stage 0 Block)
- **Cause:** Schema validation failure (missing required field, malformed `fact_key`, invalid subject), file contains more than 30 entries, or forbidden modern anachronism detected.
- **Resolution:**
  - Check the error log for the exact field or forbidden word.
  - Remove modern terms (e.g., replace `electricity` with `galvanic lightning arc` or `essence current`).
  - Split files with more than 30 entries into smaller thematic volumes.

### 3.2 `HARD_DUPLICATE` (Stage 1 Block)
- **Cause:**
  - `entry_id` collision with an existing book.
  - `fact_key` duplicate already registered in `world_library`.
  - Normalized content SHA-256 hash matches an existing entry exactly.
- **Resolution:**
  - Assign a unique, descriptive `entry_id`.
  - If intending to replace or update an existing entry, add the target entry ID to `supersedes: ["<target_id>"]`.

### 3.3 `LEXICAL_DUPLICATE` (Stage 2 Block)
- **Cause:** Word 3-gram Jaccard similarity or token-set ratio is `>= 0.82`. This occurs when text is superficially rephrased or plagiarized from an existing work.
- **Resolution:**
  - Re-author the text with novel concepts, unique empirical observations, or distinct technical procedures.
  - If the topic is genuinely distinct (e.g., *Cast Iron Smelting* vs *Wrought Iron Refining*), add the sibling entry key to `distinct_from: ["<sibling_id>"]`.

### 3.4 `SEMANTIC_DUPLICATE` (Stage 3 Block)
- **Cause:** Fast vectorized cosine similarity is `>= 0.88` between two entries that do not reference each other via `supersedes` or `distinct_from`.
- **Resolution:**
  - If the new entry is an authorized doctrine or technical update, set `supersedes: ["<existing_entry_id>"]`.
  - If the two entries represent distinct sub-fields sharing vocabulary, set `distinct_from: ["<existing_entry_id>"]`.

### 3.5 `NEAR_DUPLICATE_REVIEW` (Stage 3 Warning)
- **Cause:** Cosine similarity is between `0.78` and `0.87`. This does not automatically block commits in non-strict mode, but requires human author confirmation.
- **Resolution:**
  - Inspect the side-by-side snippet printed by `scripts/knowledge_review.py`.
  - Ensure the two concepts do not confuse practicing agents.

### 3.6 `CONFLICT` (Stage 3 Warning)
- **Cause:** Two entries share the same `subject`, overlapping `tags`, similarity `>= 0.72`, but provide opposing mechanical effect modifiers (e.g. one adds `+0.15 defense_bonus` while another adds `-0.15 defense_bonus`).
- **Resolution:**
  - If one entry is intended to correct the other, add `supersedes`.
  - If both represent legitimate divergent tactics (e.g., *Heavy Bastion Gate* vs. *Light Sally Gate*), add `distinct_from`.

---

## 4. Merge CLI Commands & Archive Safety

### 4.1 Running Dry-Run
```bash
uv run python scripts/knowledge_merge.py --dry-run
```
- Performs a complete Stage 0–3 audit.
- Verifies database connection and mock-evaluates all entries against `WorldGoddessCritic`.
- Outputs a detailed projection of books to be inserted or updated.
- Makes **zero changes** to disk or SQLite.

### 4.2 Running Full Commit
```bash
uv run python scripts/knowledge_merge.py --commit
```
- Automatically halts if any `HARD_FAIL`, `HARD_DUPLICATE`, `LEXICAL_DUPLICATE`, or `SEMANTIC_DUPLICATE` exists.
- Inserts validated entries into SQLite table `world_library` within a single atomic transaction.
- Updates embedding vector cache `.cache/knowledge_embeddings.npz`.
- Moves merged JSON packs into `data/knowledge/_merged_archive/<timestamp>_<filename>.json` with a cryptographic audit stamp, guaranteeing they are never imported twice.
