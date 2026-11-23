"""
sim_core/brains/personality.py
Pillar 3: Evolving 10-D Personality & Mood State for Mortals and Deities.
Follows Gaia v4.0 Sprint 4 specifications:
- 10 continuous personality traits clamped [0.0, 1.0].
- Fast-decaying mood state (calm, angry, grieving, fearful, inspired).
- Racial priors with Demon generational Dragon deterrence & out-group aggression.
- Neural action logit biasing (Pillar 1 coupling)
  and memory salience biasing (Pillar 2 RAG coupling).
"""

from __future__ import annotations

import random

import numpy as np
import torch
from pydantic import BaseModel, Field

from sim_core.races import RaceId


class PersonalityVector(BaseModel):
    """
    10-Dimensional continuous personality vector clamped strictly to [0.0, 1.0].
    Governs individual cognitive variance, action selection bias, and RAG recall.
    """

    courage: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    ambition: float = Field(default=0.5, ge=0.0, le=1.0)
    discipline: float = Field(default=0.5, ge=0.0, le=1.0)
    curiosity: float = Field(default=0.5, ge=0.0, le=1.0)
    devotion: float = Field(default=0.5, ge=0.0, le=1.0)
    honesty: float = Field(default=0.5, ge=0.0, le=1.0)
    out_group_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    caution: float = Field(default=0.5, ge=0.0, le=1.0)
    pride: float = Field(default=0.5, ge=0.0, le=1.0)

    def to_list(self) -> list[float]:
        return [
            self.courage,
            self.empathy,
            self.ambition,
            self.discipline,
            self.curiosity,
            self.devotion,
            self.honesty,
            self.out_group_trust,
            self.caution,
            self.pride,
        ]

    def to_tensor(self, device: str | torch.device = "cpu") -> torch.Tensor:
        return torch.tensor(self.to_list(), dtype=torch.float32, device=device)

    def apply_drift(self, deltas: dict[str, float], max_step: float = 0.03) -> None:
        """Applies bounded personality trait drift clamped to [0.0, 1.0]."""
        for trait, delta in deltas.items():
            if hasattr(self, trait):
                current = getattr(self, trait)
                clamped_delta = max(-max_step, min(max_step, delta))
                setattr(self, trait, max(0.0, min(1.0, current + clamped_delta)))


class MoodState(BaseModel):
    """
    Fast-decaying emotional state clamped [0.0, 1.0].
    Decays toward baseline calm in sleep and low-threat environments.
    """

    calm: float = Field(default=0.8, ge=0.0, le=1.0)
    angry: float = Field(default=0.0, ge=0.0, le=1.0)
    grieving: float = Field(default=0.0, ge=0.0, le=1.0)
    fearful: float = Field(default=0.0, ge=0.0, le=1.0)
    inspired: float = Field(default=0.2, ge=0.0, le=1.0)

    def to_list(self) -> list[float]:
        return [self.calm, self.angry, self.grieving, self.fearful, self.inspired]

    def to_tensor(self, device: str | torch.device = "cpu") -> torch.Tensor:
        return torch.tensor(self.to_list(), dtype=torch.float32, device=device)

    def step_decay(self, rate: float = 0.08, decay_rate: float | None = None) -> None:
        """Decays intense emotions toward calm baseline."""
        r = decay_rate if decay_rate is not None else rate
        self.angry = max(0.0, self.angry - r)
        self.grieving = max(0.0, self.grieving - r * 0.5)
        self.fearful = max(0.0, self.fearful - r)
        self.inspired = max(0.1, self.inspired - r * 0.3)
        self.calm = min(1.0, 1.0 - (self.angry + self.fearful + self.grieving) * 0.5)

    def dominant_mood(self) -> str:
        """Returns the highest intensity emotional state."""
        moods = {
            "angry": self.angry,
            "fearful": self.fearful,
            "grieving": self.grieving,
            "inspired": self.inspired,
            "calm": self.calm,
        }
        return max(moods, key=lambda k: moods[k])


# ------------------------------------------------------------------------------
# Racial Personality Priors & Generation
# ------------------------------------------------------------------------------
RACIAL_PRIORS: dict[RaceId, dict[str, float]] = {
    "DEMON": {
        "courage": 0.75,
        "empathy": 0.35,
        "ambition": 0.70,
        "discipline": 0.65,
        "curiosity": 0.60,
        "devotion": 0.85,  # High reverence for gm_demon
        "honesty": 0.50,
        "out_group_trust": 0.20,  # Generational out-group wariness/aggression prior
        "caution": 0.70,  # Generational Dragon deterrence
        "pride": 0.80,
    },
    "DRAGON": {
        "courage": 0.85,
        "empathy": 0.40,
        "ambition": 0.75,
        "discipline": 0.70,
        "curiosity": 0.60,
        "devotion": 0.70,
        "honesty": 0.65,
        "out_group_trust": 0.45,
        "caution": 0.40,
        "pride": 0.90,
    },
    "ELF": {
        "courage": 0.55,
        "empathy": 0.65,
        "ambition": 0.50,
        "discipline": 0.80,
        "curiosity": 0.75,
        "devotion": 0.75,
        "honesty": 0.70,
        "out_group_trust": 0.50,
        "caution": 0.65,
        "pride": 0.65,
    },
    "BEASTHUMAN": {
        "courage": 0.70,
        "empathy": 0.60,
        "ambition": 0.55,
        "discipline": 0.60,
        "curiosity": 0.55,
        "devotion": 0.65,
        "honesty": 0.75,
        "out_group_trust": 0.50,
        "caution": 0.50,
        "pride": 0.60,
    },
    "HUMAN": {
        "courage": 0.55,
        "empathy": 0.60,
        "ambition": 0.70,
        "discipline": 0.55,
        "curiosity": 0.70,
        "devotion": 0.60,
        "honesty": 0.60,
        "out_group_trust": 0.60,
        "caution": 0.50,
        "pride": 0.50,
    },
}


def generate_personality_vector(
    race: RaceId,
    parents: list[PersonalityVector] | None = None,
    rng: random.Random | None = None,
) -> PersonalityVector:
    """
    Generates a 10-D personality vector from racial priors or parental crossover,
    adding Gaussian individual mutation while strictly clamping [0.0, 1.0].
    """
    prior = RACIAL_PRIORS.get(race, RACIAL_PRIORS["HUMAN"])
    traits: dict[str, float] = {}

    for trait in [
        "courage",
        "empathy",
        "ambition",
        "discipline",
        "curiosity",
        "devotion",
        "honesty",
        "out_group_trust",
        "caution",
        "pride",
    ]:
        if parents and len(parents) > 0:
            # Parental genetic crossover (mean of parents) + small mutation
            parent_vals = [getattr(p, trait) for p in parents if hasattr(p, trait)]
            base_val = sum(parent_vals) / float(len(parent_vals))
            noise = rng.gauss(0.0, 0.05) if rng else random.gauss(0.0, 0.05)
        else:
            # Racial anchor + individual Gaussian variation
            base_val = prior[trait]
            noise = rng.gauss(0.0, 0.07) if rng else random.gauss(0.0, 0.07)

        val = max(0.0, min(1.0, base_val + noise))
        traits[trait] = round(val, 4)

    return PersonalityVector(**traits)


# ------------------------------------------------------------------------------
# Action Logit Biasing & Memory Salience
# ------------------------------------------------------------------------------
def compute_action_logit_bias(
    personality: PersonalityVector | None,
    mood: MoodState | None,
    action_dim: int = 20,
) -> np.ndarray:
    """
    Computes a (20,) logit bias vector based on personality traits and mood state:
    Actions (0..19 matching NEURAL_AND_LIFECYCLE_SPEC.md):
      0: REST / SLEEP
      1: EAT / DRINK
      2: GROOM / HYGIENE
      3: EVADE_DANGER / RETREAT
      4: WANDER / PATROL
      5: COMFORT_CHILD / CARE
      6: STUDY_BOOK / LIBRARY
      7: CRAFT / WORK
      8: TRADE / MARKET
      9: PRAY / ALTAR
      10: CONFRONT / DEFEND
      11..19: Specialized macro actions
    """
    bias = np.zeros(action_dim, dtype=np.float32)
    if personality is None:
        return bias

    # Rest & Sleep: fatigue recovery biased by calm, inhibited by angry/fearful
    if mood:
        bias[0] += (mood.calm * 0.4) - (mood.angry * 0.6) - (mood.fearful * 0.3)

    # Groom / Hygiene: discipline
    bias[2] += personality.discipline * 0.6

    # Danger Evasion / Retreat: caution, fear
    bias[3] += personality.caution * 0.8
    if mood:
        bias[3] += (mood.fearful * 1.2) - (mood.angry * 0.4)

    # Wander / Patrol: ambition, courage
    bias[4] += (personality.ambition * 0.4) + (personality.courage * 0.3)

    # Caregiving: empathy, calm, grief
    bias[5] += personality.empathy * 0.9
    if mood:
        bias[5] += mood.calm * 0.3

    # Study / Library: curiosity, discipline, inspiration
    bias[6] += (personality.curiosity * 1.0) + (personality.discipline * 0.4)
    if mood:
        bias[6] += mood.inspired * 0.8

    # Craft / Work: discipline, ambition
    bias[7] += (personality.discipline * 0.7) + (personality.ambition * 0.5)

    # Trade: ambition, out_group_trust
    bias[8] += (personality.ambition * 0.6) + (personality.out_group_trust * 0.4)

    # Prayer / Altar: devotion
    bias[9] += personality.devotion * 1.2

    # Confront / Defend: courage, pride, anger vs caution
    confront_bias = (personality.courage * 1.0) + (personality.pride * 0.5)
    bias[10] += confront_bias - (personality.caution * 0.8)
    if mood:
        bias[10] += (mood.angry * 1.4) - (mood.fearful * 0.8)

    return bias


def compute_memory_salience_weight(
    personality: PersonalityVector | None,
    mood: MoodState | None,
    memory_tags: list[str],
) -> float:
    """
    Computes personality & mood salience multiplier for RAG recall:
    - Threat / insult / crime: amplified by pride, caution, anger.
    - Kindness / favor / trade: amplified by empathy, trust, calm.
    - Knowledge / tactics: amplified by curiosity, discipline, inspiration.
    - Devotion / divine acts: amplified by devotion.
    """
    weight = 1.0
    if personality is None:
        return weight

    tags_upper = {t.upper() for t in memory_tags}

    if any(t in tags_upper for t in ("THREAT", "ATTACK", "INSULT", "CRIME", "WAR")):
        weight += personality.caution * 0.6 + personality.pride * 0.5
        if mood:
            weight += mood.angry * 0.8 + mood.fearful * 0.6

    if any(t in tags_upper for t in ("FAVOR", "KINDNESS", "CARE", "TRADE", "AID")):
        weight += personality.empathy * 0.7 + personality.out_group_trust * 0.5
        if mood:
            weight += mood.calm * 0.4

    if any(t in tags_upper for t in ("KNOWLEDGE", "BOOK", "TACTIC", "DISCOVERY")):
        weight += personality.curiosity * 0.8 + personality.discipline * 0.4
        if mood:
            weight += mood.inspired * 0.6

    if any(t in tags_upper for t in ("DIVINE", "PRAYER", "ALTAR", "BLESSING")):
        weight += personality.devotion * 1.0

    return max(0.1, weight)
