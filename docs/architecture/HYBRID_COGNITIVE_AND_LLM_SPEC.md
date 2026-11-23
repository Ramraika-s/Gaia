# HYBRID_COGNITIVE_AND_LLM_SPEC.md — 4-Pillar Cognitive Core, Speech Acts, Divine Agenda & Local LLM

## 1. Executive Summary & Design Philosophy
Gaia v4.0 operates a **4-Pillar Hybrid Cognitive Architecture** designed to scale from dozens of founders to **10,000+ autonomous neural agents** on consumer-grade laptop hardware (AMD Ryzen 7 8840HS, 32GB DDR5 RAM, Radeon 780M iGPU).

To achieve both high agent counts (sub-15ms tick budget on CPU) and profound conversational/behavioral depth:
1. **Zero per-agent LLM loops:** Running 10,000 language models is computationally impossible on any hardware. Instead, all 10,000+ mortals run on contiguous slab-grown PyTorch tensors (`SharedLivingNet` + `ProfessionNet` + `BatchedAgentSelfNet` + `GRUCell`), executing in a single vectorized forward pass.
2. **Selective Asynchronous Local LLM Acceleration:** High-salience conversational moments—specifically direct dialogues between God and the 6 Deities or mortal Oracles—route asynchronously to a local `llama.cpp` instance running `Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf` under strict resource controls.
3. **Strict Information Asymmetry & Grounded RAG:** Agents have zero access to global simulation memory. Mortals can only recall events they physically witnessed or cite World Library books they have physically read (`known_books: set[str]`).

```text
┌────────────────────────────────────────────────────────────────────────┐
│                    4-PILLAR HYBRID COGNITIVE CORE                      │
├───────────────────┬───────────────────┬──────────────────┬─────────────┤
│     Pillar 1      │     Pillar 2      │     Pillar 3     │  Pillar 4   │
│  3-Tier Neural    │   Grounded RAG    │  10-D Traits &   │ Sleep Cycle │
│   Hierarchical    │   Memory Index    │   Mood Engine    │Consolidator │
│      Brain        │(known_books only) │ (Dynamic Coupling│(Daily Drift │
│                   │                   │   to Logits)     │  <= 0.05)   │
└───────────────────┴───────────────────┴──────────────────┴─────────────┘
                                  │
                                  ▼
      ┌───────────────────────────────────────────────────────────┐
      │     8 Semantic Speech Acts & Diegetic Utterances          │
      │  (GREET, WARN, TRADE, LORE, CRIME, PRAY, COURT, DEBATE)   │
      └───────────────────────────────────────────────────────────┘
                                  │
                                  ▼
      ┌───────────────────────────────────────────────────────────┐
      │     Autonomous Divine Agenda & Local LLM Integration      │
      │  (6 Deities Diurnal Patrols + Async Qwen3.5-4B Llama.cpp) │
      └───────────────────────────────────────────────────────────┘
```

---

## 2. Pillar 1: 3-Tier Hierarchical Neural Brain (`sim_core/brains/hierarchical_brain.py`)

Every agent's decision logic blends three specialized neural layers into a final action probability distribution:

### 2.1 Tier 1: Species Survival Core (`SharedLivingNet`)
- **Module:** `sim_core/brains/shared_living_net.py`
- **Scope:** Species-wide shared MLP (evaluated across all $N$ active agents in one batched call).
- **Function:** Instinctual physical survival, urgent bodily preservation, and basic infant care:
  - Evaluates hunger, stamina, injury, illness, environmental exposure, and immediate physical threats.
  - Generates foundational action logits $L_{\text{shared}} \in \mathbb{R}^{N \times 20}$ and a baseline state-value estimate $V(s) \in \mathbb{R}^{N \times 1}$.
  - Enforces hard survival overrides ($g_{\text{survival}} = 0.25$ clamp) when health or hunger drops below critical thresholds ($< 25\%$).

### 2.2 Tier 2: Vocational Mastery (`ProfessionNetRegistry`)
- **Module:** `sim_core/brains/profession_nets.py`
- **Scope:** 10 discrete profession networks covering all societal roles:
  1. `FARMER`: Cultivation, crop harvesting, granary storage, winter stockpiling.
  2. `LUMBERJACK`: Timber felling, reforestation, lumber seasoning, haulage.
  3. `MINER`: Subterranean prospecting, stone quarrying, iron/gold extraction.
  4. `BLACKSMITH`: Smelting, tool forging, armor smithing, weapon crafting.
  5. `MERCHANT`: WTC arbitrage, market retail, caravan logistics, price negotiation.
  6. `BUILDER`: Foundation laying, cottage construction, city wall masonry, tier upgrades.
  7. `GUARD`: Wall patrolling, gate defense, thief apprehension, riot suppression.
  8. `SCHOLAR`: World Library research, book transcription, apprentice tutoring, history writing.
  9. `CLERIC`: Altar worship, congregational prayer leading, spiritual solace, hospital care.
  10. `HERBALIST`: Wild botanical gathering, medicine compounding, poison curing.
- **Progression:** Levels 1 to 10. Higher mastery unlocks advanced recipes, elevates execution speed, and boosts vocational logit confidence.

### 2.3 Tier 3: Individual Personality & Working Memory (`BatchedAgentSelfNet`)
- **Module:** `sim_core/neural/batched_self_net.py`
- **Scope:** Slab-grown contiguous 3D parameter tensors grown in chunks of $2,048$ slots with **no population ceiling**.
- **Working Memory:** Manual `GRUCell(20, 32)` per agent, storing multi-tick temporal context ($H \in \mathbb{R}^{C \times 32}$) in RAM.
- **Output:** Preference delta vector $\Delta L_{\text{self}} \in \mathbb{R}^{N \times 20}$, self-predicted reward $\hat{r}_t \in \mathbb{R}^{N \times 1}$, and confidence $c_t \in \mathbb{R}^{N \times 1}$.
- **Vectorized Math:**
  $$L_{\text{final}} = L_{\text{shared}} + L_{\text{prof}} + 1.25 \cdot \tanh(\Delta L_{\text{self}}) \cdot g_{\text{survival}}$$

---

## 3. Pillar 2: Grounded `MemoryRAGIndex` (`sim_core/brains/memory_rag.py`)

Unlike LLM agents with global world knowledge, mortals in Gaia obey strict cognitive boundaries:
- **Zero Global Telepathy:** An agent only knows what it has seen, heard via Rumor Packets ($8\text{m}$ acoustic radius), or read from physical library books.
- **`EpisodicMemoryRecord`:**
  - Fast ring buffer of recent personal experiences ($K = 32$ items) storing timestamp, location, actors involved, emotional valence, and factual key.
- **Strict `known_books` Asymmetry:**
  - Each agent maintains `known_books: set[str]` tracking the unique entry IDs of World Library books read or taught to them.
  - When querying the local RAG index (e.g. diagnosing a crop blight or smelting high-grade steel), the search is strictly constrained to the subset of books in `known_books`.
  - An apprentice cannot perform advanced metallurgy until their master uses `SHARE_BOOK_LORE` to grant them the treatise, or they visit a Library lectern.

---

## 4. Pillar 3: 10-D `PersonalityVector` & `MoodState` (`sim_core/brains/personality.py`)

Every mortal is born with an individualized 10-dimensional trait profile:
- **10 Orthogonal Dimensions ($[-1.0, 1.0]$):**
  1. `openness`: Curiosity, receptivity to foreign cultures, willingness to pioneer.
  2. `conscientiousness`: Work ethic, duty to craft, adherence to contracts.
  3. `extraversion`: Sociability, propensity to engage in public speech acts.
  4. `agreeableness`: Compassion, generosity with family allowances, empathy for crying children.
  5. `neuroticism`: Sensitivity to danger, anxiety during famine, fear of True Dragons.
  6. `ambition`: Drive to accumulate wealth, run for political office, or upgrade housing.
  7. `caution`: Tactical hesitation, risk aversion in combat and high-leverage WTC borrowing.
  8. `loyalty`: Dedication to dynasty, settlement leader, and patron god-mother.
  9. `rule_respect`: Compliance with local laws, aversion to theft and unauthorized library edits.
  10. `faith_devotion`: Spiritual reverence, prayer frequency, altar attendance.

### Dynamic Coupling to `MoodState`
Traits continuously modulate the agent's short-term emotional state:
- **5 Discrete Moods:** `joy`, `anger`, `fear`, `gloom`, `calm`.
- **Logit Biases:**
  - High `anger` + low `caution` biases towards `DEFEND_OR_ATTACK` and aggressive debate.
  - High `joy` + high `agreeableness` biases towards `GREET`, `COURT`, and `COMFORT_OR_CARE_CHILD`.
  - High `fear` biases strongly towards `FLEE_THREAT` and shelter seeking.

---

## 5. Pillar 4: `SleepCycleConsolidator` (`sim_core/brains/consolidation.py`)

At night, when agents enter Tier 2 Cognitive LOD (`SELF_CARE_REST` or sleeping in owned housing):
1. **Episodic Distillation:**
   - Evaluates the day's experiences from the episodic ring buffer. Traumatic events (combat wounds, loss of kin, starvation) or great triumphs (wedding, harvest feast, successful trade) are prioritized.
2. **Bounded Trait Drift:**
   - Experiences induce subtle shifts in the 10-D personality vector.
   - **Hard Bounded Drift Invariant:** Total drift across all traits is capped at $|\Delta \text{trait}| \le 0.05$ per game day, preventing wild personality oscillations while enabling realistic lifelong character growth.
3. **Memory Pruning:**
   - Low-salience routine memories (e.g. routine foraging steps) decay and are evicted, bounding per-agent RAM usage.

---

## 6. The 8 Semantic Speech Acts (`sim_core/society/speech_acts.py`)

Mortals interact physically within an $8\text{m}$ acoustic radius via structured speech acts:

| Speech Act | Primary Initiators | Mechanical Consequence | Sample In-World Utterance |
| :--- | :--- | :--- | :--- |
| `GREET` | Any citizen | Raises pairwise `affinity` ($+0.02$) and mutual `trust`. | *"Grace upon your path, traveler. I am Aldric."* |
| `WARN_PRICE_SPIKE` | Consumers, merchants | Alerts listeners of WTC inflation; logs warning to `MemoryRAGIndex`. | *"Beware the grain market—wheat has doubled since dawn!"* |
| `TRADE_OFFER` | Merchants, artisans | Initiates bilateral commodity barter or tool purchase. | *"Fine dwarven steel axes for sale, sixty credits each."* |
| `SHARE_BOOK_LORE` | Scholars, elders | Teaches known World Library entry to apprentice; adds to `known_books`. | *"Study this diagram carefully; the flux prevents brittle iron."* |
| `REPORT_CRIME` | Victims, witnesses | Alerts nearby Palace Knights and City Guards; logs case to Judiciary. | *"Thief! That scoundrel seized my purse!"* |
| `PRAYER_CALL` | Clerics, devout citizens | Rallies nearby faithful to form a Congregational Altar Prayer. | *"Brothers and sisters, gather at the altar to give thanks!"* |
| `COURT` | Unattached adults | Romantic proposition; evaluates mutual readiness and compatibility. | *"Walk with me by the southern gate this evening?"* |
| `POLITICAL_DEBATE` | Candidates, elders | Influences voter utility formulas for upcoming mayoral/royal elections. | *"Lower tariffs will bring prosperity to our workshops!"* |

---

## 7. Autonomous Divine Agenda Engine (`sim_core/divine/autonomy.py`)

The World Goddess and the 5 Racial God-Mothers operate with autonomous agendas:
- **Residences:**
  - World Goddess: Grand Divine Palace (Ring 0 Acropolis).
  - 5 God-Mothers: Sylvanor, Aurelia, Fenris Hold, Malakor, and Drakonis Spire Palaces (Ring 1).
- **Diurnal Activity States:**
  - `MEDITATING`: Restoring Divine Energy in sanctum shrines.
  - `INSPECTING_PARCEL`: Touring municipal avenues and observing mortal craftsmanship.
  - `ATTENDING_ALTAR`: Visiting congregational prayer altars to bestow blessings.
  - `COUNCIL_TRAVEL`: Flying/walking to the Ring 0 Acropolis to attend 5-Sister Councils.
  - `WALKING_AVENUE`: Mingling with citizens in central plazas.
  - `COMMUNING`: Monitoring macro planetary health and crop cycles.
- **Direct God Avatar Orders:**
  - God can give direct orders via the God Console or `DialogueModal`: `FOLLOW_GOD`, `RETURN_PALACE`, `CONVENE_COUNCIL`.

---

## 8. Local LLM Integration (`sim_core/divine/llm_brain.py`)

When God or an Oracle converses directly with a Deity via the Godot `DialogueModal` (`E` key):
1. **Engine Backend:** Connects to local `llama.cpp` server (default `http://127.0.0.1:8080/completion`).
2. **Model:** `Huihui-Qwen3.5-4B-abliterated.Q5_K_M.gguf` (4B abliterated model running at ~35–45 tokens/sec on CPU/iGPU).
3. **Single-Slot Lock (`-np 1`):** Concurrency is locked to a single slot with a 3.5s timeout, guaranteeing that the simulation tick loop and Godot Forward+ rendering are never starved of DDR5 bandwidth.
4. **Sanitization:** Strips `<think>...</think>` internal reasoning blocks, enforces strict JSON response formatting, and validates state changes through `WorldGoddessCritic`.
5. **Deterministic Offline Fallback:** If the LLM server is offline or `--no-llm` is active, seamlessly generates personality-grounded fantasy responses using trait vectors, ensuring **zero simulation hangs**.
