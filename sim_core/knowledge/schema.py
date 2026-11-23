"""
sim_core/knowledge/schema.py
Pydantic v2 schemas for Knowledge Foundry entries, packs, and anachronism validation.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CANONICAL_SUBJECTS = [
    "tactics_and_warfare",
    "craft_and_metallurgy",
    "architecture_and_engineering",
    "agriculture_and_botany",
    "medicine_and_biology",
    "economics_and_trade",
    "law_and_governance",
    "philosophy_and_culture",
    "natural_history_and_geography",
    "divine_theology_and_history",
]

SubjectLiteral = Literal[
    "tactics_and_warfare",
    "craft_and_metallurgy",
    "architecture_and_engineering",
    "agriculture_and_botany",
    "medicine_and_biology",
    "economics_and_trade",
    "law_and_governance",
    "philosophy_and_culture",
    "natural_history_and_geography",
    "divine_theology_and_history",
]

FORBIDDEN_ANACHRONISMS = [
    "internet",
    "smartphone",
    "cellphone",
    "electricity",
    "electrical",
    "nuclear",
    "atomic",
    "wikipedia",
    "steam engine",
    "computer",
    "computing",
    "silicon",
    "plastic",
    "plastics",
    "wifi",
    "wi-fi",
    "television",
    "satellite",
    "diesel",
    "gasoline",
    "petrol",
    "robotics",
    "semiconductor",
    "quantum",
    "laser",
    "microchip",
    "transistor",
    "nanotech",
    "nanotechnology",
    "machine learning",
    "neural network",
    "social media",
]

# Pre-compile regex for word-boundary matching of forbidden terms
ANACHRONISM_PATTERNS = [
    (term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)) for term in FORBIDDEN_ANACHRONISMS
]

MECHANICAL_EFFECT_BOUNDS: dict[str, tuple[float, float]] = {
    "defense_bonus": (-0.50, 0.50),
    "combat_power_multiplier": (-0.50, 0.50),
    "patrol_efficiency": (-0.50, 0.50),
    "craft_speed_bonus": (-0.50, 0.50),
    "smelting_yield_bonus": (-0.50, 0.50),
    "tool_durability_bonus": (-0.50, 0.50),
    "construction_cost_reduction": (-0.50, 0.50),
    "structural_integrity_bonus": (-0.50, 0.50),
    "crop_yield_bonus": (-0.50, 0.50),
    "spoilage_reduction": (-0.50, 0.50),
    "winter_hardiness": (-0.50, 0.50),
    "healing_rate_bonus": (-0.50, 0.50),
    "infection_resistance": (-0.50, 0.50),
    "fertility_rate_bonus": (-0.50, 0.50),
    "trade_fee_reduction": (-0.50, 0.50),
    "market_clearing_efficiency": (-0.50, 0.50),
    "credit_default_reduction": (-0.50, 0.50),
    "civil_stability_bonus": (-0.50, 0.50),
    "judicial_accuracy": (-0.50, 0.50),
    "reputation_bonus": (-0.50, 0.50),
    "faith_devotion_bonus": (-0.50, 0.50),
    "divine_favor_generation": (-0.50, 0.50),
    "attrition_reduction": (-0.50, 0.50),
}


def validate_anachronisms(text: str) -> str | None:
    """Returns the forbidden word if an anachronism is detected, otherwise None."""
    for term, pattern in ANACHRONISM_PATTERNS:
        if pattern.search(text):
            return term
    return None


class KnowledgeEntry(BaseModel):
    entry_id: str = Field(
        ...,
        min_length=4,
        max_length=64,
        pattern=r"^[a-z0-9_]{4,64}$",
        description="Globally unique snake_case identifier",
    )
    subject: SubjectLiteral = Field(
        ...,
        description="One of the 10 canonical subjects",
    )
    target_section: str = Field(
        ...,
        min_length=2,
        max_length=64,
        description="Target section in World Library",
    )
    fact_key: str = Field(
        ...,
        pattern=r"^[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+$",
        description="Dot-notation address: <subject>.<subtopic>.<concept>",
    )
    title: str = Field(..., min_length=4, max_length=120)
    summary: str = Field(..., min_length=20, max_length=600)
    body: str = Field(..., min_length=50, max_length=6000)
    author: str = Field(..., min_length=2, max_length=64)
    author_type: Literal["DIVINE", "MORTAL", "SYSTEM", "UNKNOWN"] = "MORTAL"
    era_tier: int = Field(default=1, ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=16)
    prerequisites: list[str] = Field(default_factory=list, max_length=12)
    mechanical_effects: dict[str, float] = Field(default_factory=dict)
    supersedes: list[str] = Field(default_factory=list)
    distinct_from: list[str] = Field(default_factory=list)

    @field_validator("title", "summary", "body")
    @classmethod
    def check_text_anachronisms(cls, v: str, info: Any) -> str:
        forbidden = validate_anachronisms(v)
        if forbidden:
            raise ValueError(
                f"Anachronism detected in {info.field_name}: forbidden modern term '{forbidden}'"
            )
        return v

    @field_validator("tags")
    @classmethod
    def check_tags(cls, v: list[str]) -> list[str]:
        cleaned = []
        for t in v:
            t_clean = t.strip().lower()
            forbidden = validate_anachronisms(t_clean)
            if forbidden:
                raise ValueError(f"Anachronism detected in tag: forbidden term '{forbidden}'")
            if not re.match(r"^[a-z0-9_]{2,48}$", t_clean):
                raise ValueError(f"Tag '{t}' must match ^[a-z0-9_]{{2,48}}$")
            cleaned.append(t_clean)
        return cleaned

    @field_validator("mechanical_effects")
    @classmethod
    def check_effects(cls, v: dict[str, float]) -> dict[str, float]:
        for key, val in v.items():
            if not isinstance(val, (int, float)):
                raise ValueError(f"Mechanical effect '{key}' must have numeric value")
            low, high = MECHANICAL_EFFECT_BOUNDS.get(key, (-1.0, 1.0))
            if not (low <= val <= high):
                raise ValueError(
                    f"Mechanical effect '{key}' value {val} out of bounds [{low}, {high}]"
                )
        return v


class KnowledgePack(BaseModel):
    pack_id: str | None = None
    entries: list[KnowledgeEntry] = Field(..., min_length=1, max_length=30)

    @model_validator(mode="before")
    @classmethod
    def parse_list_or_dict(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"entries": data}
        return data

    @field_validator("entries")
    @classmethod
    def validate_entries_count_and_uniqueness(
        cls, entries: list[KnowledgeEntry]
    ) -> list[KnowledgeEntry]:
        if not (1 <= len(entries) <= 30):
            raise ValueError(
                f"KnowledgePack must contain between 1 and 30 entries (got {len(entries)})"
            )
        seen_ids = set()
        seen_keys = set()
        for idx, e in enumerate(entries):
            if e.entry_id in seen_ids:
                raise ValueError(
                    f"Duplicate entry_id '{e.entry_id}' within same pack (entry index {idx})"
                )
            if e.fact_key in seen_keys:
                raise ValueError(
                    f"Duplicate fact_key '{e.fact_key}' within same pack (entry index {idx})"
                )
            seen_ids.add(e.entry_id)
            seen_keys.add(e.fact_key)
        return entries
