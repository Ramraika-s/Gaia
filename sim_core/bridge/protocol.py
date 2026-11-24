"""
sim_core/bridge/protocol.py
Single authoritative contract for WebSocket message normalization between
the Python core and the Godot 4.7.2 3D client / God HUD.
Follows Gaia v4.0 IPC Protocol Specification and AGENTS.md.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_VERSION: Final[str] = "4.0.0"
TIME_OF_DAY_RANGE: Final[tuple[float, float]] = (0.0, 24.0)  # strictly hours in [0.0, 24.0)
# 0..1 Spring, 1..2 Summer, 2..3 Autumn, 3..4 Winter:
SEASON_PROGRESS_RANGE: Final[tuple[float, float]] = (0.0, 4.0)


class GodCommandPayload(BaseModel):
    """Pydantic model representing normalized GOD_COMMAND payloads."""

    model_config = ConfigDict(extra="allow")

    command: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    raw_command: str | None = None


class LibraryEditPayload(BaseModel):
    """Normalized payload for GOD_LIBRARY_EDIT submissions."""

    model_config = ConfigDict(extra="ignore")

    topic: str
    volume_title: str = "Divine Canonical Volume"
    text_content: str = ""
    author_id: str = "GOD"
    entry_id: str | None = None


class CodexEditPayload(BaseModel):
    """Normalized payload for GOD_CODEX_EDIT submissions."""

    model_config = ConfigDict(extra="ignore")

    decree_id: str
    text_decree: str = ""
    parameter_key: str | None = None
    parameter_val: Any = None


class WorldTimeWeatherPayload(BaseModel):
    """Normalized payload for WORLD_TIME_WEATHER events."""

    model_config = ConfigDict(extra="ignore")

    type: str = "WORLD_TIME_WEATHER"
    day: int = Field(ge=1)
    time_of_day: float = Field(ge=0.0, lt=24.0)
    season_progress: float = Field(ge=0.0, lt=4.0)
    weather: str = "CLEAR"
    weather_details: dict[str, Any] | None = None


def extract_god_command_params(data: dict[str, Any]) -> dict[str, Any]:
    """
    Merges nested data.get("args", {}) (emitted by Godot's WsBridgeClient.send_god_command)
    with top-level keys (used by existing Python tests and callers), so both flat
    and nested GOD_COMMAND payloads resolve identically.
    Nested args take precedence if duplicate keys are present.
    """
    params: dict[str, Any] = {}
    for k, v in data.items():
        if k not in ("type", "args"):
            params[k] = v
    args = data.get("args")
    if isinstance(args, dict):
        params.update(args)
    return params


def normalize_library_edit_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes topic, volume_title/title, text_content/body/summary, author_id,
    and optional explicit entry_id into a canonical dictionary validated against
    the LibraryEditPayload Pydantic schema.
    """
    topic = str(data.get("topic", "")).strip()
    title = str(data.get("volume_title") or data.get("title") or "Divine Canonical Volume").strip()
    text_content = str(
        data.get("text_content") or data.get("body") or data.get("summary") or ""
    ).strip()
    author_id = str(data.get("author_id") or "GOD").strip()
    raw_entry_id = data.get("entry_id")
    entry_id = str(raw_entry_id).strip() if raw_entry_id is not None else None
    if not entry_id:
        entry_id = None

    payload_model = LibraryEditPayload(
        topic=topic,
        volume_title=title,
        text_content=text_content,
        author_id=author_id,
        entry_id=entry_id,
    )

    return {
        "topic": payload_model.topic,
        "volume_title": payload_model.volume_title,
        "title": payload_model.volume_title,
        "text_content": payload_model.text_content,
        "body": payload_model.text_content,
        "summary": payload_model.text_content,
        "author_id": payload_model.author_id,
        "entry_id": payload_model.entry_id,
    }


def resolve_library_entry_id(
    topic: str,
    volume_title: str,
    existing_entries: dict[str, Any] | None = None,
    explicit_entry_id: str | None = None,
) -> str:
    """
    Determines the unique entry_id for a library volume.
    - If explicit_entry_id is provided, uses it.
    - If an entry with matching topic and title already exists in existing_entries,
      preserves and reuses its existing entry_id (handles updates cleanly).
    - If f"lib_{topic}" does not exist in existing_entries, uses f"lib_{topic}".
    - If f"lib_{topic}" exists with a different title, generates deterministic unique
      f"lib_{topic_slug}_{title_slug}_{short_hash}" so separate volumes under the same topic
      never silently overwrite each other.
    """
    if explicit_entry_id:
        return explicit_entry_id.strip()

    topic_clean = topic.strip()
    title_clean = volume_title.strip()

    # Check if an entry with matching topic and title already exists in existing_entries
    if existing_entries:
        for eid, entry in existing_entries.items():
            etopic = getattr(entry, "topic", None) or (
                entry.get("topic") if isinstance(entry, dict) else None
            )
            etitle = getattr(entry, "title", None) or (
                entry.get("title") or entry.get("volume_title") if isinstance(entry, dict) else None
            )
            if etopic == topic_clean and etitle == title_clean:
                return eid

    slug = re.sub(r"[^\w]+", "_", topic_clean).strip("_")
    default_key = f"lib_{topic_clean}" if topic_clean.isidentifier() else f"lib_{slug or 'general'}"
    if not existing_entries or default_key not in existing_entries:
        return default_key

    # Distinct volume under existing topic -> generate deterministic unique ID
    topic_slug = re.sub(r"[^\w]+", "_", topic_clean.lower()).strip("_") or "volume"
    title_slug = re.sub(r"[^\w]+", "_", title_clean.lower()).strip("_") or "untitled"
    hash_input = f"{topic_clean}:{title_clean}".encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:8]
    return f"lib_{topic_slug}_{title_slug}_{short_hash}"


def normalize_codex_edit_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes decree_id/title, text_decree/text, parameter_key, and
    parameter_val/parameter_value into a canonical dictionary validated against
    the CodexEditPayload Pydantic schema.
    """
    decree_id = str(
        data.get("decree_id") or data.get("title") or f"decree_{uuid.uuid4().hex[:8]}"
    ).strip()
    text = str(data.get("text_decree") or data.get("text") or "").strip()
    param_key = data.get("parameter_key")
    if param_key is not None:
        param_key = str(param_key).strip() or None
    param_val = data.get("parameter_val")
    if param_val is None:
        param_val = data.get("parameter_value")

    payload_model = CodexEditPayload(
        decree_id=decree_id,
        text_decree=text,
        parameter_key=param_key,
        parameter_val=param_val,
    )

    return {
        "decree_id": payload_model.decree_id,
        "title": payload_model.decree_id,
        "text_decree": payload_model.text_decree,
        "text": payload_model.text_decree,
        "parameter_key": payload_model.parameter_key,
        "parameter_val": payload_model.parameter_val,
        "parameter_value": payload_model.parameter_val,
    }


def build_world_time_weather_payload(
    day: int,
    time_of_day_hours: float,
    season_progress: float,
    weather: str = "CLEAR",
    weather_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enforces canonical [0.0, 24.0) hours and [0.0, 4.0) season progress
    and returns a validated WORLD_TIME_WEATHER dictionary.
    """
    safe_day = max(1, int(day))
    canonical_time = float(time_of_day_hours) % 24.0
    canonical_season = float(season_progress) % 4.0

    payload: dict[str, Any] = {
        "type": "WORLD_TIME_WEATHER",
        "day": safe_day,
        "time_of_day": canonical_time,
        "season_progress": canonical_season,
        "weather": str(weather),
    }
    if weather_details:
        payload["weather_details"] = weather_details

    # Validate against Pydantic schema
    WorldTimeWeatherPayload.model_validate(payload)
    return payload
