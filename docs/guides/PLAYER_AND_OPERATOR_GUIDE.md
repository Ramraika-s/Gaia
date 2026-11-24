# PLAYER_AND_OPERATOR_GUIDE.md — Operator Handbook, Keybindings, CLI Reference & Governance Workflows

## 1. Quick Launch & Operating Modes

All commands MUST be run with `uv run` to ensure Python 3.12 binary wheel compatibility on Fedora Linux 45:

### 1.1 Standard Live Launch (Python Engine + Godot 4.7.2 Client)
```bash
# Launch with 1,500 initial agents and local LLM acceleration
uv run python scripts/launch_gaia.py --agents 1500 --speed 1.0
```

### 1.2 Offline / Zero-LLM Mode
```bash
# Launch without connecting to local llama.cpp (instantaneous deterministic dialogue)
uv run python scripts/launch_gaia.py --agents 1500 --no-llm
```

### 1.3 Headless Server Mode (Benchmarking, Soak Tests & CI)
```bash
# Launch simulation engine without launching the Godot 3D window
uv run python scripts/launch_gaia.py --agents 1500 --headless --speed 10.0
```

### 1.4 Command-Line Flags Reference (`scripts/launch_gaia.py`)
| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--agents` | `int` | `1500` | Initial population across the 5 races (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`). |
| `--speed` | `float` | `1.0` | Simulation tick speed multiplier (`1.0x` to `60.0x`). |
| `--host` | `str` | `127.0.0.1` | WebSocket server bind address. |
| `--port` | `int` | `8765` | WebSocket server bind port. |
| `--headless` | `bool` | `False` | Run Python simulation core headlessly without starting Godot. |
| `--fresh` | `bool` | `False` | Wipes existing `/tmp` or persistent DB checkpoints for a clean Day 0 boot. |
| `--no-llm` | `bool` | `False` | Disable connection to local `llama.cpp` server (uses deterministic offline fallback). |
| `--llm-url` | `str` | `http://127.0.0.1:8080` | Local `llama.cpp` HTTP server completion endpoint. |

---

## 2. In-Game Controls & Keybindings (Godot 4.7.2)

When running the Godot 3D client, you control the **God Avatar** (`CharacterBody3D`, `is_god = true`) or navigate in **Orbital RTS mode**:

| Key / Mouse Action | Mode | Function |
| :--- | :--- | :--- |
| **`Tab`** | Any | **Toggle View Mode:** Seamlessly switch between 3rd-Person God Avatar and Orbital RTS Camera. |
| **`WASD`** | Avatar / RTS | Move Avatar (3rd-person) / Pan Camera across the terrain (RTS). |
| **`Shift`** (Hold) | Avatar / RTS | Sprint (Avatar) / Fast Camera Pan (RTS). |
| **`Space`** | Avatar | Jump (Ground mode) / Ascend vertically (Flight mode). |
| **`Ctrl`** or **`C`** | Avatar | Crouch (Ground mode) / Descend vertically (Flight mode). |
| **`F`** | Avatar | **Toggle Divine Flight:** Toggle gravity physics on/off to fly freely across mountain peaks. |
| **`Alt`** | Avatar | **Release Mouse Capture:** Free cursor to click UI buttons and HUD elements. |
| **`Left-Click`** | Any | Recapture mouse in viewport / Select mortal or building in RTS mode. |
| **`Left-Click` (Target)** | Avatar / RTS | **Entity Inspector:** Open inspection modal for target mortal, deity, or building. |
| **`Esc`** | Any | **Close Modal:** Dismiss current open UI modal cleanly via `UiStateManager`. |
| **`Right-Click`** (Hold) | RTS | Orbit camera around current focal point. |
| **`Mouse Wheel`** | Avatar / RTS | Zoom camera distance ($2\text{m}$ shoulder zoom $\leftrightarrow$ $4,000\text{m}$ planetary orbital map). |
| **`E`** | Avatar | **Interact / Dialogue:** Open dialogue with a nearby Deity/Mortal or inspect a Library Lectern. |
| **`L`** | Any | **Two-Book Governance Modal:** Open the interactive World Library & Divine Codex viewer/editor. |
| **`B`** | Any | **Toggle Borders:** Show/hide explicit $16\text{m} \times 16\text{m}$ chunk parcel borders and decals. |
| **`` ` `` (Backtick)** or **`F1`** | Any | **God Console Overlay:** Toggle the in-engine Rich God Terminal command line. |

---

## 3. Terminal God Console CLI Reference (`sim_core/god_console/cli.py`)

The God Console provides direct runtime inspection and administrative powers:

### 3.1 Inspection Commands
- `status`: Displays current Game Day, Tick, Season, Living Population by race, WTC CPI, and Host RAM usage.
- `pop [race|settlement]`: Detailed demographic breakdown of living agents, infants, and gender distribution.
- `fatalities`: Lists recent fatalities by cause (`STARVATION`, `WINTER_EXPOSURE`, `COMBAT_WAR`, `OLD_AGE`, etc.).
- `crimes [agent_id]`: Inspects open and closed Judiciary cases, active warrants, and criminal records.
- `nations`: Lists sovereign polities, leaders, regime types (`KING`/`ELECTED`), and treasuries.
- `borders`: Shows total claimed $16\text{m} \times 16\text{m}$ parcels per settlement and border status.
- `elections`: Checks next scheduled election tick and incumbent standings.
- `religions`: Displays active religions, tenets, popes, and canonized scripture texts.
- `deities`: Shows current status, Divine Energy, personality traits, and locations of the 6 divine beings.
- `council`: Displays recent 1-on-1 and 5-Sister Council dialogue transcripts and active Divine Truces.
- `elders`: Lists mortal elders appointed to the World Library Council.
- `wtc`: Prints order-book prices for all 6 commodities and current Fisher CPI.
- `bank`: Displays World Bank currency reserves, circulating credit supply, and active loan book.
- `parcel <cx> <cz>`: Inspects deeds, owner ID, zoning, building footprints, and rent for a parcel.
- `traditions`: Lists active emergent cultural memes across settlements.
- `library [topic]`: Displays approved books, reading counts, and pending Elder/God-Mother proposals.
- `ledger [day]`: Reads the daily God Ledger Markdown compiled by the World Goddess.
- `inspect <agent_id>`: Dumps complete cognitive state: vitals, 10-D traits, mood, working memory, and inventory.

### 3.2 Divine Intervention Commands
- `name_deity <slot> "<name>"`: Bestows a custom name on a deity slot (e.g. `name_deity gm_human "Solis"`).
- `spawn <race> [sub_lineage] [x] [z]`: Spawns an infant or adult mortal at the specified coordinates.
- `bless <agent_id>`: Restores full health and stamina; clears illness and injury.
- `curse <agent_id>`: Inflicts physical exhaustion or illness.
- `smite <agent_id>`: Smites a mortal with divine lightning (`DIVINE_SMITE` fatality; clears slot).
- `war declare <nation_a> <nation_b>`: Forces a state of active war between two sovereign polities.
- `war peace <nation_a> <nation_b>`: Enforces an immediate ceasefire and Divine Truce.
- `bank grant <settlement_id> <amount>`: Grants credits directly from the World Bank reserve to a treasury.
- `wtc freeze` / `wtc unfreeze`: Halts or resumes commodity order-book trading at the WTC.
- `decree "<text>"`: Broadcasts an immutable divine decree across the world and logs it to the Divine Codex.
- `speed <1x..60x>`: Sets simulation execution speed multiplier.
- `pause` / `resume`: Pauses or resumes simulation ticks.
- `save`: Forces an immediate atomic Two-Phase Commit snapshot.
- `rewind <day>`: Rewinds civilization state to a verified historical daily checkpoint.

---

## 4. In-Game UI Workflows

### 4.1 Two-Book Governance Modal (`L` Key)
1. **World Library Tab:**
   - Browse cumulative mortal scholarship across all 10 canonical subjects.
   - Click any entry to read full manuscripts and inspect mechanical bonuses (`craft_speed_bonus`, `winter_hardiness`).
   - As God, click **"Edit / Author"** to write new lore or revise existing texts (`GOD_LIBRARY_EDIT`). Changes commit immediately with `bypass_god_check=True`.
2. **Divine Codex Tab:**
   - Review permanent divine laws, Sister Council covenant agreements, and recorded decrees.
   - Review pending parameter override proposals submitted by the World Goddess or 5 Daughters.
   - As God, click **"Approve"** or **"Reject"** on parameter proposals, or author new decrees directly (`GOD_CODEX_EDIT`).

### 4.2 Palace Gate Entry Decisions
When a mortal approaches the Ring 0 Grand Divine Palace Gate:
1. A **`PALACE_ENTRY_REQUEST`** banner appears in the Godot Divine HUD showing the petitioner's name, race, title, faith devotion, criminal history, and reason.
2. Press **`F1`** or click the banner to adjudicate:
   - **Grant Audience:** Emits `GOD_PALACE_DECISION` (`GRANT`); gates swing open and knights salute.
   - **Deny Entry:** Emits `DENY`; knights turn the petitioner away.
   - **Armed Escort:** Emits `ESCORT`; knights flank the petitioner and lead them to the palace dais.

### 4.3 Entity Inspector & Divine Actions
Clicking on any mortal, deity, or building in either 3rd-person or Orbital RTS mode opens the **`EntityInspector`** modal:
1. **Demographics & Vitals:** View age, stage, gender, dynasty, health, hunger, stamina, hygiene, and fatigue bars.
2. **Personality & Mood:** View the live 10-D personality radar and current dynamic `MoodState` (`calm`, `angry`, `grieving`, `fearful`, `inspired`).
3. **Inventory & Gear:** Displays equipped outfits, accessories, vocational tools, and held commodity stacks.
4. **Divine Actions:**
   - **Bless:** Emits `curse/bless` command restoring health, removing illness/fatigue, and lifting distress.
   - **Curse:** Inflicts divine affliction or exhaustion.
5. **Dismissal:** Press **`Esc`** or click the close button. `UiStateManager` ensures mouse capture is restored cleanly.

---

## 5. Knowledge Foundry & Celestial Ingestion Workflow

To enrich mortal scholarship with custom books and lore:

### Step 1: Ingest Raw Lore (`scripts/celestial_ingest.py`)
```bash
uv run python scripts/celestial_ingest.py \
  --input my_lore.txt \
  --subject craft_and_metallurgy \
  --output data/knowledge/staged/blacksmithing_annals.json \
  --use-llm \
  --max-entries 15 \
  --author "Master Blacksmith Thrain"
```

### Step 2: Review & Deduplicate (`scripts/knowledge_review.py`)
```bash
# Evaluates all staged packs against Stage 0 (Schema), Stage 1 (Hash/Key), Stage 2 (Lexical), Stage 3 (Semantic)
uv run python scripts/knowledge_review.py

# Or target an individual pack and compare against an archived directory
uv run python scripts/knowledge_review.py --pack staged_packs/blacksmithing_annals.json --archive-dir knowledge_foundry/archived_packs
```

### Step 3: Dry-Run Verification (`scripts/knowledge_merge.py`)
```bash
# Validates database insertion without modifying SQLite
uv run python scripts/knowledge_merge.py --dry-run
```

### Step 4: Atomic Merge Commit (`scripts/knowledge_merge.py`)
```bash
# Inserts validated books into world_library and archives staged JSON
uv run python scripts/knowledge_merge.py --commit --archive-dir knowledge_foundry/archived_packs
```
