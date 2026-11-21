"""
sim_core/society/naming.py
Autonomous racial, gender, and cultural phoneme naming generator,
inherited dynasty surnames, adult self-naming, and earned epithets.
Follows NEURAL_AND_LIFECYCLE_SPEC.md Section 5.3.
"""

from __future__ import annotations

import random
from typing import Any

from sim_core.schemas import Gender, RaceId

# -----------------------------------------------------------------------------
# Racial & Gender Name Datasets
# -----------------------------------------------------------------------------
NAMES_DATABASE: dict[str, dict[Gender, list[str]]] = {
    "HUMAN": {
        "BOY": [
            "Aldric", "Kaelen", "Cedric", "Lucian", "Valen",
            "Gareth", "Rowan", "Tristan", "Edwin", "Thomas", "Roger",
        ],
        "GIRL": [
            "Mira", "Clara", "Elena", "Vivian", "Lydia",
            "Rose", "Juliana", "Beatrice", "Adele", "Constance",
        ],
    },
    "ELF": {
        "BOY": [
            "Aelarion", "Faelar", "Sylas", "Thalor", "Elenion",
            "Caelynn", "Lorian", "Ilidor", "Aerin",
        ],
        "GIRL": [
            "Lyra", "Aeris", "Eleniel", "Vaeloria", "Naevys",
            "Althea", "Sylphira", "Fiora", "Ilyria",
        ],
    },
    "DRAGON": {
        "BOY": [
            "Ignis", "Pyror", "Ashwing", "Drakor", "Vermith",
            "Caldera", "Ignith", "Fyrion", "Balaur", "Smaug",
        ],
        "GIRL": [
            "Pyra", "Caldera", "Ashira", "Cinder", "Vesta",
            "Ignia", "Vermithra", "Drakira", "Solaria",
        ],
    },
    "BEASTHUMAN_CAT_KIN": {
        "BOY": [
            "Felix", "Leo", "Talon", "Neko", "Kuro", "Milo", "Jasper", "Lynx",
        ],
        "GIRL": [
            "Mia", "Nya", "Kira", "Saffron", "Luna", "Cleo", "Tabbie",
        ],
    },
    "BEASTHUMAN_DWARF": {
        "BOY": [
            "Torin", "Brokk", "Duer", "Thrain", "Gimli", "Berta", "Balin", "Durin", "Thrum",
        ],
        "GIRL": [
            "Valka", "Dwerga", "Helga", "Astrid", "Brida", "Torra", "Thora", "Gunnhild",
        ],
    },
    "BEASTHUMAN_WOLF_KIN": {
        "BOY": [
            "Fenrir", "Boris", "Lyall", "Vuk", "Remus", "Timber", "Fang", "Gray",
        ],
        "GIRL": [
            "Luna", "Sonya", "Freya", "Lyanna", "Lupa", "Frost", "Tala", "Silvia",
        ],
    },
    "BEASTHUMAN_BARBARIAN": {
        "BOY": [
            "Bjorn", "Korg", "Thorkell", "Rurik", "Beorn", "Gunnar", "Ragnar", "Sigurd",
        ],
        "GIRL": [
            "Ursula", "Hilda", "Astrid", "Freydis", "Sigrid", "Yrsa", "Brynhild",
        ],
    },
    "DEMON": {
        "BOY": [
            "Malakor", "Azael", "Belial", "Vassago", "Bael",
            "Xaphan", "Morvath", "Dagon", "Kragor", "Nergal",
        ],
        "GIRL": [
            "Lilith", "Morrigan", "Naamah", "Alruna", "Qarinah",
            "Hecate", "Bathsheba", "Nocturna", "Ravana", "Astarte",
        ],
    },
}

SURNAMES_DATABASE: dict[str, list[str]] = {
    "HUMAN": [
        "Thornwood", "Riverstone", "Crownguard", "Fairbairn", "Ashford",
        "Blackwood", "Dale", "Miller", "Vance", "Ironwood",
    ],
    "ELF": [
        "Silverleaf", "Moonwhisper", "Starfall", "Whisperwind", "Sunstrider",
        "Greenvale", "Dawnstrider", "Evenstar", "Silvershine",
    ],
    "DRAGON": [
        "Ashwing", "Flamepeak", "Cindercrest", "Wyrmheart", "Obsidian",
        "Smokecrag", "Redtalon", "Pyrespire", "Drakebane",
    ],
    "BEASTHUMAN_CAT_KIN": [
        "Swiftpaw", "Whiskerstride", "Shadowtail", "Softstep", "Clawford", "Whiskerton",
    ],
    "BEASTHUMAN_DWARF": [
        "Ironbeard", "Stonehammer", "Deepdelver", "Forgefire", "Anvilbrow", "Coppervein",
    ],
    "BEASTHUMAN_WOLF_KIN": [
        "Moonfang", "Greyhowl", "Frostfur", "Packstride", "Bloodfang", "Silvermane",
    ],
    "BEASTHUMAN_BARBARIAN": [
        "Bearskin", "Ironridge", "Frostbane", "Mountaincleaver", "Wildheart", "Stormborn",
    ],
    "DEMON": [
        "Abysswalker", "Hellsent", "Brimstone", "Shadowflame", "Ashcarver",
        "Nightvein", "Obsidianveil", "Ruinweaver", "Dreadspire", "Voidthorn",
    ],
}


def _resolve_naming_key(race: RaceId, sub_lineage: str | None) -> str:
    """Resolves race and optional Beasthuman sub-lineage to a dataset key."""
    if race == "BEASTHUMAN":
        if sub_lineage:
            sub = sub_lineage.upper()
            if "CAT" in sub:
                return "BEASTHUMAN_CAT_KIN"
            if "DWARF" in sub:
                return "BEASTHUMAN_DWARF"
            if "WOLF" in sub:
                return "BEASTHUMAN_WOLF_KIN"
            if "BEAR" in sub or "BARBARIAN" in sub:
                return "BEASTHUMAN_BARBARIAN"
        return "BEASTHUMAN_CAT_KIN"
    return race


def generate_birth_name(
    race: RaceId,
    gender: Gender,
    sub_lineage: str | None = None,
    seed: int | None = None,
) -> str:
    """Generates a culturally flavored given name for a newborn agent."""
    rng = random.Random(seed) if seed is not None else random.Random()
    key = _resolve_naming_key(race, sub_lineage)
    name_list = NAMES_DATABASE.get(key, NAMES_DATABASE["HUMAN"])[gender]
    return rng.choice(name_list)


def generate_dynasty_surname(
    race: RaceId,
    sub_lineage: str | None = None,
    seed: int | None = None,
) -> str:
    """Generates a dynasty family surname for a founder or unnamed lineage."""
    rng = random.Random(seed) if seed is not None else random.Random()
    key = _resolve_naming_key(race, sub_lineage)
    surname_list = SURNAMES_DATABASE.get(key, SURNAMES_DATABASE["HUMAN"])
    return rng.choice(surname_list)


def inherit_dynasty_surname(
    parent1_surname: str | None,
    parent2_surname: str | None,
    race: RaceId,
    sub_lineage: str | None = None,
    seed: int | None = None,
) -> str:
    """
    Inherits family surname from parents (favoring existing parental dynasties),
    or generates a new culturally resonant surname if neither parent has one.
    """
    valid_surnames = [s for s in (parent1_surname, parent2_surname) if s and s.strip()]
    if valid_surnames:
        rng = random.Random(seed) if seed is not None else random.Random()
        return rng.choice(valid_surnames)
    return generate_dynasty_surname(race, sub_lineage, seed)


def award_epithet(deeds: dict[str, Any]) -> str | None:
    """
    Evaluates mortal deeds, mastery, and life milestones to bestow earned epithets upon ADULT/ELDER.
    Deeds can contain:
      - library_books_authored: int
      - defense_kills: int
      - prayers_sent: int
      - wtc_volume: float
      - dragon_friend: bool
      - children_raised: int
      - crafts_completed: int
    """
    if deeds.get("library_books_authored", 0) >= 3:
        return "the Chronicler"
    if deeds.get("dragon_friend", False):
        return "the Dragon-Friend"
    if deeds.get("defense_kills", 0) >= 5:
        return "Ironhand"
    if deeds.get("prayers_sent", 0) >= 25:
        return "the Devout"
    if deeds.get("wtc_volume", 0.0) >= 1000.0:
        return "the Prosperous"
    if deeds.get("crafts_completed", 0) >= 20:
        return "the Maker"
    if deeds.get("children_raised", 0) >= 4:
        return "the Patriarch" if deeds.get("gender") == "BOY" else "the Matriarch"
    return None
