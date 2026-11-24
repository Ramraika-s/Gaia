"""
sim_core/schemas.py
Pydantic v2 domain schemas, boundary contracts, World Goddess commit proposals,
and daily serialization payloads for the Gaia Persistent AI Civilization Engine.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.races import BeasthumanSubLineage, DragonForm, Gender, RaceId

DeitySlot = Literal["world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"]
RacialGodMotherSlot = Literal["gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"]

Stage = Literal["INFANT", "CHILD", "ADULT", "ELDER"]
Season = Literal["SPRING", "SUMMER", "AUTUMN", "WINTER"]
SettlementTier = Literal["VILLAGE", "TOWN", "CITY", "STATE", "NATION"]
RegimeType = Literal["KING", "ELECTED"]
ParcelOwnerType = Literal["AGENT", "INDIVIDUAL", "SETTLEMENT", "NATION", "CHURCH", "UNCLAIMED"]
BuildingType = Literal[
    "GODMOTHER_PALACE",
    "CITY_GATE",
    "WALL_SEGMENT",
    "HOUSE_T1_COTTAGE",
    "HOUSE_T2_TOWNHOUSE",
    "HOUSE_T3_MANOR",
    "SHOP_MARKET",
    "SHOP_BLACKSMITH",
    "SHOP_TAVERN",
]
RacialStyle = Literal["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]

PrayerIntent = Literal[
    "EARNEST_VOLUNTARY",
    "GRATITUDE",
    "CONGREGATIONAL_ALTAR",
    "CRISIS_PLEA",
    "PARENT_DIRECTED",
    "PETITION",
    "OBLIGATION",
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
    "DIVINE_CODEX_DECREE",
    "DIVINE_CODEX_PROPOSAL",
]


AgentRole = Literal[
    "CITIZEN",
    "PALACE_KNIGHT",
    "KNIGHT",
    "CITY_GUARD",
    "SCHOLAR",
    "MERCHANT",
    "FARMER",
    "BLACKSMITH",
    "BUILDER",
    "HUNTER",
    "CLERIC",
]


class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0  # Synced against data/world_heightmap.npy
    z: float = 0.0


class AgentRecord(BaseModel):
    agent_id: str
    slot_idx: int
    display_name: str
    dynasty_surname: str
    epithet: str | None = None
    gender: Gender
    race: RaceId = "HUMAN"
    sub_lineage: BeasthumanSubLineage | None = None
    secondary_heritage_race: RaceId | None = None
    dragon_form: DragonForm | None = None
    role: AgentRole = "CITIZEN"
    title: str | None = None
    patron_godmother_slot: RacialGodMotherSlot | None = None
    godmother_affinities: dict[str, float] = Field(default_factory=dict)
    is_oracle: bool = False
    skin_hsv: list[float] = Field(default_factory=lambda: [0.08, 0.35, 0.85])
    settlement_id: str | None = None
    nation_id: str | None = None
    religion_id: str | None = None
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
    crying: bool = False
    credits: float = 10.0
    credit_score: float = Field(default=650.0, ge=300.0, le=850.0)
    breeding_cooldown: int = 0
    pregnant_ticks_remaining: int = 0
    pregnancy_father_id: str | None = None
    is_cross_species_pregnancy: bool = False
    last_prayer_tick: int = 0
    parent_ids: list[str] = Field(default_factory=list)
    spouse_id: str | None = None
    alive: bool = True
    quarantined: bool = False
    pos: Vec3 = Field(default_factory=Vec3)
    yaw: float = 0.0
    traits: dict[str, float] = Field(
        default_factory=lambda: {
            "caution": 0.0,
            "sociability": 0.0,
            "ambition": 0.0,
            "loyalty": 0.0,
            "rule_respect": 0.0,
            "faith_devotion": 0.0,
        }
    )
    skills: dict[str, float] = Field(
        default_factory=lambda: {
            "walk": 0.05,
            "self_care": 0.05,
        }
    )
    tradition_ids: list[str] = Field(default_factory=list)
    profession: str = "CITIZEN"
    profession_level: int = 1
    profession_xp: float = 0.0
    hygiene: float = Field(default=1.0, ge=0.0, le=1.0)
    fatigue: float = Field(default=0.0, ge=0.0, le=1.0)
    known_books: list[str] = Field(default_factory=list)
    personality: PersonalityVector | None = None
    mood: MoodState | None = None
    active_mechanical_effects: dict[str, float] = Field(default_factory=dict)
    speech_text: str = ""
    activity_state: str = "IDLE"
    equipped_gear: list[str] = Field(default_factory=list)
    home_building_id: str | None = None


class DivinePersonality(BaseModel):
    compassion: float = Field(default=0.6, ge=0.0, le=1.0)
    restraint: float = Field(default=0.6, ge=0.0, le=1.0)
    pride: float = Field(default=0.5, ge=0.0, le=1.0)
    protective_fury: float = Field(default=0.5, ge=0.0, le=1.0)
    diplomacy: float = Field(default=0.6, ge=0.0, le=1.0)


class DivineEntityRecord(BaseModel):
    slot: DeitySlot
    bestowed_name: str
    role: Literal["WORLD_GODDESS", "RACIAL_GOD_MOTHER"]
    patron_race: RaceId | None = None
    divine_energy: float = Field(default=300.0, ge=0.0, le=1000.0)
    personality: DivinePersonality = Field(default_factory=DivinePersonality)
    personality_vector: PersonalityVector | None = None
    mood: MoodState | None = None
    oracle_agent_ids: list[str] = Field(default_factory=list)
    active_truce_with: list[DeitySlot] = Field(default_factory=list)
    intervention_cooldown_until_tick: int = 0
    covenant_rebukes: int = 0


class SisterCouncilMessage(BaseModel):
    message_id: str
    day: int
    tick: int
    sender_slot: DeitySlot
    recipient_slots: list[DeitySlot]
    topic: Literal[
        "BORDER_FRICTION",
        "DRAGON_PROVOCATION",
        "WAR_INTERVENTION",
        "DIVINE_TRUCE",
        "COVENANT_BREACH",
        "FREE_CITY_ACCORD",
        "GOD_ESCALATION",
    ]
    summary: str
    resolution: str | None = None


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
    parent_polity_id: str | None = None
    regime_type: RegimeType = "ELECTED"
    is_holy_polity: bool = False
    is_neutral_free_city: bool = False
    war_exempt: bool = False
    state_religion_id: str | None = None
    founder_id: str
    leader_id: str | None = None
    center_pos: Vec3
    border_parcel_ids: list[str] = Field(default_factory=list)
    treasury_credits: float = 100.0
    tax_rate: float = Field(default=0.05, ge=0.0, le=0.30)
    tariff_rate: float = Field(default=0.0, ge=0.0, le=0.50)
    next_election_tick: int | None = None
    laws: dict[str, Any] = Field(
        default_factory=lambda: {
            "theft_fine_mult": 2.0,
            "assault_fine": 60.0,
            "banish_on_repeat_offenses": 3,
            "infant_welfare_enabled": True,
            "property_tax_rate": 0.01,
        }
    )
    at_war_with: list[str] = Field(default_factory=list)
    allied_with: list[str] = Field(default_factory=list)
    founded_tick: int = 0


class SettlementAppealRecord(BaseModel):
    appeal_id: str
    settlement_id: str
    proposer_id: str
    appeal_kind: Literal["TIER_UPGRADE", "NEUTRAL_FREE_CITY"] = "TIER_UPGRADE"
    current_tier: SettlementTier | None = None
    requested_tier: SettlementTier | None = None
    claimed_parcel_ids: list[str] = Field(default_factory=list)
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    reason: str = ""
    submitted_tick: int


class ReligionRecord(BaseModel):
    religion_id: str
    name: str
    aligned_deity_slot: DeitySlot = "world_goddess"
    founder_id: str
    pope_id: str | None = None
    treasury_credits: float = 0.0
    tenets: dict[str, float] = Field(
        default_factory=lambda: {
            "pacifism": 0.5,
            "charity_tithe_rate": 0.05,
            "work_ethic": 0.5,
            "sacred_land_defense": 0.5,
            "heresy_intolerance": 0.2,
        }
    )
    canonized_entry_ids: list[str] = Field(default_factory=list)
    excommunicated_ids: list[str] = Field(default_factory=list)
    founded_tick: int = 0


class ParcelRecord(BaseModel):
    parcel_id: str  # f"{cx}_{cz}"
    cx: int
    cz: int
    settlement_id: str | None = None
    nation_id: str | None = None
    owner_id: str | None = None
    owner_type: ParcelOwnerType = "UNCLAIMED"
    has_altar: bool = False
    has_library: bool = False
    assessed_value: float = 50.0
    for_sale_price: float | None = None
    tenant_id: str | None = None
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
    cpi: float = 1.0
    money_supply_m: float
    real_output_q: float
    prices: dict[str, float]
    frozen: bool = False


class JudiciaryCaseRecord(BaseModel):
    case_id: str
    settlement_id: str | None
    accused_id: str
    victim_id: str | None = None
    offense_type: Literal[
        "THEFT", "UNPROVOKED_ATTACK", "VANDALISM", "DEBT_DEFAULT", "TRESPASS", "CONTESTED_COMBAT"
    ]
    combat_context: CombatContext | None = None
    witness_ids: list[str] = Field(default_factory=list)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    ruling: Literal["ACQUITTED", "RESTITUTION", "FINE", "GARNISH", "BANISHMENT"] | None = None
    penalty_credits: float = 0.0
    opened_tick: int
    closed_tick: int | None = None


class FatalityRecord(BaseModel):
    agent_id: str
    display_name: str
    race: RaceId
    sub_lineage: BeasthumanSubLineage | None = None
    secondary_heritage_race: RaceId | None = None
    age_ticks: int
    stage_at_death: Stage
    cause: DeathCause
    combat_context: CombatContext | None = None
    killer_id: str | None = None
    settlement_id: str | None = None
    season: Season
    death_day: int
    death_tick: int


class WorldLibraryEntry(BaseModel):
    entry_id: str
    topic: str
    title: str
    summary: str
    author_id: str
    author_proficiency: float = Field(default=1.0, ge=0.0, le=1.0)
    skill_bonus: float = Field(default=0.08, ge=0.01, le=0.15)
    is_scripture: bool = False
    read_count: int = 0
    created_tick: int
    body: str | None = None
    subject: str | None = None
    section: str | None = None
    fact_key: str | None = None
    tags: list[str] = Field(default_factory=list)
    mechanical_effects: dict[str, float] = Field(default_factory=dict)
    author_type: Literal["DIVINE", "MORTAL", "SYSTEM", "UNKNOWN"] = "MORTAL"
    supersedes: list[str] = Field(default_factory=list)
    distinct_from: list[str] = Field(default_factory=list)


class LibraryCouncilElderRecord(BaseModel):
    nation_id: str
    agent_id: str
    appointed_tick: int


class LibraryProposalRecord(BaseModel):
    proposal_id: str
    action: Literal["CREATE", "EDIT", "SUPERSEDE"]
    target_entry_id: str | None = None
    author_id: str
    topic: str
    title: str
    summary: str
    author_proficiency: float = Field(ge=0.0, le=1.0)
    votes_approve: list[str] = Field(default_factory=list)
    votes_reject: list[str] = Field(default_factory=list)
    godmother_approvals: list[DeitySlot] = Field(default_factory=list)
    godmother_objections: list[DeitySlot] = Field(default_factory=list)
    first_approval_tick: int | None = None
    appeal_target: Literal["WORLD_GODDESS", "GOD"] | None = None
    appeal_ruling: str | None = None
    status: Literal[
        "OPEN",
        "PENDING_GODMOTHERS",
        "OBJECTION_WINDOW",
        "BLOCKED_BY_DAUGHTERS",
        "EXPIRED",
        "APPROVED",
        "REJECTED",
    ] = "OPEN"
    created_tick: int
    body: str | None = None
    subject: str | None = None
    section: str | None = None
    fact_key: str | None = None
    tags: list[str] = Field(default_factory=list)
    mechanical_effects: dict[str, float] = Field(default_factory=dict)
    author_type: Literal["DIVINE", "MORTAL", "SYSTEM", "UNKNOWN"] = "MORTAL"
    supersedes: list[str] = Field(default_factory=list)
    distinct_from: list[str] = Field(default_factory=list)


class DivineCodexEntry(BaseModel):
    entry_id: str
    title: str
    text: str
    category: Literal["DECREE", "COVENANT_LAW", "WAR_DIRECTIVE", "PARAMETER_OVERRIDE"]
    parameter_key: str | None = None
    parameter_value_json: str | None = None
    author_slot: str  # "GOD", "world_goddess", or "gm_*"
    supporting_daughter_slots: list[DeitySlot] = Field(default_factory=list)
    approved_by_god: bool = False
    created_tick: int


class DivineCodexProposalRecord(BaseModel):
    proposal_id: str
    title: str
    text: str
    parameter_key: str
    parameter_value_json: str
    proposer_slot: DeitySlot  # "world_goddess" (alone) or "gm_*"
    co_sponsors: list[DeitySlot] = Field(default_factory=list)
    status: Literal["PENDING_GOD", "APPROVED", "REJECTED"] = "PENDING_GOD"
    submitted_tick: int
    resolved_tick: int | None = None


class TraditionRecord(BaseModel):
    tradition_id: str
    name: str
    origin_settlement_id: str
    trigger: Literal[
        "FIRST_DAY_OF_WINTER",
        "HARVEST_SURPLUS",
        "ROYAL_DEATH",
        "MARRIAGE",
        "WAR_VICTORY",
        "GOD_SIGHTING",
    ]
    ritual_action: Literal[
        "GIFT_FOOD_IN_SQUARE",
        "GATHER_AT_TEMPLE",
        "SILENT_FAST",
        "PUBLIC_FEAST",
        "BUILD_MONUMENT_STEP",
    ]
    adoption_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    taboo_penalty: float = Field(default=0.15, ge=0.0, le=0.5)
    created_tick: int


class GodLedgerEntry(BaseModel):
    entry_id: str
    day: int
    tick: int
    category: Literal[
        "WORLD_GODDESS_SUMMARY",
        "GOD_MOTHER_REPORT",
        "CONGREGATIONAL_ALTAR",
        "SISTER_COUNCIL",
        "PATRON_TIE_BREAK",
        "PRAYER_DIGEST",
        "MILESTONE",
        "HEALER_ALERT",
        "CRITICAL_ESCALATION",
        "PALACE_SECURITY",
    ]
    deity_slot: DeitySlot | None = None
    speaker_name: str
    prayer_head_name: str | None = None
    settlement_name: str | None = None
    group_size: int = 1
    intent: PrayerIntent | None = None
    message: str
    delivered_realtime: bool = False


class DailyManifest(BaseModel):
    day: int
    tick: int
    season: Season
    committed_by: str
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
    actor_id: str | None = None
    payload: dict[str, Any]
    bypass_god_check: bool = False


class CriticVerdict(BaseModel):
    proposal_id: str
    kind: CommitKind
    actor_id: str | None = None
    status: Literal["SUCCESS", "FAILURE"]
    reason: str
    committed_tick: int | None = None


PalaceDecision = Literal["GRANT", "DENY", "ESCORT"]
PalaceRequestStatus = Literal["PENDING", "GRANTED", "DENIED", "ESCORTED", "EXPIRED"]


class PalacePass(BaseModel):
    pass_id: str
    agent_id: str
    granted_by: Literal["GOD", "WORLD_GODDESS"]
    granted_tick: int
    expires_tick: int


class PalaceEntryRequest(BaseModel):
    request_id: str
    agent_id: str
    name: str
    race: RaceId
    title: str | None = None
    criminal_count: int = 0
    faith_devotion: float = 0.5
    reason: str = "Petitioning Audience"
    tick: int = 0
    status: PalaceRequestStatus = "PENDING"


class BuildingRecord(BaseModel):
    building_id: str
    city_id: str
    building_type: BuildingType
    racial_style: RacialStyle
    x: float
    y: float
    z: float
    rotation_y: float
    parcel_x: int
    parcel_z: int
    footprint_radius: float = 8.0
    owner_id: str | None = None
    owner_name: str | None = None
    for_sale: bool = False
    sale_price: float = 0.0
    settlement_id: str | None = None
    is_frontier: bool = False


class CityRecord(BaseModel):
    city_id: str
    name: str
    native_race: RaceId
    racial_style: RacialStyle
    center_x: float
    center_z: float
    elevation_y: float
    curtain_wall_radius: float = 240.0
    godmother_slot: RacialGodMotherSlot
    buildings_count: int = 0


SpeechActType = Literal[
    "GREET",
    "WARN_PRICE_SPIKE",
    "TRADE_OFFER",
    "SHARE_BOOK_LORE",
    "REPORT_CRIME",
    "PRAYER_CALL",
    "COURT",
    "POLITICAL_DEBATE",
]


class SpeechActRecord(BaseModel):
    speech_id: str
    speaker_id: str
    speaker_name: str = ""
    listener_id: str | None = None
    act_type: SpeechActType
    topic: str = ""
    value: float = 0.0
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    trust_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    tick: int = 0
    short_utterance: str = ""


class DeitySyncRecord(BaseModel):
    id: str
    name: str
    title: str = ""
    race: str = "DIVINE"
    x: float
    y: float
    z: float
    yaw: float = 0.0
    speed: float = 0.0
    activity: str = "IDLE"
    speech_text: str = ""


class DialogueRequest(BaseModel):
    type: Literal["DIALOGUE_REQUEST"] = "DIALOGUE_REQUEST"
    dialogue_id: str = ""
    target_type: Literal["DEITY", "MORTAL"] = "DEITY"
    target_id: str
    message: str
    order: str = ""


class DialogueResponse(BaseModel):
    type: Literal["DIALOGUE_RESPONSE"] = "DIALOGUE_RESPONSE"
    target_id: str
    target_name: str
    title: str = ""
    race: str = "DIVINE"
    mood: str = "calm"
    spoken_reply: str
    action_taken: str = ""
    llm_backend: str = "OFFLINE_FALLBACK"
