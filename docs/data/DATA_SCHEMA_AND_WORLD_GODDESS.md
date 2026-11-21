# DATA_SCHEMA_AND_WORLD_GODDESS.md — Domain Contracts, SQLite WAL DDL, DuckDB Analytics, World Goddess RBAC & Atomic Daily 2PC 

## 1. Python Domain Schemas (`sim_core/schemas.py`)
All cross-module payloads, **World Goddess** commit proposals, institutional appeals, **Divine Family** records, **God Ledger** entries, and **Godot 4.7.2 WebSocket** JSON envelopes use **Pydantic v2** (`pydantic>=2.7`). During the active 1–2 real-hour game day, hot-loop numeric state for unbounded populations lives in contiguous slab-grown NumPy/PyTorch arrays in RAM; Pydantic models validate boundary events, World Goddess commits, and atomic end-of-day SQLite serialization.

> **Single Source of Truth Rule:** Godot 4.7.2 **never** opens or writes directly to `data/civilization.db`. Every in-world divine edit (such as saving a World Library book in Godot's 2D `TextEdit` modal) arrives as a JSON WebSocket frame (`ws://127.0.0.1:8765`), is validated by Python, mutates RAM immediately (`bypass_god_check=True`), and persists atomically at end-of-day via the **World Goddess**.

```python
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

Gender = Literal["BOY", "GIRL"]
RaceId = Literal["HUMAN", "ELF", "DRAGON", "BEASTHUMAN"]
BeasthumanSubLineage = Literal["CAT_KIN", "DWARF", "WOLF_KIN", "BARBARIAN", "BEAR_KIN"]
DragonForm = Literal["HUMANOID_DRAGON", "TRUE_DRAGON"]
DeitySlot = Literal["world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman"]
RacialGodMotherSlot = Literal["gm_human", "gm_elf", "gm_dragon", "gm_beasthuman"]

Stage = Literal["INFANT", "CHILD", "ADULT", "ELDER"]
Season = Literal["SPRING", "SUMMER", "AUTUMN", "WINTER"]
SettlementTier = Literal["VILLAGE", "TOWN", "CITY", "STATE", "NATION"]
RegimeType = Literal["KING", "ELECTED"]
ParcelOwnerType = Literal["AGENT", "SETTLEMENT", "NATION", "CHURCH", "UNCLAIMED"]

PrayerIntent = Literal[
    "EARNEST_VOLUNTARY",
    "GRATITUDE",
    "CONGREGATIONAL_ALTAR",
    "CRISIS_PLEA",
    "PARENT_DIRECTED",
]

CombatContext = Literal[
    "SELF_DEFENSE",
    "DEFENDING_KIN_OR_TOWN",
    "ACTIVE_WAR",
    "UNPROVOKED_ATTACK",
]

DeathCause = Literal[
    "STARVATION",
    "WINTER_EXPOSURE",
    "ILLNESS",
    "BIRTH_COMPLICATION",
    "COMBAT_WAR",
    "COMBAT_UNPROVOKED",
    "COMBAT_SELF_DEFENSE",
    "HAZARD",
    "OLD_AGE",
    "DIVINE_SMITE",
]

CommitKind = Literal[
    "CONCEPTION",
    "BIRTH",
    "DEATH",
    "STAGE_UP",
    "PATRON_CHOICE",
    "SELF_RENAME",
    "CREDIT_TRANSFER",
    "LIBRARY_ENTRY",
    "LIBRARY_VOTE",
    "TRADITION",
    "CRIME_REPORT",
    "JUDICIARY_RULING",
    "BANK_LOAN",
    "PARCEL_TRANSFER",
    "SETTLEMENT_APPEAL",
    "SETTLEMENT_UPDATE",
    "ELECTION_OR_SUCCESSION",
    "RELIGION_DECREE",
    "WAR_DECLARATION",
    "WTC_INTERVENTION",
    "GOD_MOTHER_INTERVENTION",
    "SISTER_COUNCIL_RESOLUTION",
    "NAME_DEITY",
    "DIVINE_DECREE",
]

class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0                      # Synced against data/world_heightmap.npy
    z: float = 0.0

class AgentRecord(BaseModel):
    agent_id: str                       # Immutable internal key
    slot_idx: int                       # Index in slab-grown BatchedAgentSelfNet tensors
    display_name: str                   # Autonomous racial/cultural or self-chosen name
    dynasty_surname: str                # Inherited family/dynasty name
    epithet: Optional[str] = None       # Earned deed title (e.g., "Ironhand")
    gender: Gender                      # Strict binary biological sex ("BOY" or "GIRL")
    race: RaceId = "HUMAN"              # Dominant biological race
    sub_lineage: Optional[BeasthumanSubLineage] = None
    secondary_heritage_race: Optional[RaceId] = None  # Set on cross-species births
    dragon_form: Optional[DragonForm] = None          # "HUMANOID_DRAGON" or "TRUE_DRAGON"
    patron_godmother_slot: Optional[RacialGodMotherSlot] = None  # None until Age 10 for mixed-race
    godmother_affinities: dict[str, float] = Field(default_factory=dict)  # Tracked for Age-10 choice
    is_oracle: bool = False             # Mortal Oracle/Champion (1-3 per race)
    skin_hsv: list[float] = Field(default_factory=lambda: [0.08, 0.35, 0.85])  # Godot shader tint
    settlement_id: Optional[str] = None
    nation_id: Optional[str] = None
    religion_id: Optional[str] = None
    cleric_rank: Literal["NONE", "PRIEST", "HIGH_CLERIC", "POPE"] = "NONE"
    stage: Stage = "INFANT"
    age_ticks: int = 0
    health: float = 40.0
    max_health: float = 40.0
    hunger: float = 100.0
    stamina: float = 100.0
    injured: float = Field(default=0.0, ge=0.0, le=1.0)
    illness: float = Field(default=0.0, ge=0.0, le=1.0)
    distress: float = Field(default=0.0, ge=0.0, le=1.0)
    crying: bool = False                # Derived: distress >= 0.45 for INFANT/CHILD
    credits: float = 10.0
    credit_score: float = Field(default=650.0, ge=300.0, le=850.0)
    breeding_cooldown: int = 0
    pregnant_ticks_remaining: int = 0   # > 0 only for pregnant GIRL adults
    pregnancy_father_id: Optional[str] = None
    is_cross_species_pregnancy: bool = False
    last_prayer_tick: int = 0
    parent_ids: list[str] = Field(default_factory=list)
    spouse_id: Optional[str] = None
    alive: bool = True
    quarantined: bool = False           # Set by ErrorHealer on repeated single-slot fault
    pos: Vec3 = Field(default_factory=Vec3)
    traits: dict[str, float] = Field(default_factory=lambda: {
        "caution": 0.0,
        "sociability": 0.0,
        "ambition": 0.0,
        "loyalty": 0.0,
        "rule_respect": 0.0,
        "faith_devotion": 0.0,
    })
    skills: dict[str, float] = Field(default_factory=lambda: {
        "walk": 0.05,
        "self_care": 0.05,
    })
    tradition_ids: list[str] = Field(default_factory=list)

class DivinePersonality(BaseModel):
    compassion: float = Field(default=0.6, ge=0.0, le=1.0)
    restraint: float = Field(default=0.6, ge=0.0, le=1.0)
    pride: float = Field(default=0.5, ge=0.0, le=1.0)
    protective_fury: float = Field(default=0.5, ge=0.0, le=1.0)
    diplomacy: float = Field(default=0.6, ge=0.0, le=1.0)

class DivineEntityRecord(BaseModel):
    slot: DeitySlot
    bestowed_name: str                  # Custom name bestowed by God (Admin)
    role: Literal["WORLD_GODDESS", "RACIAL_GOD_MOTHER"]
    patron_race: Optional[RaceId] = None
    divine_energy: float = Field(default=300.0, ge=0.0, le=1000.0)
    personality: DivinePersonality = Field(default_factory=DivinePersonality)
    oracle_agent_ids: list[str] = Field(default_factory=list)  # Max 3 living Oracles per race
    active_truce_with: list[DeitySlot] = Field(default_factory=list)
    intervention_cooldown_until_tick: int = 0
    covenant_rebukes: int = 0

class SisterCouncilMessage(BaseModel):
    message_id: str
    day: int
    tick: int
    sender_slot: DeitySlot
    recipient_slots: list[DeitySlot]    # 1 sister, all 4 sisters, or ["world_goddess"]
    topic: Literal[
        "BORDER_FRICTION", "DRAGON_PROVOCATION", "WAR_INTERVENTION",
        "DIVINE_TRUCE", "COVENANT_BREACH", "FREE_CITY_ACCORD", "GOD_ESCALATION"
    ]
    summary: str
    resolution: Optional[str] = None

class RelationshipRecord(BaseModel):
    agent_a: str
    agent_b: str
    trust: float = Field(default=0.0, ge=-1.0, le=1.0)
    affinity: float = Field(default=0.0, ge=-1.0, le=1.0)
    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    role: Literal["NONE", "PARENT", "CHILD", "PARTNER", "ALLY", "RIVAL"] = "NONE"
    interaction_count: int = 0

class SettlementRecord(BaseModel):
    settlement_id: str
    name: str
    tier: SettlementTier = "VILLAGE"
    parent_polity_id: Optional[str] = None   # Parent STATE or NATION; None if sovereign
    regime_type: RegimeType = "ELECTED"
    is_holy_polity: bool = False             # Applies birth imprinting to newborns
    is_neutral_free_city: bool = False       # Multi-racial safe haven for WTC/Library
    war_exempt: bool = False                 # True for approved Neutral Free Cities
    state_religion_id: Optional[str] = None
    founder_id: str
    leader_id: Optional[str] = None          # Headman, Mayor, Governor, King, or President
    center_pos: Vec3
    border_parcel_ids: list[str] = Field(default_factory=list)  # Explicit 16x16m borders
    treasury_credits: float = 100.0
    tax_rate: float = Field(default=0.05, ge=0.0, le=0.30)
    tariff_rate: float = Field(default=0.0, ge=0.0, le=0.50)
    next_election_tick: Optional[int] = None
    laws: dict[str, Any] = Field(default_factory=lambda: {
        "theft_fine_mult": 2.0,
        "assault_fine": 60.0,
        "banish_on_repeat_offenses": 3,
        "infant_welfare_enabled": True,
        "property_tax_rate": 0.01,
    })
    at_war_with: list[str] = Field(default_factory=list)
    allied_with: list[str] = Field(default_factory=list)
    founded_tick: int = 0

class SettlementAppealRecord(BaseModel):
    appeal_id: str
    settlement_id: str
    proposer_id: str
    appeal_kind: Literal["TIER_UPGRADE", "NEUTRAL_FREE_CITY"] = "TIER_UPGRADE"
    current_tier: Optional[SettlementTier] = None
    requested_tier: Optional[SettlementTier] = None
    claimed_parcel_ids: list[str] = Field(default_factory=list)
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    reason: str = ""
    submitted_tick: int

class ReligionRecord(BaseModel):
    religion_id: str
    name: str
    aligned_deity_slot: DeitySlot = "world_goddess"
    founder_id: str
    pope_id: Optional[str] = None
    treasury_credits: float = 0.0
    tenets: dict[str, float] = Field(default_factory=lambda: {
        "pacifism": 0.5,
        "charity_tithe_rate": 0.05,
        "work_ethic": 0.5,
        "sacred_land_defense": 0.5,
        "heresy_intolerance": 0.2,
    })
    canonized_entry_ids: list[str] = Field(default_factory=list)
    excommunicated_ids: list[str] = Field(default_factory=list)
    founded_tick: int = 0

class ParcelRecord(BaseModel):
    parcel_id: str                      # f"{cx}_{cz}" aligned 1:1 to 16x16m Terrain3D grid
    cx: int
    cz: int
    settlement_id: Optional[str] = None # Explicit immediate settlement border; None = Wilderness
    nation_id: Optional[str] = None     # Explicit sovereign nation border
    owner_id: Optional[str] = None
    owner_type: ParcelOwnerType = "UNCLAIMED"
    has_altar: bool = False
    has_library: bool = False
    assessed_value: float = 50.0
    for_sale_price: Optional[float] = None
    tenant_id: Optional[str] = None
    rent_per_civic_tick: float = 0.0
    updated_tick: int = 0

class BankLoanRecord(BaseModel):
    loan_id: str
    holder_id: str
    holder_type: Literal["AGENT", "SETTLEMENT", "NATION", "CHURCH"]
    principal: float
    remaining_balance: float
    interest_rate: float = 0.02
    missed_windows: int = 0
    status: Literal["GOOD", "DELINQUENT", "DEFAULTED", "PAID"] = "GOOD"
    issued_tick: int

class WTCMarketSnapshot(BaseModel):
    day: int
    tick: int
    cpi: float = 1.0                    # Consumer Price Index (1.0 = baseline)
    money_supply_m: float
    real_output_q: float
    prices: dict[str, float]
    frozen: bool = False

class JudiciaryCaseRecord(BaseModel):
    case_id: str
    settlement_id: Optional[str]
    accused_id: str
    victim_id: Optional[str] = None
    offense_type: Literal[
        "THEFT", "UNPROVOKED_ATTACK", "VANDALISM", "DEBT_DEFAULT", "TRESPASS", "CONTESTED_COMBAT"
    ]
    combat_context: Optional[CombatContext] = None
    witness_ids: list[str] = Field(default_factory=list)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    ruling: Optional[Literal["ACQUITTED", "RESTITUTION", "FINE", "GARNISH", "BANISHMENT"]] = None
    penalty_credits: float = 0.0
    opened_tick: int
    closed_tick: Optional[int] = None

class FatalityRecord(BaseModel):
    agent_id: str
    display_name: str
    race: RaceId
    sub_lineage: Optional[BeasthumanSubLineage] = None
    secondary_heritage_race: Optional[RaceId] = None
    age_ticks: int
    stage_at_death: Stage
    cause: DeathCause
    combat_context: Optional[CombatContext] = None
    killer_id: Optional[str] = None
    settlement_id: Optional[str] = None
    season: Season
    death_day: int
    death_tick: int

class WorldLibraryEntry(BaseModel):
    entry_id: str
    topic: str
    title: str
    summary: str
    author_id: str
    author_proficiency: float = Field(ge=0.0, le=1.0)
    skill_bonus: float = Field(default=0.08, ge=0.01, le=0.15)
    is_scripture: bool = False
    read_count: int = 0
    created_tick: int

class LibraryCouncilElderRecord(BaseModel):
    nation_id: str
    agent_id: str
    appointed_tick: int

class LibraryProposalRecord(BaseModel):
    proposal_id: str
    action: Literal["CREATE", "EDIT", "SUPERSEDE"]
    target_entry_id: Optional[str] = None
    author_id: str
    topic: str
    title: str
    summary: str
    author_proficiency: float = Field(ge=0.0, le=1.0)
    votes_approve: list[str] = Field(default_factory=list)  # Appointed Elder agent_ids
    votes_reject: list[str] = Field(default_factory=list)
    status: Literal["OPEN", "APPROVED", "REJECTED"] = "OPEN"
    created_tick: int

class TraditionRecord(BaseModel):
    tradition_id: str
    name: str
    origin_settlement_id: str
    trigger: Literal[
        "FIRST_DAY_OF_WINTER", "HARVEST_SURPLUS", "ROYAL_DEATH",
        "MARRIAGE", "WAR_VICTORY", "GOD_SIGHTING"
    ]
    ritual_action: Literal[
        "GIFT_FOOD_IN_SQUARE", "GATHER_AT_TEMPLE", "SILENT_FAST",
        "PUBLIC_FEAST", "BUILD_MONUMENT_STEP"
    ]
    adoption_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    taboo_penalty: float = Field(default=0.15, ge=0.0, le=0.5)
    created_tick: int

class GodLedgerEntry(BaseModel):
    entry_id: str
    day: int
    tick: int
    category: Literal[
        "WORLD_GODDESS_SUMMARY", "GOD_MOTHER_REPORT", "CONGREGATIONAL_ALTAR",
        "SISTER_COUNCIL", "PATRON_TIE_BREAK", "PRAYER_DIGEST",
        "MILESTONE", "HEALER_ALERT", "CRITICAL_ESCALATION"
    ]
    deity_slot: Optional[DeitySlot] = None  # Only World Goddess / God-Mothers message God
    speaker_name: str                       # Bestowed Deity name or "HEALER"
    prayer_head_name: Optional[str] = None  # Mortal Prayer Head if relaying an altar prayer
    settlement_name: Optional[str] = None
    group_size: int = 1
    intent: Optional[PrayerIntent] = None
    message: str
    delivered_realtime: bool = False

class DailyManifest(BaseModel):
    day: int
    tick: int
    season: Season
    committed_by: str                   # Bestowed name of the World Goddess
    db_path: str
    db_sha256: str
    pt_path: str
    pt_sha256: str
    ledger_path: str
    status: Literal["VERIFIED"] = "VERIFIED"

class CommitProposal(BaseModel):
    proposal_id: str
    tick: int
    kind: CommitKind
    actor_id: Optional[str] = None      # agent_id or DeitySlot
    payload: dict[str, Any]
    bypass_god_check: bool = False      # True ONLY for direct God Avatar / Console actions

class CriticVerdict(BaseModel):
    proposal_id: str
    kind: CommitKind
    actor_id: Optional[str] = None
    status: Literal["SUCCESS", "FAILURE"]
    reason: str
    committed_tick: Optional[int] = None
```

---

## 2. SQLite WAL Schema DDL (`sim_core/persistence/db.py`)
Single transactional database: `data/civilization.db`. Written **exclusively by the World Goddess during atomic end-of-day commits** (or clean shutdown). Always open with:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA foreign_keys = ON;
```

```sql
CREATE TABLE IF NOT EXISTS world_meta (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_entities (
    slot TEXT PRIMARY KEY,
    bestowed_name TEXT NOT NULL,
    role TEXT NOT NULL,
    patron_race TEXT,
    divine_energy REAL NOT NULL,
    personality_json TEXT NOT NULL,
    oracle_agent_ids_json TEXT NOT NULL,
    active_truce_with_json TEXT NOT NULL,
    intervention_cooldown_until_tick INTEGER NOT NULL DEFAULT 0,
    covenant_rebukes INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sister_council_messages (
    message_id TEXT PRIMARY KEY,
    day INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    sender_slot TEXT NOT NULL,
    recipient_slots_json TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    resolution TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    slot_idx INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    dynasty_surname TEXT NOT NULL,
    epithet TEXT,
    gender TEXT NOT NULL,
    race TEXT NOT NULL,
    sub_lineage TEXT,
    secondary_heritage_race TEXT,
    dragon_form TEXT,
    patron_godmother_slot TEXT,
    godmother_affinities_json TEXT NOT NULL,
    is_oracle INTEGER NOT NULL DEFAULT 0,
    skin_hsv_json TEXT NOT NULL,
    settlement_id TEXT,
    nation_id TEXT,
    religion_id TEXT,
    cleric_rank TEXT NOT NULL DEFAULT 'NONE',
    stage TEXT NOT NULL,
    age_ticks INTEGER NOT NULL,
    health REAL NOT NULL,
    max_health REAL NOT NULL,
    hunger REAL NOT NULL,
    stamina REAL NOT NULL,
    injured REAL NOT NULL DEFAULT 0.0,
    illness REAL NOT NULL DEFAULT 0.0,
    distress REAL NOT NULL DEFAULT 0.0,
    crying INTEGER NOT NULL DEFAULT 0,
    credits REAL NOT NULL,
    credit_score REAL NOT NULL,
    breeding_cooldown INTEGER NOT NULL DEFAULT 0,
    pregnant_ticks_remaining INTEGER NOT NULL DEFAULT 0,
    pregnancy_father_id TEXT,
    is_cross_species_pregnancy INTEGER NOT NULL DEFAULT 0,
    last_prayer_tick INTEGER NOT NULL DEFAULT 0,
    parent_ids_json TEXT NOT NULL,
    spouse_id TEXT,
    alive INTEGER NOT NULL,
    quarantined INTEGER NOT NULL DEFAULT 0,
    pos_json TEXT NOT NULL,
    traits_json TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    tradition_ids_json TEXT NOT NULL,
    updated_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    agent_a TEXT NOT NULL,
    agent_b TEXT NOT NULL,
    trust REAL NOT NULL,
    affinity REAL NOT NULL,
    fear REAL NOT NULL,
    role TEXT NOT NULL,
    interaction_count INTEGER NOT NULL,
    PRIMARY KEY (agent_a, agent_b)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    parent_polity_id TEXT,
    regime_type TEXT NOT NULL,
    is_holy_polity INTEGER NOT NULL DEFAULT 0,
    is_neutral_free_city INTEGER NOT NULL DEFAULT 0,
    war_exempt INTEGER NOT NULL DEFAULT 0,
    state_religion_id TEXT,
    founder_id TEXT NOT NULL,
    leader_id TEXT,
    center_pos_json TEXT NOT NULL,
    border_parcel_ids_json TEXT NOT NULL,
    treasury_credits REAL NOT NULL,
    tax_rate REAL NOT NULL,
    tariff_rate REAL NOT NULL DEFAULT 0.0,
    next_election_tick INTEGER,
    laws_json TEXT NOT NULL,
    at_war_with_json TEXT NOT NULL,
    allied_with_json TEXT NOT NULL,
    founded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settlement_appeals (
    appeal_id TEXT PRIMARY KEY,
    settlement_id TEXT NOT NULL,
    proposer_id TEXT NOT NULL,
    appeal_kind TEXT NOT NULL,
    current_tier TEXT,
    requested_tier TEXT,
    claimed_parcel_ids_json TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    submitted_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settlement_standing (
    settlement_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    standing REAL NOT NULL,
    PRIMARY KEY (settlement_id, agent_id)
);

CREATE TABLE IF NOT EXISTS religions (
    religion_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    aligned_deity_slot TEXT NOT NULL,
    founder_id TEXT NOT NULL,
    pope_id TEXT,
    treasury_credits REAL NOT NULL,
    tenets_json TEXT NOT NULL,
    canonized_entry_ids_json TEXT NOT NULL,
    excommunicated_ids_json TEXT NOT NULL,
    founded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS parcels (
    parcel_id TEXT PRIMARY KEY,
    cx INTEGER NOT NULL,
    cz INTEGER NOT NULL,
    settlement_id TEXT,
    nation_id TEXT,
    owner_id TEXT,
    owner_type TEXT NOT NULL,
    has_altar INTEGER NOT NULL DEFAULT 0,
    has_library INTEGER NOT NULL DEFAULT 0,
    assessed_value REAL NOT NULL,
    for_sale_price REAL,
    tenant_id TEXT,
    rent_per_civic_tick REAL NOT NULL DEFAULT 0.0,
    updated_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS world_bank_loans (
    loan_id TEXT PRIMARY KEY,
    holder_id TEXT NOT NULL,
    holder_type TEXT NOT NULL,
    principal REAL NOT NULL,
    remaining_balance REAL NOT NULL,
    interest_rate REAL NOT NULL,
    missed_windows INTEGER NOT NULL,
    status TEXT NOT NULL,
    issued_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wtc_history (
    tick INTEGER PRIMARY KEY,
    day INTEGER NOT NULL,
    cpi REAL NOT NULL,
    money_supply_m REAL NOT NULL,
    real_output_q REAL NOT NULL,
    prices_json TEXT NOT NULL,
    frozen INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS judiciary_cases (
    case_id TEXT PRIMARY KEY,
    settlement_id TEXT,
    accused_id TEXT NOT NULL,
    victim_id TEXT,
    offense_type TEXT NOT NULL,
    combat_context TEXT,
    witness_ids_json TEXT NOT NULL,
    evidence_score REAL NOT NULL,
    status TEXT NOT NULL,
    ruling TEXT,
    penalty_credits REAL NOT NULL,
    opened_tick INTEGER NOT NULL,
    closed_tick INTEGER
);

CREATE TABLE IF NOT EXISTS criminal_records (
    record_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    settlement_id TEXT,
    offense_type TEXT NOT NULL,
    ruling TEXT NOT NULL,
    penalty_credits REAL NOT NULL,
    active_warrant INTEGER NOT NULL DEFAULT 0,
    recorded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fatalities (
    agent_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    race TEXT NOT NULL,
    sub_lineage TEXT,
    secondary_heritage_race TEXT,
    age_ticks INTEGER NOT NULL,
    stage_at_death TEXT NOT NULL,
    cause TEXT NOT NULL,
    combat_context TEXT,
    killer_id TEXT,
    settlement_id TEXT,
    season TEXT NOT NULL,
    death_day INTEGER NOT NULL,
    death_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS world_library (
    entry_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_proficiency REAL NOT NULL,
    skill_bonus REAL NOT NULL,
    is_scripture INTEGER NOT NULL DEFAULT 0,
    read_count INTEGER NOT NULL DEFAULT 0,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS library_council_elders (
    nation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    appointed_tick INTEGER NOT NULL,
    PRIMARY KEY (nation_id, agent_id)
);

CREATE TABLE IF NOT EXISTS library_proposals (
    proposal_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    target_entry_id TEXT,
    author_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    author_proficiency REAL NOT NULL,
    votes_approve_json TEXT NOT NULL,
    votes_reject_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS traditions (
    tradition_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    origin_settlement_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    ritual_action TEXT NOT NULL,
    adoption_rate REAL NOT NULL,
    taboo_penalty REAL NOT NULL,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS political_history (
    event_id TEXT PRIMARY KEY,
    settlement_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    winner_or_actor_id TEXT,
    details_json TEXT NOT NULL,
    tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS healer_incidents (
    incident_id TEXT PRIMARY KEY,
    day INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    fault_class TEXT NOT NULL,
    agent_id TEXT,
    action_taken TEXT NOT NULL,
    escalated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS world_goddess_audit (
    proposal_id TEXT PRIMARY KEY,
    tick INTEGER NOT NULL,
    kind TEXT NOT NULL,
    actor_id TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agents_alive ON agents(alive);
CREATE INDEX IF NOT EXISTS idx_agents_race ON agents(race, sub_lineage);
CREATE INDEX IF NOT EXISTS idx_agents_patron ON agents(patron_godmother_slot);
CREATE INDEX IF NOT EXISTS idx_agents_settlement ON agents(settlement_id);
CREATE INDEX IF NOT EXISTS idx_parcels_owner ON parcels(owner_id);
CREATE INDEX IF NOT EXISTS idx_parcels_settlement ON parcels(settlement_id);
CREATE INDEX IF NOT EXISTS idx_parcels_nation ON parcels(nation_id);
CREATE INDEX IF NOT EXISTS idx_fatalities_race_cause_season ON fatalities(race, cause, season);
CREATE INDEX IF NOT EXISTS idx_cases_status ON judiciary_cases(status);
CREATE INDEX IF NOT EXISTS idx_crimes_agent ON criminal_records(agent_id);
CREATE INDEX IF NOT EXISTS idx_library_topic ON world_library(topic);
CREATE INDEX IF NOT EXISTS idx_council_day ON sister_council_messages(day);
CREATE INDEX IF NOT EXISTS idx_healer_day_class ON healer_incidents(day, fault_class);
```

---

## 3. DuckDB Read-Only Analytics Helper (`sim_core/persistence/db.py`)
Never run heavy analytical aggregations on the live `aiosqlite` writer connection. Attach `data/civilization.db` read-only inside DuckDB:

```python
import duckdb

def run_analytics_query(db_path: str, sql: str) -> list[dict]:
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{db_path}' AS civ (TYPE sqlite, READ_ONLY);")
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = [dict(zip(cols, r)) for r in rel.fetchall()]
    con.close()
    return rows
```

Standard analytics views supported out of the box:
- **Racial Demographics & Cross-Species Birth Survival:** Compares live births vs. `civ.fatalities` (`cause = 'BIRTH_COMPLICATION'`) grouped by `(race, secondary_heritage_race)`.
- **Infant Mortality vs. Season & WTC Inflation:** Joins `civ.fatalities` (`stage_at_death = 'INFANT'`) against `civ.wtc_history` (`cpi`).
- **Patronage Distribution of Mixed-Race Citizens:** Tracks how Age-10 mixed-race children dedicate across the 4 Racial God-Mothers and how often the World Goddess breaks ties.
- **Wealth Gini, Land Concentration & War Debt:** Computes credit/parcel concentration per settlement and correlates wars with World Bank loan delinquencies.

---

## 4. `WorldGoddessCritic` Validation & RBAC Matrix (`sim_core/persistence/world_goddess.py`)
During the game day, `WorldGoddessCritic.evaluate(proposal)` validates every mutation immediately in RAM, applies approved state changes to RAM, queues SQL deltas for end-of-day atomic persistence, and returns `CriticVerdict` to the actor.

| `CommitKind` | Deterministic Validation & RBAC Rules (unless `bypass_god_check=True`) | Common `FAILURE` Reason Codes |
| :--- | :--- | :--- |
| `CONCEPTION` | Both parents alive, `ADULT`, `P1.gender != P2.gender`, disjoint `parent_ids`, within `5m`, mother not pregnant (`pregnant_ticks_remaining == 0`), `health >= 70%` max, `hunger >= 60`, `breeding_cooldown == 0`, mutual `affinity >= 0.6` & `trust >= 0.5`. If cross-species with a Dragon, Dragon must be in `HUMANOID_DRAGON` form. Cross-species conception rolls `50%` chance; gestation set to mother's `RaceProfile.gestation_days`. | `"Rejected: mating requires one BOY and one GIRL"`, `"Rejected: mother already pregnant"`, `"Rejected: Dragon must be in HUMANOID_DRAGON form"`, `"Conception did not occur (cross-species 50% roll)"` |
| `BIRTH` | Triggered only when mother's `pregnant_ticks_remaining == 0` and mother is alive. If `is_cross_species_pregnancy`, rolls `60%` birth survival (on failure, logs `BIRTH_COMPLICATION` fatality and allocates zero tensor slot). Child `agent_id` unused. | `"Rejected: gestation incomplete"`, `"Birth complication: cross-species infant did not survive"` |
| `DEATH` | Agent exists and not already in `fatalities`; probate/escheatment verified (direct heirs -> extended kin -> settlement treasury if inside borders, else wilderness `UNCLAIMED`). Clears Oracle slot if deceased was an Oracle. | `"Rejected: agent already deceased"`, `"Rejected: invalid probate target"` |
| `STAGE_UP` | Agent alive; `age_days` (scaled by `RaceProfile.lifespan_multiplier`) and required `skills` meet exact next-stage threshold; no stage skipping. | `"Rejected: age/skill threshold unmet"`, `"Rejected: cannot skip stage"` |
| `PATRON_CHOICE` | Agent is alive, mixed-race (`secondary_heritage_race is not None`), `patron_godmother_slot is None`, and has reached biological age 10 (`>= 3.33 * L` game days). Target must be one of the two parental God-Mothers; on timeout, auto-allocates higher affinity, or escalates tie to World Goddess. | `"Rejected: agent is not an uncommitted mixed-race child"`, `"Rejected: target God-Mother is not a parental patron"`, `"Rejected: patron already permanently locked"` |
| `SELF_RENAME` | Agent alive, `stage in {"ADULT", "ELDER"}`, non-empty valid `display_name`. | `"Rejected: only adults may self-rename"` |
| `CREDIT_TRANSFER` | **Strict Double-Entry:** `amount > 0`, sender exists and `sender.credits >= amount`, receiver exists. Debits sender and credits receiver identically (zero currency minted). | `"Rejected: insufficient funds"`, `"Rejected: non-positive transfer amount"` |
| `LIBRARY_ENTRY` | Direct creation/edit by any mortal is **blocked** unless backed by an `APPROVED` `LibraryProposalRecord` with `len(votes_approve) > total_appointed_elders / 2`. Author must have `skills[topic] >= 0.70` (or be `POPE` for scripture). Only `God` (`bypass_god_check=True`, e.g. Godot `GOD_LIBRARY_EDIT`) bypasses voting. | `"Unauthorized: requires >50% Council of Elders consensus"`, `"Rejected: insufficient mastery (<0.70)"` |
| `LIBRARY_VOTE` | Voter is a living Elder registered in `library_council_elders`; proposal is `OPEN`; voter has not already voted. Auto-commits when `approvals > total_elders / 2`. | `"Unauthorized: voter is not an Appointed Library Elder"`, `"Rejected: duplicate vote"` |
| `SETTLEMENT_APPEAL` | On `TIER_UPGRADE`: meets `requested_tier` pop, contiguous `16×16m` parcel count, and treasury thresholds; `claimed_parcel_ids` do **not** overlap existing same-tier borders. On `NEUTRAL_FREE_CITY`: `tier == "CITY"` with `>= 2` races each representing `>= 15%` of living pop. | `"Rejected: pop/parcel/treasury threshold unmet"`, `"Rejected: border overlaps existing settlement"`, `"Rejected: Neutral Free City requires >=2 races at >=15% share"` |
| `SETTLEMENT_UPDATE` | Actor is `leader_id` (or founder on creation). On `APPOINT_LIBRARY_ELDER`: polity `tier == "NATION"`, target is living `ELDER`, and nation currently has `< 2` appointed Elders. `0.0 <= tax_rate <= 0.30`, `0.0 <= tariff_rate <= 0.50`. | `"Rejected: nation already has maximum 2 Library Elders"`, `"Unauthorized: actor is not settlement leader"` |
| `GOD_MOTHER_INTERVENTION` | Actor is a `RacialGodMotherSlot`; `divine_energy >= cost`; `tick >= intervention_cooldown_until_tick`; target is of her patron race (or uncommitted mixed-race ward). **Non-Aggression Covenant:** blocks offensive strikes against rival civilians (increments `covenant_rebukes`). Respects active `DIVINE_TRUCE` during wars. On `BLESS_ORACLE`, living Oracles `< 3`. | `"Rejected: violates Non-Aggression Covenant"`, `"Rejected: insufficient Divine Energy or on cooldown"`, `"Rejected: active Divine Truce blocks wartime boost"`, `"Rejected: maximum 3 active Oracles reached"` |
| `SISTER_COUNCIL_RESOLUTION` | Participants are valid `DeitySlot`s; `DIVINE_TRUCE` requires mutual diplomacy agreement or World Goddess mediation decree. | `"Rejected: invalid council participants"` |
| `NAME_DEITY` | Requires `bypass_god_check=True` (strictly **God** only). Updates `bestowed_name` on `divine_entities`. | `"Unauthorized: only God may bestow deity names"` |
| `TRADITION` | Origin settlement exists; proposer is `ADULT`/`ELDER` citizen; valid trigger/ritual; not duplicate in settlement. | `"Rejected: duplicate settlement tradition"` |
| `CRIME_REPORT` | Accused exists; valid `offense_type`; combat cases include `combat_context`; no duplicate within 10 ticks. | `"Rejected: missing combat_context"`, `"Rejected: duplicate incident"` |
| `JUDICIARY_RULING` | Case `OPEN`; verified `SELF_DEFENSE`, `DEFENDING_KIN_OR_TOWN`, or `ACTIVE_WAR` in domestic/neutral court **must** be `ACQUITTED`. | `"Rejected: unlawful conviction on verified self-defense/war context"` |
| `BANK_LOAN` | Holder exists, not `DEFAULTED`; if `AGENT`, `ADULT` & `credit_score >= 580`; `principal <= max_eligible` and `<= world_bank.reserve_credits`. Debits World Bank reserve. | `"Rejected: credit_score below 580"`, `"Rejected: active default"`, `"Rejected: exceeds Bank reserve"` |
| `PARCEL_TRANSFER` | Seller is current owner (or `UNCLAIMED` / probate); buyer has sufficient `credits` (double-entry check unless inheritance/escheatment). | `"Rejected: insufficient credits for parcel"`, `"Rejected: seller does not own parcel"` |
| `ELECTION_OR_SUCCESSION` | Winner is living citizen/heir; `ELECTED` tally matches registered voters; `KING` heir matches lineage or succession council. | `"Rejected: invalid royal heir"`, `"Rejected: ballot mismatch"` |
| `RELIGION_DECREE` | Actor is `pope_id` (or `founder_id` on founding); tithe rate `<= 0.15`; excommunication target alive. | `"Rejected: actor is not Pope"`, `"Rejected: tithe rate exceeds 15%"` |
| `WAR_DECLARATION` | Both polities exist, distinct, not already at war; proposer is sovereign leader or God; initiator is **not** `war_exempt` (`is_neutral_free_city == False`). | `"Rejected: Neutral Free Cities cannot declare offensive war"`, `"Rejected: already at war"`, `"Rejected: proposer is not sovereign leader"` |
| `WTC_INTERVENTION` | Actor is sovereign leader (tariffs) or God (freeze/unfreeze). | `"Rejected: unauthorized WTC intervention"` |

### Verdict Feedback Loop
- Every `CriticVerdict` updates the proposing mortal's in-RAM `last_critic_verdict` (`+1.0` / `-1.0`), appends to its episodic ring buffer, and applies `+0.25` (milestone success) or `-0.60` (rejection) to its next neural training reward.
- `world_goddess_audit` is pruned to the most recent `20,000` rows during daily atomic commits to prevent unbounded SQLite growth.

---

## 5. Pure End-of-Day Atomic Two-Phase Commit & God Ledger (`checkpoints.py`, `god_ledger.py`)
No mid-day disk flushes and **no 15-minute crash journal**. At the final tick of Game Day $D$ (every 1–2 real hours at `1x`, or on clean `shutdown` / manual `save`), the **World Goddess** executes an all-or-nothing atomic commit:

1. **Brief Tick Pause (less than 20 ms):** Freeze RAM tensors, pending SQLite queue, and `god_ledger_buffer` at exact `(day, tick)`.
2. **Phase 1 — All-or-Nothing SQLite Transaction (`data/civilization.db`):**
   - Execute all daily World-Goddess-approved deltas inside a single `BEGIN IMMEDIATE ... COMMIT` block.
   - Any exception triggers an immediate `ROLLBACK` (zero partial writes) and delegates to `ErrorHealer.handle("SQLITE_COMMIT_FAIL", ...)`.
3. **Phase 2 — Synchronized Daily Artifacts + SHA-256 Checksums:**
   - Write `data/checkpoints/day_{D:05d}.pt.tmp` (`SharedSkillNet`, slab-grown `BatchedAgentSelfNet` weights + `H` + `free_slots`, RNG states, `money_supply_m`, `world_bank_reserve`).
   - Online-backup `data/civilization.db` to `data/checkpoints/day_{D:05d}.db.tmp`.
   - Render `data/god_ledger/day_{D:05d}.md.tmp` (and `latest.md.tmp`) compiled by the **World Goddess**, containing her daily summary, 4 Racial God-Mother escalations, congregational altar Prayer Head reports, Inter-Sister Council logs, Age-10 tie-break decrees, and `ErrorHealer` alerts.
   - Compute **SHA-256** hashes of `.db.tmp` and `.pt.tmp`, call `os.fsync()`, and atomically `os.replace()` all `.tmp` files to final paths.
4. **Phase 3 — Manifest Written Last (`data/checkpoints/manifest.json`):**
   - Atomically write `DailyManifest(status="VERIFIED")` **only after Phases 1–2 succeed**. Retain the last `7` verified daily snapshots to bound SSD usage.
5. **Startup Verification & Automatic Corruption Rewind:**
   - On boot (`resume`), recompute SHA-256 of the latest `.db` and `.pt` against `manifest.json`.
   - If missing, truncated, or corrupted, automatically step backward through prior verified daily manifests, restore both `.db` and `.pt`, rebuild the NumPy spatial hash grid, reload `data/world_heightmap.npy`, and log a `[CORRUPTION_REWIND]` entry to the God Ledger.