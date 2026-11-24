# Gaia v4.0 Master Documentation Index

Welcome to the central documentation index for **Gaia v4.0** — the persistent, local-first anime-fantasy AI civilization engine. Every document listed below is maintained in strict synchrony with the production codebase.

---

## 1. System Architecture & Network Protocols (`docs/architecture/`)

- [ARCHITECTURE.md](file:///home/shivam/Desktop/Gaia/docs/architecture/ARCHITECTURE.md): Master architectural topology, multi-tier cognitive LOD scheduler, WebSocket bridge design, atomic 2PC commit cycle, and the Self-Healing Error Solver.
- [GODOT_CLIENT_AND_ASSETS_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/architecture/GODOT_CLIENT_AND_ASSETS_SPEC.md): Godot 4.7.2 Forward+ rendering, $8\text{km} \times 8\text{km}$ heightmap parity, TerrainBiome shaders, 3D grass streaming, Grand Divine Palace, gated cities, zero-T-pose animation, and God Avatar physics.
- [WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md](file:///home/shivam/Desktop/Gaia/docs/architecture/WORLD_GEOGRAPHY_AND_SETTLEMENTS_V4.md): Concentric 4-ring topography ($8\text{km} \times 8\text{km}$), Ring 0 Imperial Acropolis & Twin Guardian Dragons, Ring 1 pentagonal gated cities, Ring 2 frontier wilderness, Ring 3 ocean, and regional weather cells.
- [HYBRID_COGNITIVE_AND_LLM_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/architecture/HYBRID_COGNITIVE_AND_LLM_SPEC.md): 4-Pillar Hybrid Cognitive Core (`SharedLivingNet`, `ProfessionNetRegistry`, `BatchedAgentSelfNet`, Grounded `MemoryRAGIndex`, `SleepCycleConsolidator`), 8 Semantic Speech Acts, Divine Agenda Engine, and local `llama.cpp` + Qwen3.5-4B integration.
- [ECONOMY_HOUSING_AND_GEAR_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/architecture/ECONOMY_HOUSING_AND_GEAR_SPEC.md): Closed-loop double-entry credit conservation, World Bank, WTC Fisher CPI, $16\text{m} \times 16\text{m}$ deeds, `HousingMarketEngine` tier upgrades/probate, and `GearEconomy` 3D Reality Bubble synchronization.
- [WEBSOCKET_PROTOCOL_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/architecture/WEBSOCKET_PROTOCOL_SPEC.md): Complete binary 24-byte/agent frame layout + flag bitmasks and all bidirectional JSON message schemas (`BUBBLE_SYNC`, `DEITY_SYNC`, `BOOK_STATE_SYNC`, `PALACE_ENTRY_REQUEST`, etc.).

---

## 2. Simulation Core, Biology & Cognitive Systems (`docs/simulation/`)

- [NEURAL_AND_LIFECYCLE_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/simulation/NEURAL_AND_LIFECYCLE_SPEC.md): Unbounded 2,048-slab PyTorch tensor brains (`torch.bmm` + `GRUCell`), 4-Pillar Cognitive Core, 8 Semantic Speech Acts, 20 primitives, root-cause infant distress/crying, 5-race lifecycle, and mortality.
- [RACES_AND_BIOLOGY_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/simulation/RACES_AND_BIOLOGY_SPEC.md): 5 biological races (`HUMAN`, `ELF`, `DRAGON`, `BEASTHUMAN`, `DEMON`), strict binary gender (`BOY`/`GIRL`), cross-species mating ($50\%$ conception, $60\%$ birth survival), and Dragon metamorphosis state machine.
- [DIVINE_HIERARCHY_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/simulation/DIVINE_HIERARCHY_SPEC.md): Divine Family Hierarchy (God $\rightarrow$ World Goddess $\rightarrow$ 5 Racial God-Mothers), prayer routing, Age-10 mixed-race patronage choice, Sister Councils, Divine Truces, Autonomous Divine Agenda Engine, and local LLM integration.
- [SOCIETY_AND_GOVERNANCE_SPEC.md](file:///home/shivam/Desktop/Gaia/docs/simulation/SOCIETY_AND_GOVERNANCE_SPEC.md): Two-Book Governance (`world_library` + `divine_codex`), 5-tier bordered polities, Neutral Free Cities, double-entry economy, WTC inflation, `HousingMarketEngine`, `GearEconomy`, and Judiciary.

---

## 3. Data Contracts, Schemas & Persistence (`docs/data/`)

- [DATA_SCHEMA_AND_WORLD_GODDESS.md](file:///home/shivam/Desktop/Gaia/docs/data/DATA_SCHEMA_AND_WORLD_GODDESS.md): Complete Pydantic v2 domain schemas, SQLite WAL DDL table definitions, DuckDB analytical queries, `WorldGoddessCritic` RBAC validation matrix, and pure end-of-day atomic Two-Phase Commit with SHA-256 corruption rewind.

---

## 4. Player & Operator Guides (`docs/guides/`)

- [PLAYER_AND_OPERATOR_GUIDE.md](file:///home/shivam/Desktop/Gaia/docs/guides/PLAYER_AND_OPERATOR_GUIDE.md): Practical operator handbook covering launch commands (live, offline, headless, fresh), complete in-game keyboard/mouse keybindings, Rich God Console CLI reference, Two-Book, Palace Gate, and Entity Inspector UI workflows, and Knowledge Foundry authoring.
- [llama_cpp_install_guide.md](file:///home/shivam/Desktop/Gaia/docs/guides/llama_cpp_install_guide.md): Local compilation and hardware acceleration setup for llama.cpp on Fedora Linux 45.
- [llama_cpp_run_guide.md](file:///home/shivam/Desktop/Gaia/docs/guides/llama_cpp_run_guide.md): Runtime orchestration guide for llama-server with Qwen3.5-4B abliterated GGUF.

---

## 5. Knowledge Foundry & Lore Ingestion (`knowledge_foundry/`)

- [DEDUPE_AND_REVIEW_PLAYBOOK.md](file:///home/shivam/Desktop/Gaia/knowledge_foundry/DEDUPE_AND_REVIEW_PLAYBOOK.md): Author review guide for Knowledge Foundry packs, 3-stage cascaded deduplication architecture (Stage 0 Schema $\rightarrow$ Stage 1 Hash/Key $\rightarrow$ Stage 2 Lexical $\rightarrow$ Stage 3 Semantic Vector), conflict detection, merge CLI commands, and the `celestial_ingest.py` automated harvester.

---

## 6. Implementation Roadmap & Milestones (`docs/roadmap/`)

- [IMPLEMENTATION_ROADMAP.md](file:///home/shivam/Desktop/Gaia/docs/roadmap/IMPLEMENTATION_ROADMAP.md): Complete implementation record for Phases 0–5, Gaia v4.0 Sprints 0–6, Waves 1–6 Hardening & Normalization, modularized domain test suite (191 unit/integration tests across 7 domain packages), 10,000-agent benchmarks, and future v4.1+ architectural ideas.

---

## 7. Root Master Directives & Entry Points

- [README.md](file:///home/shivam/Desktop/Gaia/README.md): Master repository overview, architecture diagrams, feature highlights, and quickstart commands.
- [AGENTS.md](file:///home/shivam/Desktop/Gaia/AGENTS.md): Strict engineering rules, hardware targets (Fedora 45, Ryzen 7 8840HS, Radeon 780M), `uv` toolchain enforcement, repository layout, non-negotiable architectural invariants, and multi-agent QA loop hygiene.
